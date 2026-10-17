"""
Shared pytest fixtures for RealityCheck backend tests.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from sqlmodel import Session, SQLModel

from app.database import create_test_engine, init_db
from app.models.task import Task, TaskStatus, UserSettings


# ── Database fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def engine():
    """Fresh in-memory SQLite engine per test."""
    eng = create_test_engine()
    init_db(eng)
    yield eng
    eng.dispose()


@pytest.fixture(scope="function")
def session(engine):
    """DB session backed by the in-memory engine."""
    with Session(engine) as s:
        yield s


# ── Default settings fixture ───────────────────────────────────────────────────

@pytest.fixture
def default_settings(session) -> UserSettings:
    """8 h/day Mon–Fri, 4 h Sat, 0 h Sun; 10 % buffer; UTC."""
    s = UserSettings(
        id=1,
        work_start="09:00",
        work_end="17:00",
        break_duration_minutes=15,
        break_after_hours=2.0,
        buffer_fraction=0.10,
        timezone="UTC",
    )
    s.daily_hours = {"0": 8, "1": 8, "2": 8, "3": 8, "4": 8, "5": 4, "6": 0}
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


# ── Task factory helpers ───────────────────────────────────────────────────────

def make_task(
    session,
    title: str = "Test Task",
    priority: int = 3,
    estimated_hours: float = 4.0,
    days_until_deadline: int = 7,
    status: TaskStatus = TaskStatus.TODO,
    category: str = "general",
    splittable: bool = True,
    depends_on: list | None = None,
    now: datetime | None = None,
) -> Task:
    ref = now or datetime.now(timezone.utc)
    deadline = (ref + timedelta(days=days_until_deadline)).isoformat()
    task = Task(
        title=title,
        priority=priority,
        deadline=deadline,
        estimated_hours=estimated_hours,
        remaining_hours=estimated_hours,
        status=status,
        category=category,
        splittable=splittable,
    )
    if depends_on:
        task.depends_on = depends_on
    session.add(task)
    session.commit()
    session.refresh(task)
    return task
