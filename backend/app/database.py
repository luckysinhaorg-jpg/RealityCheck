"""
Database engine, session factory, and table initialization.

All datetimes stored in UTC. Application layer converts to/from user timezone.
"""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

logger = logging.getLogger(__name__)


def _get_engine(url: str | None = None) -> Engine:
    settings = get_settings()
    db_url = url or settings.database_url

    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(
        db_url,
        connect_args=connect_args,
        echo=settings.app_debug,
    )

    # Enable WAL mode and foreign-key enforcement for SQLite
    if db_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


# Module-level singleton engine (overridable in tests via set_engine)
_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = _get_engine()
    return _engine


def set_engine(engine: Engine) -> None:
    """Override the module-level engine. Used in tests to inject an in-memory engine."""
    global _engine
    _engine = engine


def reset_engine() -> None:
    """Reset the engine singleton (call in test teardown)."""
    global _engine
    _engine = None


def create_test_engine(url: str = "sqlite:///:memory:") -> Engine:
    """
    Create a fresh engine for isolated test sessions.

    Uses StaticPool so every Session created from this engine reuses the
    SAME underlying SQLite connection.  This is required for in-memory
    SQLite — without it each new connection gets a blank database and the
    tables created by init_db() are invisible to request handlers.
    """
    from sqlalchemy.pool import StaticPool

    connect_args = {"check_same_thread": False}
    engine = create_engine(
        url,
        connect_args=connect_args,
        poolclass=StaticPool,
        echo=False,
    )

    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def init_db(engine: Engine | None = None) -> None:
    """Create all tables. Safe to call multiple times."""
    eng = engine or get_engine()
    # Import all models so SQLModel sees them before create_all
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(eng)
    logger.info("Database tables initialised.")


def get_session(engine: Engine | None = None):
    """FastAPI dependency that yields a database session."""
    eng = engine or get_engine()
    with Session(eng) as session:
        yield session
