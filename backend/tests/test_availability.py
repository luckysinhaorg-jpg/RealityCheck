"""
Tests for AvailabilityCalculator.
"""
from __future__ import annotations

import pytest
from datetime import date, datetime, timedelta, timezone

from app.models.task import UserSettings
from app.services.availability import AvailabilityCalculator


@pytest.fixture
def settings_8h():
    s = UserSettings(id=1, buffer_fraction=0.0)  # 0 % buffer for clean arithmetic
    s.daily_hours = {"0": 8, "1": 8, "2": 8, "3": 8, "4": 8, "5": 0, "6": 0}
    return s


@pytest.fixture
def settings_with_buffer():
    s = UserSettings(id=1, buffer_fraction=0.10)
    s.daily_hours = {"0": 8, "1": 8, "2": 8, "3": 8, "4": 8, "5": 0, "6": 0}
    return s


def _monday() -> date:
    """Return a Monday date (for predictable weekday indexing)."""
    d = date(2026, 10, 19)  # 2026-10-19 is a Monday
    assert d.weekday() == 0
    return d


# ── Basic availability ─────────────────────────────────────────────────────────

def test_weekday_availability(settings_8h):
    monday = _monday()
    calc = AvailabilityCalculator(settings_8h, monday, monday)
    days = calc.compute()
    assert len(days) == 1
    assert days[0].gross_hours == 8.0
    # With 15 min break every 2 h: 4 breaks in 8 h = 1 h breaks
    assert days[0].break_hours == 1.0
    assert days[0].available_hours == 7.0  # 8 - 1 break


def test_weekend_zero_hours(settings_8h):
    saturday = date(2026, 10, 24)  # Saturday
    assert saturday.weekday() == 5
    calc = AvailabilityCalculator(settings_8h, saturday, saturday)
    days = calc.compute()
    assert days[0].available_hours == 0.0


def test_five_day_week_total(settings_8h):
    """Mon–Fri with 0 % buffer and 1 h breaks/day = 5 × 7 = 35 h."""
    monday = _monday()
    friday = monday + timedelta(days=4)
    calc = AvailabilityCalculator(settings_8h, monday, friday)
    assert calc.total_usable_hours() == pytest.approx(35.0)


def test_buffer_reduces_availability(settings_with_buffer):
    monday = _monday()
    calc = AvailabilityCalculator(settings_with_buffer, monday, monday)
    days = calc.compute()
    # Net = 7 h (after breaks), buffer = 10 % → 7 × 0.9 = 6.3
    assert days[0].available_hours == pytest.approx(6.3)


# ── Lost hours ────────────────────────────────────────────────────────────────

def test_lost_hours_today(settings_8h):
    monday = _monday()
    calc = AvailabilityCalculator(settings_8h, monday, monday, lost_hours_today=3.0)
    days = calc.compute()
    assert days[0].available_hours == pytest.approx(4.0)  # 7 - 3 = 4


def test_lost_hours_only_on_first_day(settings_8h):
    monday = _monday()
    tuesday = monday + timedelta(days=1)
    calc = AvailabilityCalculator(settings_8h, monday, tuesday, lost_hours_today=7.0)
    days = calc.compute()
    # Monday: max(0, 7 - 7) = 0
    assert days[0].available_hours == pytest.approx(0.0)
    # Tuesday: full 7 h
    assert days[1].available_hours == pytest.approx(7.0)


# ── Usable hours before deadline ──────────────────────────────────────────────

def test_usable_hours_before_deadline_exact_end(settings_8h):
    monday = _monday()
    # Deadline = end of Monday working day (17:00 UTC)
    deadline = datetime(2026, 10, 19, 17, 0, tzinfo=timezone.utc)
    calc = AvailabilityCalculator(settings_8h, monday, monday + timedelta(days=7))
    h = calc.usable_hours_before(deadline)
    assert h == pytest.approx(7.0)


def test_usable_hours_before_deadline_partial_day(settings_8h):
    monday = _monday()
    # Deadline = 13:00 on Monday (4 h into 09:00–17:00 window)
    deadline = datetime(2026, 10, 19, 13, 0, tzinfo=timezone.utc)
    calc = AvailabilityCalculator(settings_8h, monday, monday + timedelta(days=7))
    h = calc.usable_hours_before(deadline)
    # 4 / 8 fraction × 7.0 net available hours = 3.5
    assert h == pytest.approx(3.5)


def test_no_available_hours_past_deadline(settings_8h):
    monday = _monday()
    # Deadline before working day starts
    deadline = datetime(2026, 10, 19, 8, 0, tzinfo=timezone.utc)
    calc = AvailabilityCalculator(settings_8h, monday, monday + timedelta(days=7))
    h = calc.usable_hours_before(deadline)
    assert h == 0.0


# ── Override ───────────────────────────────────────────────────────────────────

def test_day_override(settings_8h):
    monday = _monday()
    calc = AvailabilityCalculator(
        settings_8h, monday, monday, overrides={monday: 2.0}
    )
    days = calc.compute()
    assert days[0].available_hours == pytest.approx(2.0)
    assert "Override" in days[0].notes[0]
