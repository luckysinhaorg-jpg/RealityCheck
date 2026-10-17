"""Settings router — /api/settings"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlmodel import Session

from app.dependencies import get_or_create_settings, get_session
from app.models.task import UserSettings

router = APIRouter()


class SettingsRead(BaseModel):
    daily_hours: dict
    work_start: str
    work_end: str
    break_duration_minutes: int
    break_after_hours: float
    buffer_fraction: float
    timezone: str
    updated_at: str


class SettingsUpdate(BaseModel):
    daily_hours: Optional[dict] = None
    work_start: Optional[str] = None
    work_end: Optional[str] = None
    break_duration_minutes: Optional[int] = None
    break_after_hours: Optional[float] = None
    buffer_fraction: Optional[float] = None
    timezone: Optional[str] = None


@router.get("", response_model=SettingsRead)
def get_settings(
    settings: UserSettings = Depends(get_or_create_settings),
):
    return _to_read(settings)


@router.patch("", response_model=SettingsRead)
def update_settings(
    data: SettingsUpdate,
    settings: UserSettings = Depends(get_or_create_settings),
    session: Session = Depends(get_session),
):
    if data.daily_hours is not None:
        settings.daily_hours = data.daily_hours
    for field in ("work_start", "work_end", "break_duration_minutes",
                  "break_after_hours", "buffer_fraction", "timezone"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(settings, field, val)
    settings.touch()
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return _to_read(settings)


def _to_read(s: UserSettings) -> SettingsRead:
    return SettingsRead(
        daily_hours=s.daily_hours,
        work_start=s.work_start,
        work_end=s.work_end,
        break_duration_minutes=s.break_duration_minutes,
        break_after_hours=s.break_after_hours,
        buffer_fraction=s.buffer_fraction,
        timezone=s.timezone,
        updated_at=s.updated_at,
    )
