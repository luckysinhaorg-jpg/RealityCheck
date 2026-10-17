"""Plans router — /api/plans"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.dependencies import get_or_create_settings, get_session
from app.models.task import Task, UserSettings
from app.schemas.plan import FeasibilityResult, PortfolioScheduleResult, ScheduleRequest
from app.services.feasibility import FeasibilityService
from app.services.scheduler import SchedulerService
from app.services.task_service import TaskNotFoundError, TaskService

router = APIRouter()


@router.get("/feasibility/{task_id}", response_model=FeasibilityResult)
def get_feasibility(
    task_id: str,
    lost_hours_today: float = Query(0.0, ge=0, description="Hours already lost today"),
    session: Session = Depends(get_session),
    user_settings: UserSettings = Depends(get_or_create_settings),
):
    """Analyse whether the given task can finish by its deadline."""
    try:
        task = TaskService(session).get_task(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task {task_id!r} not found")

    svc = FeasibilityService(session)
    return svc.analyse_p1_feasibility(
        task, user_settings,
        now=datetime.now(timezone.utc),
        lost_hours_today=lost_hours_today,
    )


@router.post("/generate", response_model=PortfolioScheduleResult)
def generate_daily_plan(
    req: ScheduleRequest,
    session: Session = Depends(get_session),
    user_settings: UserSettings = Depends(get_or_create_settings),
):
    """Generate a daily plan for all active tasks."""
    from sqlmodel import select
    tasks = list(session.exec(select(Task)).all())
    sched = SchedulerService(
        session=session,
        settings=user_settings,
        tasks=tasks,
        now=datetime.now(timezone.utc),
        days_ahead=req.days_ahead,
        lost_hours_today=req.lost_hours_today,
    )
    return sched.generate()
