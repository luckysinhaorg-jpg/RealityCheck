"""FastAPI dependency: inject a DB session."""
from app.database import get_session as _get_session
from fastapi import Depends
from sqlmodel import Session

from app.config import get_settings as _get_settings
from app.models.task import UserSettings


def get_session():
    yield from _get_session()


def get_or_create_settings(session: Session = Depends(get_session)) -> UserSettings:
    """Return the singleton UserSettings row, creating it if absent."""
    settings = session.get(UserSettings, 1)
    if settings is None:
        cfg = _get_settings()
        settings = UserSettings(timezone=cfg.default_timezone)
        session.add(settings)
        session.commit()
        session.refresh(settings)
    return settings
