"""
Tasks REST router — /api/tasks
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.dependencies import get_session
from app.schemas.task import TaskCreate, TaskListResponse, TaskRead, TaskUpdate
from app.services.task_service import (
    DuplicateTaskError,
    InvalidDependencyError,
    TaskNotFoundError,
    TaskService,
)

router = APIRouter()


def _task_svc(session: Session = Depends(get_session)) -> TaskService:
    return TaskService(session)


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(data: TaskCreate, svc: TaskService = Depends(_task_svc)):
    try:
        task = svc.create_task(data)
    except DuplicateTaskError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except InvalidDependencyError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _to_read(task)


@router.get("", response_model=TaskListResponse)
def list_tasks(
    status: Optional[str] = Query(None),
    priority: Optional[int] = Query(None, ge=1, le=5),
    category: Optional[str] = Query(None),
    svc: TaskService = Depends(_task_svc),
):
    tasks = svc.list_tasks(status=status, priority=priority, category=category)
    return TaskListResponse(tasks=[_to_read(t) for t in tasks], total=len(tasks))


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: str, svc: TaskService = Depends(_task_svc)):
    try:
        return _to_read(svc.get_task(task_id))
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task {task_id!r} not found")


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(
    task_id: str, data: TaskUpdate, svc: TaskService = Depends(_task_svc)
):
    try:
        return _to_read(svc.update_task(task_id, data))
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task {task_id!r} not found")
    except InvalidDependencyError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: str, svc: TaskService = Depends(_task_svc)):
    try:
        svc.delete_task(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task {task_id!r} not found")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_read(task) -> TaskRead:
    return TaskRead(
        id=task.id,
        title=task.title,
        description=task.description,
        category=task.category,
        priority=task.priority,
        deadline=task.deadline,
        estimated_hours=task.estimated_hours,
        actual_hours=task.actual_hours,
        remaining_hours=task.remaining_hours,
        status=task.status,
        depends_on=task.depends_on,
        splittable=task.splittable,
        earliest_start=task.earliest_start,
        fixed_start=task.fixed_start,
        fixed_end=task.fixed_end,
        confidence=task.confidence,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )
