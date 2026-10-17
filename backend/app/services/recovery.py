"""
Recovery planner.

Generates 2–3 concrete recovery options when a plan is infeasible.
Persists the proposal and requires explicit accept/reject — never applies silently.

Options generated:
  1. Defer lower-priority tasks (free up time for P1)
  2. Extend daily working hours
  3. Negotiate the deadline (if P1 hours still exceed max available)
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlmodel import Session, select

from app.models.task import RecoveryProposal, RecoveryProposalStatus, Task, TaskStatus, UserSettings
from app.schemas.recovery import (
    AffectedTask,
    RecoveryOption,
    RecoveryProposalResponse,
    ResolveProposalResponse,
)
from app.schemas.plan import FeasibilityResult
from app.services.availability import AvailabilityCalculator
from app.services.task_service import TaskService, TaskNotFoundError


class RecoveryService:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ── Generate ──────────────────────────────────────────────────────────────

    def generate_recovery_plan(
        self,
        feasibility: FeasibilityResult,
        settings: UserSettings,
        now: Optional[datetime] = None,
    ) -> RecoveryProposalResponse:
        """
        Given a failed feasibility result, generate 2–3 recovery options,
        persist the proposal, and return the proposal with its ID.
        """
        now = now or datetime.now(timezone.utc)

        shortfall = feasibility.shortfall_hours or 0.0
        options: List[RecoveryOption] = []

        # ── Option 1: Defer lower-priority tasks ──────────────────────────────
        lower_prio_tasks = self._get_lower_priority_tasks(feasibility.task_id)
        freeable_hours = sum(t.remaining_hours for t in lower_prio_tasks)

        if freeable_hours >= shortfall and lower_prio_tasks:
            tasks_to_defer = self._select_tasks_to_defer(lower_prio_tasks, shortfall)
            affected = [
                AffectedTask(
                    task_id=t.id,
                    title=t.title,
                    original_deadline=t.deadline,
                    action="defer",
                )
                for t in tasks_to_defer
            ]
            options.append(RecoveryOption(
                option_index=0,
                label="Defer lower-priority tasks",
                description=(
                    f"Move {len(tasks_to_defer)} lower-priority task(s) beyond the deadline of "
                    f"'{feasibility.task_title}' to free {sum(t.remaining_hours for t in tasks_to_defer):.1f} h."
                ),
                trade_offs=(
                    "Lower-priority work is delayed. Useful if those tasks have flexible deadlines."
                ),
                affected_tasks=affected,
                additional_hours_required=0.0,
                feasible_after_recovery=True,
            ))

        # ── Option 2: Extend daily hours ──────────────────────────────────────
        extra_per_day = shortfall / max(feasibility.days_until_deadline, 1)
        options.append(RecoveryOption(
            option_index=1,
            label="Extend daily working hours",
            description=(
                f"Work an extra {extra_per_day:.1f} h/day to cover the {shortfall:.1f} h shortfall "
                f"over {feasibility.days_until_deadline:.0f} days."
            ),
            trade_offs=(
                "Increases personal workload. Sustainable only for short bursts. "
                "Consider taking breaks."
            ),
            affected_tasks=[],
            additional_hours_required=round(shortfall, 2),
            feasible_after_recovery=True,
        ))

        # ── Option 3: Negotiate deadline ──────────────────────────────────────
        # How many extra days are needed at current daily rate?
        daily_available = (
            feasibility.usable_hours_before_deadline / max(feasibility.days_until_deadline, 1)
        )
        extra_days_needed = math.ceil(shortfall / daily_available) if daily_available > 0 else 999
        new_deadline_dt = datetime.fromisoformat(feasibility.deadline).astimezone(timezone.utc) + timedelta(days=extra_days_needed)
        options.append(RecoveryOption(
            option_index=2,
            label="Negotiate deadline extension",
            description=(
                f"Extend the deadline by {extra_days_needed} day(s) to "
                f"{new_deadline_dt.strftime('%Y-%m-%d')}. "
                f"No extra daily hours required."
            ),
            trade_offs=(
                "Requires stakeholder agreement. Other tasks may still conflict."
            ),
            affected_tasks=[
                AffectedTask(
                    task_id=feasibility.task_id,
                    title=feasibility.task_title,
                    original_deadline=feasibility.deadline,
                    new_deadline=new_deadline_dt.isoformat(),
                    action="extend_deadline",
                )
            ],
            additional_hours_required=0.0,
            new_p1_deadline=new_deadline_dt.isoformat(),
            feasible_after_recovery=True,
        ))

        # Persist proposal
        proposal = RecoveryProposal(
            trigger_task_id=feasibility.task_id,
            trigger_reason=feasibility.explanation,
        )
        proposal.options = [opt.model_dump() for opt in options]
        self.session.add(proposal)
        self.session.commit()
        self.session.refresh(proposal)

        return RecoveryProposalResponse(
            proposal_id=proposal.id,
            trigger_task_id=feasibility.task_id,
            trigger_reason=feasibility.explanation,
            options=options,
            requires_approval=True,
        )

    # ── Resolve ───────────────────────────────────────────────────────────────

    def resolve_proposal(
        self,
        proposal_id: str,
        action: str,          # "accept" or "reject"
        option_index: Optional[int] = None,
    ) -> ResolveProposalResponse:
        """
        Accept or reject a recovery proposal.

        REJECT: changes absolutely nothing — verified by test.
        ACCEPT: applies the chosen option's task modifications.
        """
        proposal = self.session.get(RecoveryProposal, proposal_id)
        if proposal is None:
            raise KeyError(f"Recovery proposal {proposal_id!r} not found")

        if proposal.status != RecoveryProposalStatus.PENDING:
            return ResolveProposalResponse(
                proposal_id=proposal_id,
                action=action,
                status=proposal.status,
                message=f"Proposal already {proposal.status}. No changes made.",
                tasks_modified=[],
            )

        if action == "reject":
            proposal.reject()
            self.session.add(proposal)
            self.session.commit()
            return ResolveProposalResponse(
                proposal_id=proposal_id,
                action="reject",
                status=RecoveryProposalStatus.REJECTED,
                message="Recovery proposal rejected. No tasks were modified.",
                tasks_modified=[],
            )

        # ── Accept ────────────────────────────────────────────────────────────
        if option_index is None:
            raise ValueError("option_index is required when accepting a proposal")
        options = proposal.options
        if option_index < 0 or option_index >= len(options):
            raise ValueError(f"option_index {option_index} out of range (0–{len(options)-1})")

        chosen = options[option_index]
        modified_ids: List[str] = []

        task_svc = TaskService(self.session)
        from app.schemas.task import TaskUpdate

        for affected in chosen.get("affected_tasks", []):
            tid = affected["task_id"]
            action_type = affected.get("action", "")
            try:
                if action_type == "defer":
                    task_svc.update_task(tid, TaskUpdate(status=TaskStatus.DEFERRED))
                    modified_ids.append(tid)
                elif action_type == "extend_deadline":
                    new_dl = affected.get("new_deadline")
                    if new_dl:
                        task_svc.update_task(tid, TaskUpdate(deadline=new_dl))
                        modified_ids.append(tid)
            except TaskNotFoundError:
                pass  # Task may have been deleted; skip

        proposal.accept(option_index)
        self.session.add(proposal)
        self.session.commit()

        return ResolveProposalResponse(
            proposal_id=proposal_id,
            action="accept",
            status=RecoveryProposalStatus.ACCEPTED,
            message=f"Accepted option {option_index}: '{chosen.get('label', '')}'. {len(modified_ids)} task(s) modified.",
            tasks_modified=modified_ids,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_lower_priority_tasks(self, p1_task_id: str) -> List[Task]:
        from sqlmodel import select
        stmt = (
            select(Task)
            .where(
                Task.priority > 1,
                Task.status.not_in([TaskStatus.DONE, TaskStatus.DEFERRED]),
                Task.id != p1_task_id,
            )
            .order_by(Task.priority.desc(), Task.deadline.desc())
        )
        return list(self.session.exec(stmt).all())

    def _select_tasks_to_defer(self, tasks: List[Task], needed_hours: float) -> List[Task]:
        """Select minimum tasks to defer to cover the needed hours shortfall."""
        selected: List[Task] = []
        freed = 0.0
        for t in tasks:
            selected.append(t)
            freed += t.remaining_hours
            if freed >= needed_hours:
                break
        return selected
