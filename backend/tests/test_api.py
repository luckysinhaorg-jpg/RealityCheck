"""
FastAPI REST API integration tests using httpx.AsyncClient + in-memory SQLite.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from app.database import create_test_engine, init_db
from app.main import create_app
from app.dependencies import get_session, get_or_create_settings
from app.models.task import UserSettings


# ── App fixture with isolated DB ──────────────────────────────────────────────

@pytest.fixture(scope="function")
def api_client():
    """
    Create a test FastAPI client backed by a fresh in-memory SQLite database.

    We inject the test engine into the module-level singleton BEFORE the
    TestClient context manager runs the app's lifespan, so init_db() in
    lifespan uses our test engine, not the real file-based one.
    """
    from app.database import set_engine, reset_engine, create_test_engine, init_db

    engine = create_test_engine()
    # Inject before TestClient (lifespan) starts
    set_engine(engine)
    # Create tables now (lifespan init_db will be a no-op since tables exist)
    init_db(engine)

    def _override_session():
        with Session(engine) as s:
            yield s

    def _override_settings():
        """Return default settings, creating if absent."""
        with Session(engine) as s:
            settings = s.get(UserSettings, 1)
            if settings is None:
                settings = UserSettings()
                s.add(settings)
                s.commit()
                s.refresh(settings)
            return settings

    app = create_app()
    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_or_create_settings] = _override_settings

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client

    reset_engine()
    engine.dispose()



# ── Helper ────────────────────────────────────────────────────────────────────

def _deadline(days: int = 7) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


# ── Health ────────────────────────────────────────────────────────────────────

def test_health(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── Tasks CRUD ────────────────────────────────────────────────────────────────

def test_create_task(api_client):
    payload = {"title": "Write API", "deadline": _deadline(), "estimated_hours": 5}
    r = api_client.post("/api/tasks", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "Write API"
    assert body["remaining_hours"] == 5.0
    assert "id" in body


def test_create_task_missing_field(api_client):
    r = api_client.post("/api/tasks", json={"title": "No deadline"})
    assert r.status_code == 422


def test_duplicate_task_returns_409(api_client):
    dl = _deadline()
    api_client.post("/api/tasks", json={"title": "Dup", "deadline": dl, "estimated_hours": 2})
    r = api_client.post("/api/tasks", json={"title": "Dup", "deadline": dl, "estimated_hours": 2})
    assert r.status_code == 409
    assert "already exists" in r.json()["detail"]


def test_list_tasks_empty(api_client):
    r = api_client.get("/api/tasks")
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_list_tasks_filter_status(api_client):
    dl = _deadline()
    api_client.post("/api/tasks", json={"title": "A", "deadline": dl, "estimated_hours": 2})
    api_client.post("/api/tasks", json={"title": "B", "deadline": _deadline(14), "estimated_hours": 2})
    r = api_client.get("/api/tasks?status=todo")
    assert r.status_code == 200
    assert r.json()["total"] == 2


def test_get_task_not_found(api_client):
    r = api_client.get("/api/tasks/nonexistent-id")
    assert r.status_code == 404


def test_update_task(api_client):
    r = api_client.post("/api/tasks", json={"title": "X", "deadline": _deadline(), "estimated_hours": 3})
    task_id = r.json()["id"]
    r2 = api_client.patch(f"/api/tasks/{task_id}", json={"priority": 1, "category": "research"})
    assert r2.status_code == 200
    assert r2.json()["priority"] == 1
    assert r2.json()["category"] == "research"


def test_delete_task(api_client):
    r = api_client.post("/api/tasks", json={"title": "Del", "deadline": _deadline(), "estimated_hours": 1})
    task_id = r.json()["id"]
    r2 = api_client.delete(f"/api/tasks/{task_id}")
    assert r2.status_code == 204
    r3 = api_client.get(f"/api/tasks/{task_id}")
    assert r3.status_code == 404


def test_invalid_dependency_returns_422(api_client):
    r = api_client.post("/api/tasks", json={
        "title": "Bad", "deadline": _deadline(),
        "estimated_hours": 2, "depends_on": ["no-such-id"]
    })
    assert r.status_code == 422


# ── Settings ──────────────────────────────────────────────────────────────────

def test_get_settings(api_client):
    r = api_client.get("/api/settings")
    assert r.status_code == 200
    body = r.json()
    assert "daily_hours" in body
    assert "buffer_fraction" in body


def test_update_settings(api_client):
    r = api_client.patch("/api/settings", json={"buffer_fraction": 0.15, "timezone": "America/New_York"})
    assert r.status_code == 200
    body = r.json()
    assert body["buffer_fraction"] == 0.15
    assert body["timezone"] == "America/New_York"


# ── Plans ─────────────────────────────────────────────────────────────────────

def test_feasibility_task_not_found(api_client):
    r = api_client.get("/api/plans/feasibility/bad-id")
    assert r.status_code == 404


def test_feasibility_feasible(api_client):
    r = api_client.post("/api/tasks", json={
        "title": "Easy", "deadline": _deadline(30),
        "estimated_hours": 4, "priority": 1
    })
    task_id = r.json()["id"]
    r2 = api_client.get(f"/api/plans/feasibility/{task_id}")
    assert r2.status_code == 200
    body = r2.json()
    assert body["feasible"] is True
    assert "FEASIBLE" in body["explanation"]


def test_feasibility_impossible(api_client):
    r = api_client.post("/api/tasks", json={
        "title": "Impossible", "deadline": _deadline(1),
        "estimated_hours": 999, "priority": 1
    })
    task_id = r.json()["id"]
    r2 = api_client.get(f"/api/plans/feasibility/{task_id}")
    assert r2.status_code == 200
    body = r2.json()
    assert body["feasible"] is False
    assert body["shortfall_hours"] is not None


def test_generate_plan_empty(api_client):
    r = api_client.post("/api/plans/generate", json={"days_ahead": 7})
    assert r.status_code == 200
    body = r.json()
    assert "plan" in body
    assert len(body["plan"]) == 7


def test_generate_plan_with_tasks(api_client):
    api_client.post("/api/tasks", json={"title": "Plan me", "deadline": _deadline(5), "estimated_hours": 4})
    r = api_client.post("/api/plans/generate", json={"days_ahead": 7})
    assert r.status_code == 200


# ── Recovery ──────────────────────────────────────────────────────────────────

def test_generate_recovery_task_not_found(api_client):
    r = api_client.post("/api/recovery/generate/bad-id")
    assert r.status_code == 404


def test_generate_and_reject_recovery(api_client):
    r = api_client.post("/api/tasks", json={
        "title": "Infeasible", "deadline": _deadline(1),
        "estimated_hours": 999, "priority": 1
    })
    task_id = r.json()["id"]

    r2 = api_client.post(f"/api/recovery/generate/{task_id}")
    assert r2.status_code == 200
    body = r2.json()
    assert "proposal_id" in body
    assert len(body["options"]) >= 2
    assert body["requires_approval"] is True

    proposal_id = body["proposal_id"]
    r3 = api_client.post("/api/recovery/resolve", json={
        "proposal_id": proposal_id,
        "action": "reject"
    })
    assert r3.status_code == 200
    assert r3.json()["action"] == "reject"
    assert r3.json()["tasks_modified"] == []


def test_reject_changes_nothing(api_client):
    """Full end-to-end: reject must leave all tasks unchanged."""
    # Create tasks
    dl = _deadline(1)
    r1 = api_client.post("/api/tasks", json={"title": "Main", "deadline": dl, "estimated_hours": 999})
    r2 = api_client.post("/api/tasks", json={"title": "Low", "deadline": dl, "estimated_hours": 5, "priority": 4})

    before_tasks = api_client.get("/api/tasks").json()["tasks"]
    before_map = {t["id"]: t["status"] for t in before_tasks}

    proposal_id = api_client.post(f"/api/recovery/generate/{r1.json()['id']}").json()["proposal_id"]
    api_client.post("/api/recovery/resolve", json={"proposal_id": proposal_id, "action": "reject"})

    after_tasks = api_client.get("/api/tasks").json()["tasks"]
    after_map = {t["id"]: t["status"] for t in after_tasks}
    assert before_map == after_map


def test_record_completion(api_client):
    r = api_client.post("/api/tasks", json={"title": "Done Soon", "deadline": _deadline(5), "estimated_hours": 4})
    task_id = r.json()["id"]
    r2 = api_client.post(f"/api/recovery/complete/{task_id}?actual_hours=6")
    assert r2.status_code == 200
    body = r2.json()
    assert body["actual_hours"] == 6.0
    assert "ratio" in body

    # Task should now be DONE
    r3 = api_client.get(f"/api/tasks/{task_id}")
    assert r3.json()["status"] == "done"


def test_resolve_nonexistent_proposal(api_client):
    r = api_client.post("/api/recovery/resolve", json={
        "proposal_id": "nonexistent",
        "action": "reject"
    })
    assert r.status_code == 404
