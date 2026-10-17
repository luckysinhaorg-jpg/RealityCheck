"""
Duration estimator.

Tracks actual vs estimated durations per category.
Adjustment applied only after ≥ 3 completed tasks in that category.
Manual overrides are always honoured and preserved.
"""
from __future__ import annotations

from typing import Optional
from sqlmodel import Session, select

from app.models.task import CompletionLog, Task, TaskStatus
from app.schemas.task import TaskUpdate
from app.services.task_service import TaskService


class EstimatorService:
    MIN_SAMPLES = 3  # Must have this many completions before adjusting

    def __init__(self, session: Session) -> None:
        self.session = session

    def record_completion(
        self,
        task_id: str,
        actual_hours: float,
    ) -> dict:
        """
        Record a task completion with actual duration.

        - Logs to CompletionLog.
        - Marks task as DONE with actual_hours set.
        - Calculates category ratio (if ≥ MIN_SAMPLES).
        - Returns summary including ratio and explanation.
        """
        task_svc = TaskService(self.session)
        task = task_svc.get_task(task_id)

        # Log the completion
        log = CompletionLog(
            task_id=task.id,
            category=task.category,
            estimated_hours=task.estimated_hours,
            actual_hours=actual_hours,
        )
        self.session.add(log)

        # Update task
        task_svc.update_task(
            task_id,
            TaskUpdate(
                actual_hours=actual_hours,
                remaining_hours=0.0,
                status=TaskStatus.DONE,
            ),
        )

        # Get category ratio
        ratio_info = self.category_ratio(task.category)

        return {
            "task_id": task_id,
            "task_title": task.title,
            "category": task.category,
            "estimated_hours": task.estimated_hours,
            "actual_hours": actual_hours,
            "ratio": ratio_info["ratio"],
            "samples": ratio_info["samples"],
            "adjustment_active": ratio_info["adjustment_active"],
            "explanation": ratio_info["explanation"],
        }

    def category_ratio(self, category: str) -> dict:
        """
        Compute actual/estimated ratio for a category.
        Returns ratio=1.0 and adjustment_active=False if < MIN_SAMPLES.
        """
        logs = list(self.session.exec(
            select(CompletionLog).where(CompletionLog.category == category)
        ).all())

        if len(logs) < self.MIN_SAMPLES:
            return {
                "category": category,
                "samples": len(logs),
                "ratio": 1.0,
                "adjustment_active": False,
                "explanation": (
                    f"Only {len(logs)} completion(s) in '{category}'. "
                    f"Need at least {self.MIN_SAMPLES} before applying adjustment. "
                    "Estimates unchanged."
                ),
            }

        total_est = sum(l.estimated_hours for l in logs)
        total_act = sum(l.actual_hours for l in logs)
        ratio = total_act / total_est if total_est > 0 else 1.0

        return {
            "category": category,
            "samples": len(logs),
            "ratio": round(ratio, 3),
            "adjustment_active": True,
            "explanation": (
                f"Based on {len(logs)} completions in '{category}': "
                f"avg actual/estimated = {ratio:.2f}x. "
                + ("Tasks in this category tend to run over." if ratio > 1.05 else
                   "Tasks in this category tend to finish early." if ratio < 0.95 else
                   "Estimates in this category are accurate.")
            ),
        }

    def suggest_adjusted_estimate(self, task: Task) -> float:
        """
        Return adjusted estimate = estimated_hours × category_ratio.
        Only applied if adjustment_active (≥ MIN_SAMPLES).
        """
        info = self.category_ratio(task.category)
        if not info["adjustment_active"]:
            return task.estimated_hours
        return round(task.estimated_hours * info["ratio"], 2)
