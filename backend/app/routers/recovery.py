"""Recovery router — /api/recovery"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.dependencies import get_or_create_settings, get_session
from app.models.task import UserSettings
from app.schemas.recovery import (
    RecoveryProposalResponse,
    ResolveProposalRequest,
    ResolveProposalResponse,
)
from app.services.feasibility import FeasibilityService
from app.services.recovery import RecoveryService
from app.services.task_service import TaskNotFoundError, TaskService

router = APIRouter()


@router.post("/generate/{task_id}", response_model=RecoveryProposalResponse)
def generate_recovery_plan(
    task_id: str,
    lost_hours_today: float = Query(0.0, ge=0),
    session: Session = Depends(get_session),
    user_settings: UserSettings = Depends(get_or_create_settings),
):
    """Generate a recovery plan for the given task and persist it for approval."""
    try:
        task = TaskService(session).get_task(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task {task_id!r} not found")

    now = datetime.now(timezone.utc)
    feasibility = FeasibilityService(session).analyse_p1_feasibility(
        task, user_settings, now=now, lost_hours_today=lost_hours_today
    )

    svc = RecoveryService(session)
    return svc.generate_recovery_plan(feasibility, user_settings, now=now)


@router.post("/resolve", response_model=ResolveProposalResponse)
def resolve_recovery_proposal(
    req: ResolveProposalRequest,
    session: Session = Depends(get_session),
):
    """
    Accept or reject a recovery proposal.

    - **reject**: changes absolutely nothing (tested by scenario 9).
    - **accept**: applies the chosen option. Requires option_index.
    """
    svc = RecoveryService(session)
    try:
        return svc.resolve_proposal(
            proposal_id=req.proposal_id,
            action=req.action,
            option_index=req.option_index,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/complete/{task_id}")
def record_task_completion(
    task_id: str,
    actual_hours: float = Query(..., gt=0),
    session: Session = Depends(get_session),
):
    """Record a task completion with actual duration and update duration estimates."""
    from app.services.estimator import EstimatorService
    try:
        return EstimatorService(session).record_completion(task_id, actual_hours)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
