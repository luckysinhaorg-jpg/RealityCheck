"""Pydantic schemas for scheduling plans and feasibility analysis."""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class WorkSession(BaseModel):
    """A block of scheduled work on a task."""
    task_id: str
    task_title: str
    date: str           # YYYY-MM-DD
    start_time: str     # HH:MM UTC
    end_time: str       # HH:MM UTC
    hours: float


class DailyPlan(BaseModel):
    """Scheduled work for a single day."""
    date: str           # YYYY-MM-DD
    sessions: List[WorkSession]
    total_scheduled_hours: float
    available_hours: float
    buffer_hours: float


class FeasibilityResult(BaseModel):
    """
    Result of Priority-1 feasibility analysis.

    feasible=True means the task CAN finish by deadline given current settings.
    The intermediate calculation steps are included for transparency.
    """
    task_id: str
    task_title: str
    feasible: bool

    # Inputs / intermediate values — always populated
    deadline: str
    remaining_hours: float
    days_until_deadline: float
    usable_hours_before_deadline: float
    required_hours_per_day: float
    buffer_hours: float
    buffer_percent: float

    # Explanation
    explanation: str
    assumptions: List[str]

    # If infeasible
    shortfall_hours: Optional[float] = None
    blocking_tasks: List[str] = Field(default_factory=list)


class PortfolioScheduleResult(BaseModel):
    """Result of the full portfolio scheduling run."""
    plan: List[DailyPlan]
    scheduled_task_ids: List[str]
    unscheduled_tasks: List[dict]   # [{task_id, title, reason}]
    feasible: bool
    validation_errors: List[str]
    explanation: str


class ScheduleRequest(BaseModel):
    """Request body for generate_daily_plan."""
    days_ahead: int = Field(default=14, ge=1, le=90)
    lost_hours_today: float = Field(default=0.0, ge=0)
