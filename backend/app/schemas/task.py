"""
Pydantic request/response schemas for Tasks.
Separate from SQLModel ORM models to keep the API surface clean.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.task import TaskStatus


# ── Validation helpers ────────────────────────────────────────────────────────

def _parse_utc(v: str | datetime) -> str:
    """Accept ISO 8601 string or datetime; ensure UTC-aware; return ISO string."""
    if isinstance(v, datetime):
        dt = v
    else:
        dt = datetime.fromisoformat(str(v))
    if dt.tzinfo is None:
        raise ValueError("Datetime must be timezone-aware (include UTC offset or Z)")
    # Normalise to UTC
    utc_dt = dt.astimezone(timezone.utc)
    return utc_dt.isoformat()


# ── Task schemas ──────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    category: str = Field(default="general", min_length=1, max_length=80)
    priority: int = Field(default=3, ge=1, le=5)
    deadline: str = Field(description="UTC ISO 8601 deadline")
    estimated_hours: float = Field(gt=0)
    status: TaskStatus = TaskStatus.TODO
    depends_on: List[str] = Field(default_factory=list)
    splittable: bool = True
    earliest_start: Optional[str] = None
    fixed_start: Optional[str] = None
    fixed_end: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("deadline", "earliest_start", "fixed_start", "fixed_end", mode="before")
    @classmethod
    def validate_datetime(cls, v):
        if v is None:
            return v
        return _parse_utc(v)

    @model_validator(mode="after")
    def validate_fixed_consistency(self) -> "TaskCreate":
        if self.fixed_start and self.fixed_end:
            fs = datetime.fromisoformat(self.fixed_start)
            fe = datetime.fromisoformat(self.fixed_end)
            if fe <= fs:
                raise ValueError("fixed_end must be after fixed_start")
        return self


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[int] = Field(default=None, ge=1, le=5)
    deadline: Optional[str] = None
    estimated_hours: Optional[float] = Field(default=None, gt=0)
    actual_hours: Optional[float] = Field(default=None, ge=0)
    remaining_hours: Optional[float] = Field(default=None, ge=0)
    status: Optional[TaskStatus] = None
    depends_on: Optional[List[str]] = None
    splittable: Optional[bool] = None
    earliest_start: Optional[str] = None
    fixed_start: Optional[str] = None
    fixed_end: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    @field_validator("deadline", "earliest_start", "fixed_start", "fixed_end", mode="before")
    @classmethod
    def validate_datetime(cls, v):
        if v is None:
            return v
        return _parse_utc(v)


class TaskRead(BaseModel):
    id: str
    title: str
    description: Optional[str]
    category: str
    priority: int
    deadline: str
    estimated_hours: float
    actual_hours: float
    remaining_hours: float
    status: str
    depends_on: List[str]
    splittable: bool
    earliest_start: Optional[str]
    fixed_start: Optional[str]
    fixed_end: Optional[str]
    confidence: float
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    tasks: List[TaskRead]
    total: int
