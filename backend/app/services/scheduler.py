"""
Portfolio Scheduler — deterministic greedy algorithm.

Strategy:
  1. Reserve fixed-commitment sessions.
  2. Schedule Priority-1 tasks first (earliest deadline wins tiebreak).
  3. Schedule remaining tasks in (priority ASC, deadline ASC) order.
  4. Respect dependencies: a task cannot start before all its deps are done.
  5. Respect earliest_start.
  6. Never overflow a day's available hours.
  7. Track unscheduled tasks with clear reasons.

This is a best-effort greedy scheduler.
A failure here is NOT proof of global infeasibility — the independent
FeasibilityService.validate_schedule() must make that determination.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlmodel import Session

from app.models.task import Task, TaskStatus, UserSettings
from app.schemas.plan import DailyPlan, PortfolioScheduleResult, WorkSession
from app.services.availability import AvailabilityCalculator, DayAvailability
from app.services.feasibility import FeasibilityService


class SchedulerService:
    """
    Greedy portfolio scheduler.

    Args:
        session:           DB session (for dependency lookups).
        settings:          UserSettings (working hours, buffer, timezone).
        tasks:             List of Task objects to schedule.
        now:               Reference 'now' (default: UTC now).
        days_ahead:        How many calendar days to schedule into.
        lost_hours_today:  Already-lost hours on day 0.
    """

    def __init__(
        self,
        session: Session,
        settings: UserSettings,
        tasks: List[Task],
        now: Optional[datetime] = None,
        days_ahead: int = 14,
        lost_hours_today: float = 0.0,
    ) -> None:
        self.session = session
        self.settings = settings
        self.tasks = tasks
        self.now = now or datetime.now(timezone.utc)
        self.days_ahead = days_ahead
        self.lost_hours_today = lost_hours_today

    # ── Public ────────────────────────────────────────────────────────────────

    def generate(self) -> PortfolioScheduleResult:
        today = self.now.date()
        end_date = today + timedelta(days=self.days_ahead - 1)

        # Build availability map: date → DayAvailability
        calc = AvailabilityCalculator(
            settings=self.settings,
            start_date=today,
            end_date=end_date,
            lost_hours_today=self.lost_hours_today,
        )
        availability: List[DayAvailability] = calc.compute()
        avail_map: Dict[date, DayAvailability] = {d.date: d for d in availability}

        # Mutable remaining capacity per day
        remaining_capacity: Dict[date, float] = {
            d.date: d.available_hours for d in availability
        }

        # Mutable remaining work per task
        task_remaining: Dict[str, float] = {
            t.id: t.remaining_hours
            for t in self.tasks
            if t.status not in (TaskStatus.DONE, TaskStatus.DEFERRED)
        }

        # Session ledger per day
        scheduled_sessions: Dict[date, List[WorkSession]] = defaultdict(list)

        scheduled_task_ids: List[str] = []
        unscheduled: List[dict] = []

        # Sort tasks: p1 first, then priority ASC, deadline ASC
        active_tasks = [
            t for t in self.tasks
            if t.status not in (TaskStatus.DONE, TaskStatus.DEFERRED)
        ]
        sorted_tasks = sorted(active_tasks, key=lambda t: (t.priority, t.deadline))

        for task in sorted_tasks:
            if task.remaining_hours <= 0:
                scheduled_task_ids.append(task.id)
                continue

            dep_finish_date = self._dependency_finish_date(task)
            result = self._schedule_task(
                task=task,
                remaining_capacity=remaining_capacity,
                scheduled_sessions=scheduled_sessions,
                avail_map=avail_map,
                dep_finish_date=dep_finish_date,
            )
            if result == "ok":
                scheduled_task_ids.append(task.id)
            else:
                unscheduled.append({
                    "task_id": task.id,
                    "title": task.title,
                    "priority": task.priority,
                    "deadline": task.deadline,
                    "reason": result,
                })

        # Build DailyPlan list
        plan: List[DailyPlan] = []
        for da in availability:
            sessions = scheduled_sessions.get(da.date, [])
            total_sched = sum(s.hours for s in sessions)
            plan.append(DailyPlan(
                date=da.date.isoformat(),
                sessions=sessions,
                total_scheduled_hours=round(total_sched, 2),
                available_hours=round(da.available_hours, 2),
                buffer_hours=round(da.gross_hours * self.settings.buffer_fraction, 2),
            ))

        # Validate
        feasibility_svc = FeasibilityService(self.session)
        schedule_result = PortfolioScheduleResult(
            plan=plan,
            scheduled_task_ids=scheduled_task_ids,
            unscheduled_tasks=unscheduled,
            feasible=len(unscheduled) == 0,
            validation_errors=[],
            explanation="",
        )
        validation_errors = feasibility_svc.validate_schedule(
            schedule_result, active_tasks, self.settings, self.now
        )
        schedule_result.validation_errors = validation_errors
        if validation_errors:
            schedule_result.feasible = False
            schedule_result.explanation = (
                f"Schedule generated but failed {len(validation_errors)} validation check(s). "
                "See validation_errors for details. "
                "Note: greedy scheduling failure does not imply no feasible schedule exists."
            )
        elif unscheduled:
            schedule_result.explanation = (
                f"{len(unscheduled)} task(s) could not be placed within the {self.days_ahead}-day window. "
                "Recovery plan required."
            )
        else:
            schedule_result.explanation = (
                f"All {len(scheduled_task_ids)} tasks scheduled successfully within {self.days_ahead} days."
            )

        return schedule_result

    # ── Internal ──────────────────────────────────────────────────────────────

    def _schedule_task(
        self,
        task: Task,
        remaining_capacity: Dict[date, float],
        scheduled_sessions: Dict[date, List[WorkSession]],
        avail_map: Dict[date, DayAvailability],
        dep_finish_date: Optional[date],
    ) -> str:
        """
        Greedily place work sessions for a task.
        Returns "ok" or a reason string explaining why scheduling failed.
        """
        deadline = task.deadline_dt().date()
        earliest = (
            task.earliest_start_dt().date()
            if task.earliest_start_dt()
            else self.now.date()
        )
        if dep_finish_date:
            earliest = max(earliest, dep_finish_date + timedelta(days=1))

        remaining = task.remaining_hours
        placed = 0.0

        for day, da in sorted(avail_map.items()):
            if day < earliest:
                continue
            if day > deadline:
                break
            cap = remaining_capacity.get(day, 0.0)
            if cap <= 0:
                continue

            # For non-splittable tasks: need to fit entire remaining in one session
            if not task.splittable and remaining > cap:
                continue

            chunk = min(remaining, cap)
            if chunk <= 0:
                continue

            # Build time string from day availability
            prev_used = da.available_hours - remaining_capacity[day]
            start_offset = timedelta(hours=prev_used)
            session_start = da.work_start + start_offset
            session_end = session_start + timedelta(hours=chunk)

            # Format HH:MM in UTC
            session_start_utc = session_start.astimezone(timezone.utc)
            session_end_utc = session_end.astimezone(timezone.utc)

            session = WorkSession(
                task_id=task.id,
                task_title=task.title,
                date=day.isoformat(),
                start_time=session_start_utc.strftime("%H:%M"),
                end_time=session_end_utc.strftime("%H:%M"),
                hours=round(chunk, 2),
            )
            scheduled_sessions[day].append(session)
            remaining_capacity[day] -= chunk
            placed += chunk
            remaining -= chunk

            if remaining <= 1e-9:
                return "ok"

        if remaining > 1e-9:
            if not task.splittable:
                return (
                    f"Non-splittable task needs {task.remaining_hours:.1f} h contiguous "
                    f"but no single day has enough capacity before deadline"
                )
            return (
                f"Insufficient time before deadline: "
                f"{remaining:.1f} h still unscheduled"
            )
        return "ok"

    def _dependency_finish_date(self, task: Task) -> Optional[date]:
        """
        Return the latest deadline date of any unfinished dependency.
        Completed dependencies are ignored.
        """
        latest: Optional[date] = None
        for dep_id in task.depends_on:
            dep = self.session.get(Task, dep_id)
            if dep and dep.status != TaskStatus.DONE:
                dep_date = dep.deadline_dt().date()
                if latest is None or dep_date > latest:
                    latest = dep_date
        return latest
