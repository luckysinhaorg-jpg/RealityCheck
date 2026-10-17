"""
Task CRUD service with duplicate prevention and dependency validation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlmodel import Session, select

from app.models.task import Task, TaskStatus
from app.schemas.task import TaskCreate, TaskUpdate


class DuplicateTaskError(ValueError):
    pass


class TaskNotFoundError(KeyError):
    pass


class InvalidDependencyError(ValueError):
    pass


class TaskService:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ── Create ────────────────────────────────────────────────────────────────

    def create_task(self, data: TaskCreate) -> Task:
        """Create a task. Raises DuplicateTaskError if title+deadline matches existing."""
        # Duplicate check: same title AND same deadline
        existing = self.session.exec(
            select(Task).where(
                Task.title == data.title,
                Task.deadline == data.deadline,
                Task.status != TaskStatus.DONE,
            )
        ).first()
        if existing:
            raise DuplicateTaskError(
                f"Task '{data.title}' with deadline {data.deadline} already exists (id={existing.id}). "
                "Use update_task to modify it."
            )

        # Validate dependencies exist
        self._validate_deps(data.depends_on)

        task = Task(
            title=data.title,
            description=data.description,
            category=data.category,
            priority=data.priority,
            deadline=data.deadline,
            estimated_hours=data.estimated_hours,
            remaining_hours=data.estimated_hours,  # starts equal to estimate
            status=data.status,
            splittable=data.splittable,
            earliest_start=data.earliest_start,
            fixed_start=data.fixed_start,
            fixed_end=data.fixed_end,
            confidence=data.confidence,
        )
        task.depends_on = data.depends_on
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_task(self, task_id: str) -> Task:
        task = self.session.get(Task, task_id)
        if task is None:
            raise TaskNotFoundError(f"Task {task_id!r} not found")
        return task

    def list_tasks(
        self,
        status: Optional[str] = None,
        priority: Optional[int] = None,
        category: Optional[str] = None,
    ) -> List[Task]:
        stmt = select(Task)
        if status:
            stmt = stmt.where(Task.status == status)
        if priority is not None:
            stmt = stmt.where(Task.priority == priority)
        if category:
            stmt = stmt.where(Task.category == category)
        stmt = stmt.order_by(Task.priority, Task.deadline)
        return list(self.session.exec(stmt).all())

    def get_priority1_task(self) -> Optional[Task]:
        """Return the earliest-deadline priority-1 task that is not done."""
        stmt = (
            select(Task)
            .where(Task.priority == 1, Task.status != TaskStatus.DONE)
            .order_by(Task.deadline)
        )
        return self.session.exec(stmt).first()

    # ── Update ────────────────────────────────────────────────────────────────

    def update_task(self, task_id: str, data: TaskUpdate) -> Task:
        task = self.get_task(task_id)

        update_data = data.model_dump(exclude_unset=True)

        # Handle depends_on separately (JSON field)
        if "depends_on" in update_data:
            new_deps = update_data.pop("depends_on")
            self._validate_deps(new_deps, exclude_id=task_id)
            task.depends_on = new_deps

        for field, value in update_data.items():
            if hasattr(task, field):
                setattr(task, field, value)

        # Auto-recalculate remaining if estimated changed and actual not also changed
        if "estimated_hours" in update_data and "remaining_hours" not in update_data:
            task.remaining_hours = max(
                0.0,
                task.estimated_hours - task.actual_hours,
            )

        task.touch()
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    # ── Delete ────────────────────────────────────────────────────────────────

    def delete_task(self, task_id: str) -> None:
        task = self.get_task(task_id)
        self.session.delete(task)
        self.session.commit()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _validate_deps(self, dep_ids: List[str], exclude_id: Optional[str] = None) -> None:
        for dep_id in dep_ids:
            if exclude_id and dep_id == exclude_id:
                raise InvalidDependencyError(f"Task cannot depend on itself: {dep_id}")
            existing = self.session.get(Task, dep_id)
            if existing is None:
                raise InvalidDependencyError(
                    f"Dependency task {dep_id!r} not found"
                )
