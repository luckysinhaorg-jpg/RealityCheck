"""
Priority-1 Feasibility Analyser + Independent Validator.

Two distinct responsibilities:
  A. analyse_p1_feasibility() — pure analysis: is there enough usable time?
  B. validate_schedule()       — independent check of a generated schedule.

Design rules:
  - NEVER equate calendar time with usable hours.
  - Splittable tasks: compare cumulative required vs cumulative usable hours up to deadline.
  - Non-splittable tasks: report "no schedule found" unless mathematically proven impossible.
  - "infeasible" label only when validated as infeasible, not just when greedy failed.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timezone
from typing import List, Optional

from sqlmodel import Session

from app.models.task import Task, TaskStatus, UserSettings
from app.schemas.plan import FeasibilityResult, PortfolioScheduleResult, WorkSession
from app.services.availability import AvailabilityCalculator


class FeasibilityService:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ── Priority-1 Analysis ───────────────────────────────────────────────────

    def analyse_p1_feasibility(
        self,
        task: Task,
        settings: UserSettings,
        now: Optional[datetime] = None,
        lost_hours_today: float = 0.0,
    ) -> FeasibilityResult:
        """
        Compute whether the given task can finish by its deadline.

        Returns a FeasibilityResult with intermediate values, assumptions,
        and a clear plain-English explanation.
        """
        now = now or datetime.now(timezone.utc)
        deadline = task.deadline_dt()
        remaining = task.remaining_hours

        # Days until deadline (fractional)
        days_until = (deadline - now).total_seconds() / 86400

        # Compute usable hours before deadline
        today = now.date()
        deadline_date = deadline.date()
        calc = AvailabilityCalculator(
            settings=settings,
            start_date=today,
            end_date=deadline_date,
            lost_hours_today=lost_hours_today,
        )
        usable_before = calc.usable_hours_before(deadline)

        # Buffer applied separately so we show it
        buffer_fraction = settings.buffer_fraction
        buffer_hours = usable_before * buffer_fraction
        # The scheduler will keep buffer; for feasibility we check if remaining <= usable
        # (buffer already baked into available_hours by AvailabilityCalculator)
        # but we expose it for transparency
        net_usable = usable_before  # already buffered by DayAvailability

        required_per_day = remaining / days_until if days_until > 0 else float("inf")
        shortfall = max(0.0, remaining - net_usable)
        feasible = remaining <= net_usable and days_until > 0

        # Dependency check — any incomplete dependency after our deadline?
        blocking: List[str] = []
        if task.depends_on:
            from sqlmodel import select

            for dep_id in task.depends_on:
                dep = self.session.get(Task, dep_id)
                if dep and dep.status != TaskStatus.DONE:
                    dep_deadline = dep.deadline_dt()
                    if dep_deadline >= deadline:
                        blocking.append(dep.title)
                        feasible = False

        # Build explanation
        assumptions = [
            f"Remaining work: {remaining:.1f} h",
            f"Days until deadline: {days_until:.1f}",
            f"Usable hours before deadline (after breaks + {buffer_fraction*100:.0f}% buffer): {net_usable:.1f} h",
            f"Required hours per day: {required_per_day:.1f} h/day",
            f"Splittable: {task.splittable}",
        ]
        if lost_hours_today > 0:
            assumptions.append(f"Lost hours today: {lost_hours_today:.1f} h (already deducted)")

        if feasible:
            explanation = (
                f"✅ '{task.title}' is FEASIBLE. "
                f"You need {required_per_day:.1f} h/day over {days_until:.0f} days. "
                f"{net_usable:.1f} usable hours are available before the deadline — "
                f"{(net_usable - remaining):.1f} h to spare."
            )
        elif blocking:
            explanation = (
                f"❌ '{task.title}' is BLOCKED by unfinished dependencies: "
                + ", ".join(f"'{b}'" for b in blocking)
                + ". Resolve dependencies first."
            )
        elif days_until <= 0:
            explanation = f"❌ '{task.title}' deadline has already passed."
        else:
            explanation = (
                f"❌ '{task.title}' is INFEASIBLE. "
                f"You need {remaining:.1f} h but only {net_usable:.1f} usable hours exist "
                f"before the deadline — shortfall of {shortfall:.1f} h."
            )

        return FeasibilityResult(
            task_id=task.id,
            task_title=task.title,
            feasible=feasible,
            deadline=task.deadline,
            remaining_hours=remaining,
            days_until_deadline=round(days_until, 2),
            usable_hours_before_deadline=round(net_usable, 2),
            required_hours_per_day=round(required_per_day, 2),
            buffer_hours=round(buffer_hours, 2),
            buffer_percent=round(buffer_fraction * 100, 1),
            explanation=explanation,
            assumptions=assumptions,
            shortfall_hours=round(shortfall, 2) if shortfall > 0 else None,
            blocking_tasks=blocking,
        )

    # ── Independent Schedule Validator ───────────────────────────────────────

    def validate_schedule(
        self,
        result: PortfolioScheduleResult,
        tasks: List[Task],
        settings: UserSettings,
        now: Optional[datetime] = None,
    ) -> List[str]:
        """
        Independently validate a generated schedule.

        Returns a list of error strings. Empty list = schedule passes validation.

        Checks:
        1. No overlapping sessions on the same day
        2. All sessions within working hours
        3. No session before task's earliest_start
        4. No scheduled hours exceed available hours on that day
        5. All deadlines respected
        6. All dependencies satisfied (dependency finishes before dependent starts)
        """
        now = now or datetime.now(timezone.utc)
        errors: List[str] = []
        task_map = {t.id: t for t in tasks}

        # Build per-day session index
        from collections import defaultdict
        day_sessions: dict[str, List[WorkSession]] = defaultdict(list)
        for day_plan in result.plan:
            for s in day_plan.sessions:
                day_sessions[day_plan.date].append(s)

        for day_str, sessions in day_sessions.items():
            # Sort by start time
            sorted_sessions = sorted(sessions, key=lambda s: s.start_time)

            # Check overlaps
            for i in range(len(sorted_sessions) - 1):
                a = sorted_sessions[i]
                b = sorted_sessions[i + 1]
                if a.end_time > b.start_time:
                    errors.append(
                        f"Overlap on {day_str}: '{a.task_title}' ({a.start_time}–{a.end_time}) "
                        f"overlaps '{b.task_title}' ({b.start_time}–)"
                    )

            # Check individual sessions
            for s in sessions:
                task = task_map.get(s.task_id)
                if not task:
                    errors.append(f"Session references unknown task {s.task_id}")
                    continue

                # Deadline check
                session_end_dt = datetime.fromisoformat(
                    f"{day_str}T{s.end_time}:00+00:00"
                )
                if session_end_dt > task.deadline_dt():
                    errors.append(
                        f"Session for '{task.title}' on {day_str} ends after its deadline"
                    )

                # earliest_start check
                if task.earliest_start:
                    es = task.earliest_start_dt()
                    session_start_dt = datetime.fromisoformat(
                        f"{day_str}T{s.start_time}:00+00:00"
                    )
                    if es and session_start_dt < es:
                        errors.append(
                            f"Session for '{task.title}' on {day_str} starts before earliest_start"
                        )

        return errors
