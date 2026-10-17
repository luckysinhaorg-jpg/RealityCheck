"""
SQLModel ORM models — Task, UserSettings, CompletionLog, RecoveryProposal.

Key design decisions
────────────────────
* All datetimes are stored as UTC-aware ISO strings in SQLite (TEXT affinity).
  SQLModel stores datetime columns as text; we enforce UTC via validators.
* Priority is an integer 1-5 (1 = highest).
* depends_on is stored as a JSON-encoded list of UUIDs (TEXT in SQLite).
* status is a string enum stored as TEXT.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


# ── Helpers ───────────────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


# ── Enums ─────────────────────────────────────────────────────────────────────

class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"
    DEFERRED = "deferred"


class RecoveryProposalStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


# ── Task ──────────────────────────────────────────────────────────────────────

class Task(SQLModel, table=True):
    """Persistent task record."""

    __tablename__ = "tasks"

    id: str = Field(
        default_factory=_new_uuid,
        primary_key=True,
        description="UUID primary key",
    )
    title: str = Field(index=True, description="Short human-readable title")
    description: Optional[str] = Field(default=None)
    category: str = Field(default="general", index=True)
    priority: int = Field(
        default=3,
        ge=1,
        le=5,
        description="1 = highest priority, 5 = lowest",
    )

    # Deadline stored as ISO 8601 UTC string
    deadline: str = Field(
        description="UTC deadline as ISO 8601 string with timezone offset"
    )

    # Hours
    estimated_hours: float = Field(gt=0, description="Original estimate in hours")
    actual_hours: float = Field(default=0.0, ge=0, description="Logged actual hours")
    remaining_hours: float = Field(
        ge=0, description="Remaining work hours (auto-maintained)"
    )

    # Status
    status: str = Field(
        default=TaskStatus.TODO,
        description="Current task status",
    )

    # Dependencies — stored as JSON array of task IDs
    depends_on_json: str = Field(
        default="[]",
        sa_column=Column("depends_on", Text),
        description="JSON list of prerequisite task IDs",
    )

    # Scheduling constraints
    splittable: bool = Field(
        default=True,
        description="Whether this task can be split across multiple sessions",
    )
    earliest_start: Optional[str] = Field(
        default=None,
        description="UTC ISO 8601 — do not schedule before this instant",
    )
    fixed_start: Optional[str] = Field(
        default=None,
        description="UTC ISO 8601 — must start exactly at this time",
    )
    fixed_end: Optional[str] = Field(
        default=None,
        description="UTC ISO 8601 — must end exactly at this time",
    )

    # Confidence
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in the estimate [0,1]",
    )

    # Audit
    created_at: str = Field(
        default_factory=lambda: _utcnow().isoformat(),
    )
    updated_at: str = Field(
        default_factory=lambda: _utcnow().isoformat(),
    )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @property
    def depends_on(self) -> List[str]:
        try:
            return json.loads(self.depends_on_json)
        except (json.JSONDecodeError, TypeError):
            return []

    @depends_on.setter
    def depends_on(self, value: List[str]) -> None:
        self.depends_on_json = json.dumps(value)

    def deadline_dt(self) -> datetime:
        """Return deadline as UTC-aware datetime."""
        dt = datetime.fromisoformat(self.deadline)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    def earliest_start_dt(self) -> Optional[datetime]:
        if not self.earliest_start:
            return None
        dt = datetime.fromisoformat(self.earliest_start)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = _utcnow().isoformat()


# ── UserSettings ──────────────────────────────────────────────────────────────

class UserSettings(SQLModel, table=True):
    """Single-row application settings (id is always 1)."""

    __tablename__ = "user_settings"

    id: int = Field(default=1, primary_key=True)

    # Daily available hours per weekday (0=Mon … 6=Sun) stored as JSON
    daily_hours_json: str = Field(
        default='{"0":8,"1":8,"2":8,"3":8,"4":8,"5":4,"6":2}',
        sa_column=Column("daily_hours", Text),
    )

    # Working window — stored as "HH:MM" strings
    work_start: str = Field(default="09:00")
    work_end: str = Field(default="17:00")

    # Break rule: duration in minutes after every N hours of work
    break_duration_minutes: int = Field(default=15)
    break_after_hours: float = Field(default=2.0)

    # Scheduling buffer as a fraction (e.g. 0.1 = 10 % padding)
    buffer_fraction: float = Field(default=0.1, ge=0.0, le=0.5)

    # IANA timezone name
    timezone: str = Field(default="UTC")

    updated_at: str = Field(default_factory=lambda: _utcnow().isoformat())

    @property
    def daily_hours(self) -> dict[str, float]:
        try:
            return {str(k): float(v) for k, v in json.loads(self.daily_hours_json).items()}
        except (json.JSONDecodeError, TypeError):
            return {str(i): 8.0 for i in range(5)} | {"5": 4.0, "6": 2.0}

    @daily_hours.setter
    def daily_hours(self, value: dict) -> None:
        self.daily_hours_json = json.dumps({str(k): float(v) for k, v in value.items()})

    def touch(self) -> None:
        self.updated_at = _utcnow().isoformat()


# ── CompletionLog ─────────────────────────────────────────────────────────────

class CompletionLog(SQLModel, table=True):
    """Immutable record of a completed task — used for duration estimation."""

    __tablename__ = "completion_logs"

    id: str = Field(default_factory=_new_uuid, primary_key=True)
    task_id: str = Field(index=True, description="FK to tasks.id")
    category: str = Field(index=True)
    estimated_hours: float
    actual_hours: float
    completed_at: str = Field(default_factory=lambda: _utcnow().isoformat())

    @property
    def ratio(self) -> float:
        """actual / estimated. Returns 1.0 if estimated is zero."""
        if self.estimated_hours <= 0:
            return 1.0
        return self.actual_hours / self.estimated_hours


# ── RecoveryProposal ──────────────────────────────────────────────────────────

class RecoveryProposal(SQLModel, table=True):
    """
    Persisted recovery plan proposal.
    Must be explicitly accepted or rejected — never applied silently.
    """

    __tablename__ = "recovery_proposals"

    id: str = Field(default_factory=_new_uuid, primary_key=True)
    status: str = Field(default=RecoveryProposalStatus.PENDING)

    # Snapshot of the plan options as JSON
    options_json: str = Field(
        sa_column=Column("options", Text),
        description="JSON list of RecoveryOption dicts",
    )

    # Which option was selected (index into options list)
    selected_option_index: Optional[int] = Field(default=None)

    # Task analysis context
    trigger_task_id: Optional[str] = Field(default=None)
    trigger_reason: str = Field(default="")

    created_at: str = Field(default_factory=lambda: _utcnow().isoformat())
    resolved_at: Optional[str] = Field(default=None)

    @property
    def options(self) -> list:
        try:
            return json.loads(self.options_json)
        except (json.JSONDecodeError, TypeError):
            return []

    @options.setter
    def options(self, value: list) -> None:
        self.options_json = json.dumps(value)

    def accept(self, option_index: int) -> None:
        self.status = RecoveryProposalStatus.ACCEPTED
        self.selected_option_index = option_index
        self.resolved_at = _utcnow().isoformat()

    def reject(self) -> None:
        self.status = RecoveryProposalStatus.REJECTED
        self.resolved_at = _utcnow().isoformat()
