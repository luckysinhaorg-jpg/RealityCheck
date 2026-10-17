"""
Tests for TaskService CRUD operations and model persistence.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

from app.models.task import Task, TaskStatus, UserSettings
from app.schemas.task import TaskCreate, TaskUpdate
from app.services.task_service import (
    TaskService,
    DuplicateTaskError,
    TaskNotFoundError,
    InvalidDependencyError,
)


def _deadline(days: int = 7) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def test_create_task_basic(session):
    svc = TaskService(session)
    task = svc.create_task(TaskCreate(
        title="Write Report",
        deadline=_deadline(),
        estimated_hours=5,
    ))
    assert task.id
    assert task.remaining_hours == 5.0
    assert task.status == TaskStatus.TODO


def test_create_sets_remaining_equal_to_estimated(session):
    svc = TaskService(session)
    task = svc.create_task(TaskCreate(
        title="Coding Task",
        deadline=_deadline(),
        estimated_hours=12,
    ))
    assert task.remaining_hours == task.estimated_hours


def test_duplicate_prevention(session):
    svc = TaskService(session)
    dl = _deadline()
    svc.create_task(TaskCreate(title="Same Task", deadline=dl, estimated_hours=4))
    with pytest.raises(DuplicateTaskError, match="already exists"):
        svc.create_task(TaskCreate(title="Same Task", deadline=dl, estimated_hours=4))


def test_different_deadline_not_duplicate(session):
    svc = TaskService(session)
    svc.create_task(TaskCreate(title="Task A", deadline=_deadline(7), estimated_hours=4))
    svc.create_task(TaskCreate(title="Task A", deadline=_deadline(14), estimated_hours=4))


def test_update_task_fields(session):
    svc = TaskService(session)
    task = svc.create_task(TaskCreate(title="X", deadline=_deadline(), estimated_hours=3))
    updated = svc.update_task(task.id, TaskUpdate(priority=1, category="research"))
    assert updated.priority == 1
    assert updated.category == "research"


def test_update_estimated_recalculates_remaining(session):
    svc = TaskService(session)
    task = svc.create_task(TaskCreate(title="Y", deadline=_deadline(), estimated_hours=4))
    # Simulate 2 h logged
    svc.update_task(task.id, TaskUpdate(actual_hours=2.0))
    updated = svc.update_task(task.id, TaskUpdate(estimated_hours=8.0))
    # remaining = 8 - 2 = 6
    assert updated.remaining_hours == pytest.approx(6.0)


def test_get_task_not_found(session):
    svc = TaskService(session)
    with pytest.raises(TaskNotFoundError):
        svc.get_task("non-existent-id")


def test_list_tasks_filter_by_status(session):
    svc = TaskService(session)
    svc.create_task(TaskCreate(title="Todo", deadline=_deadline(), estimated_hours=2))
    done_task = svc.create_task(TaskCreate(title="Done", deadline=_deadline(), estimated_hours=2))
    svc.update_task(done_task.id, TaskUpdate(status=TaskStatus.DONE))

    todos = svc.list_tasks(status=TaskStatus.TODO)
    assert all(t.status == TaskStatus.TODO for t in todos)
    assert all(t.title != "Done" for t in todos)


def test_depends_on_serialization(session):
    svc = TaskService(session)
    dep = svc.create_task(TaskCreate(title="Dep", deadline=_deadline(), estimated_hours=2))
    task = svc.create_task(TaskCreate(
        title="Dependent",
        deadline=_deadline(10),
        estimated_hours=3,
        depends_on=[dep.id],
    ))
    assert dep.id in task.depends_on


def test_invalid_dependency_raises(session):
    svc = TaskService(session)
    with pytest.raises(InvalidDependencyError, match="not found"):
        svc.create_task(TaskCreate(
            title="Bad",
            deadline=_deadline(),
            estimated_hours=2,
            depends_on=["fake-id-xyz"],
        ))


def test_self_dependency_raises(session):
    svc = TaskService(session)
    task = svc.create_task(TaskCreate(title="Self", deadline=_deadline(), estimated_hours=2))
    with pytest.raises(InvalidDependencyError, match="itself"):
        svc.update_task(task.id, TaskUpdate(depends_on=[task.id]))


def test_timezone_aware_deadline_required(session):
    svc = TaskService(session)
    with pytest.raises(Exception):
        svc.create_task(TaskCreate(
            title="Naive",
            deadline="2026-11-01T12:00:00",  # no timezone
            estimated_hours=4,
        ))


def test_persistence_across_reload(session, engine):
    """Task written in one session is readable in a new session."""
    from sqlmodel import Session
    svc = TaskService(session)
    task = svc.create_task(TaskCreate(title="Persist Me", deadline=_deadline(), estimated_hours=6))
    task_id = task.id

    # Open a fresh session
    with Session(engine) as s2:
        svc2 = TaskService(s2)
        reloaded = svc2.get_task(task_id)
        assert reloaded.title == "Persist Me"
        assert reloaded.estimated_hours == 6.0
