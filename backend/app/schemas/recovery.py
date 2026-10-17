"""
Recovery schemas — proposal options and responses.
"""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class AffectedTask(BaseModel):
    task_id: str
    title: str
    original_deadline: str
    new_deadline: Optional[str] = None
    action: str   # e.g. "defer", "reduce_scope", "extend_hours"


class RecoveryOption(BaseModel):
    """One of (typically 2–3) recovery options offered to the user."""
    option_index: int
    label: str
    description: str
    trade_offs: str
    affected_tasks: List[AffectedTask]
    additional_hours_required: float
    new_p1_deadline: Optional[str] = None
    feasible_after_recovery: bool


class RecoveryProposalResponse(BaseModel):
    """
    API/MCP response when a recovery plan is generated.
    Contains a persisted proposal_id for the resolve_recovery_proposal tool.
    """
    proposal_id: str
    trigger_task_id: Optional[str]
    trigger_reason: str
    options: List[RecoveryOption]
    requires_approval: bool = True


class ResolveProposalRequest(BaseModel):
    proposal_id: str
    action: str = Field(pattern="^(accept|reject)$")
    option_index: Optional[int] = Field(
        default=None,
        description="Required when action=accept. Zero-based index into options list.",
    )


class ResolveProposalResponse(BaseModel):
    proposal_id: str
    action: str
    status: str
    message: str
    tasks_modified: List[str] = Field(default_factory=list)
