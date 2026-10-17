"""
Availability calculator.

Given user settings, a date range, and optional lost hours today, compute
the usable working hours for each day. This is the ONLY source of truth
for available time — never equate calendar time with usable hours.

All datetime arithmetic uses Python stdlib only (zoneinfo + datetime).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from app.models.task import UserSettings


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class DayAvailability:
    date: date
    available_hours: float          # net usable hours after breaks
    gross_hours: float              # raw window length
    break_hours: float              # time lost to breaks
    work_start: datetime            # timezone-aware
    work_end: datetime              # timezone-aware
    notes: List[str] = field(default_factory=list)


# ── Calculator ────────────────────────────────────────────────────────────────

class AvailabilityCalculator:
    """
    Deterministic, pure-Python availability calculator.

    Args:
        settings:       UserSettings ORM object.
        start_date:     First day to calculate (inclusive).
        end_date:       Last day to calculate (inclusive).
        lost_hours_today: Hours already lost on start_date (reduces availability).
        overrides:      Map of date → override hours (replaces computed value).
    """

    def __init__(
        self,
        settings: UserSettings,
        start_date: date,
        end_date: date,
        lost_hours_today: float = 0.0,
        overrides: Optional[Dict[date, float]] = None,
    ) -> None:
        self.settings = settings
        self.start_date = start_date
        self.end_date = end_date
        self.lost_hours_today = lost_hours_today
        self.overrides = overrides or {}
        self._tz = ZoneInfo(settings.timezone)

    # ── Public API ────────────────────────────────────────────────────────────

    def compute(self) -> List[DayAvailability]:
        """Return one DayAvailability per day in [start_date, end_date]."""
        results: List[DayAvailability] = []
        day = self.start_date
        while day <= self.end_date:
            avail = self._compute_day(day)
            results.append(avail)
            day += timedelta(days=1)
        return results

    def total_usable_hours(self) -> float:
        """Sum of available hours across the entire range."""
        return sum(d.available_hours for d in self.compute())

    def usable_hours_before(self, deadline: datetime) -> float:
        """
        Sum available hours up to but not crossing deadline.
        Deadline must be timezone-aware.
        """
        deadline_utc = deadline.astimezone(timezone.utc)
        total = 0.0
        for da in self.compute():
            # Convert day work window to UTC for comparison
            day_end_utc = da.work_end.astimezone(timezone.utc)
            day_start_utc = da.work_start.astimezone(timezone.utc)

            if day_end_utc <= deadline_utc:
                # Full day available
                total += da.available_hours
            elif day_start_utc < deadline_utc < day_end_utc:
                # Partial day: proportion of the available hours
                full_window = (day_end_utc - day_start_utc).total_seconds() / 3600
                partial_window = (deadline_utc - day_start_utc).total_seconds() / 3600
                if full_window > 0:
                    fraction = partial_window / full_window
                    # Scale net available hours by the same fraction
                    total += da.available_hours * fraction
                break
            else:
                # Deadline is before this day starts — stop
                break
        return max(0.0, total)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _compute_day(self, day: date) -> DayAvailability:
        # Check overrides first
        if day in self.overrides:
            override_h = max(0.0, self.overrides[day])
            ws = self._day_start_dt(day)
            we = ws + timedelta(hours=override_h)
            return DayAvailability(
                date=day,
                available_hours=override_h,
                gross_hours=override_h,
                break_hours=0.0,
                work_start=ws,
                work_end=we,
                notes=[f"Override: {override_h:.1f} h"],
            )

        # Weekday index: Monday=0 … Sunday=6
        weekday = day.weekday()
        daily_config = self.settings.daily_hours
        gross_hours = float(daily_config.get(str(weekday), 0.0))

        if gross_hours <= 0:
            ws = self._day_start_dt(day)
            return DayAvailability(
                date=day,
                available_hours=0.0,
                gross_hours=0.0,
                break_hours=0.0,
                work_start=ws,
                work_end=ws,
                notes=["Non-working day"],
            )

        # Work window from settings
        ws = self._day_start_dt(day)
        we = self._day_end_dt(day)

        # Cap gross hours to actual window width
        window_hours = (we - ws).total_seconds() / 3600
        gross_hours = min(gross_hours, window_hours)

        # Calculate break time
        break_hours = self._break_hours(gross_hours)
        net_hours = max(0.0, gross_hours - break_hours)

        # Apply lost hours (only for start_date)
        notes: List[str] = []
        if day == self.start_date and self.lost_hours_today > 0:
            reduction = min(self.lost_hours_today, net_hours)
            net_hours = max(0.0, net_hours - reduction)
            notes.append(f"Lost {reduction:.1f} h today")

        # Apply buffer
        buffered = net_hours * (1.0 - self.settings.buffer_fraction)

        return DayAvailability(
            date=day,
            available_hours=round(buffered, 4),
            gross_hours=round(gross_hours, 4),
            break_hours=round(break_hours, 4),
            work_start=ws,
            work_end=we,
            notes=notes,
        )

    def _break_hours(self, gross_hours: float) -> float:
        """
        Compute total break time.
        break_duration_minutes every break_after_hours of work.
        Returns 0 if break_after_hours is zero or negative.
        """
        if self.settings.break_after_hours <= 0 or self.settings.break_duration_minutes <= 0:
            return 0.0
        if gross_hours <= 0:
            return 0.0
        n_breaks = math.floor(gross_hours / self.settings.break_after_hours)
        return n_breaks * (self.settings.break_duration_minutes / 60)

    def _day_start_dt(self, day: date) -> datetime:
        h, m = map(int, self.settings.work_start.split(":"))
        return datetime(day.year, day.month, day.day, h, m, tzinfo=self._tz)

    def _day_end_dt(self, day: date) -> datetime:
        h, m = map(int, self.settings.work_end.split(":"))
        return datetime(day.year, day.month, day.day, h, m, tzinfo=self._tz)
