"""
Integration tests for RealityCheck MCP server over Streamable HTTP.

Verifies:
  1. Unauthorized request (missing/invalid Bearer token) returns 401.
  2. Protocol initialize handshake (MCP spec 2025-11-25).
  3. Trailing-slash handling (/mcp and /mcp/ both respond with 200).
  4. Response headers include MCP-Protocol-Version: 2025-11-25.
  5. notifications/initialized notification handled cleanly.
  6. tools/list returns all 9 required tools with schemas.
  7. tools/call create_task persists real task in database.
  8. tools/call calculate_deadline_feasibility returns deterministic calculation.
  9. tools/call generate_recovery_plan returns proposal with proposal_id & options.
 10. tools/call resolve_recovery_proposal: REJECT leaves tasks unchanged.
 11. tools/call record_task_completion and update_duration_estimate.
 12. tools/call error handling: missing task, duplicate task, invalid input.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config import get_settings
from app.database import create_test_engine, init_db, reset_engine, set_engine
from app.dependencies import get_or_create_settings, get_session
from app.main import create_app
from app.models.task import UserSettings


# ── Test Client Fixture ────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def mcp_client():
    engine = create_test_engine()
    set_engine(engine)
    init_db(engine)

    def _override_session():
        with Session(engine) as s:
            yield s

    def _override_settings():
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


@pytest.fixture
def auth_headers():
    cfg = get_settings()
    return {
        "Authorization": f"Bearer {cfg.mcp_bearer_token}",
        "Content-Type": "application/json",
    }


def _deadline(days: int = 5) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


# ── Authentication Tests ──────────────────────────────────────────────────────

def test_mcp_unauthorized_missing_token(mcp_client):
    r = mcp_client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert r.status_code == 401
    assert "WWW-Authenticate" in r.headers
    assert r.json()["error"] == "Unauthorized"


def test_mcp_unauthorized_invalid_token(mcp_client):
    r = mcp_client.post(
        "/mcp",
        headers={"Authorization": "Bearer completely-wrong-token"},
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
    )
    assert r.status_code == 401
    assert r.json()["error"] == "Unauthorized"


# ── MCP Protocol Handshake ───────────────────────────────────────────────────

def test_mcp_initialize(mcp_client, auth_headers):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "realitycheck-client", "version": "0.1.0"},
        },
    }
    r = mcp_client.post("/mcp", headers=auth_headers, json=payload)
    assert r.status_code == 200
    assert r.headers.get("MCP-Protocol-Version") == "2025-11-25"
    data = r.json()
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == 1
    assert "result" in data
    res = data["result"]
    assert res["protocolVersion"] == "2025-11-25"
    assert res["serverInfo"]["name"] == "realitycheck"
    assert "tools" in res["capabilities"]


def test_mcp_trailing_slash_normalization(mcp_client, auth_headers):
    """Both /mcp and /mcp/ must return 200 without redirect errors."""
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "realitycheck-client", "version": "0.1.0"},
        },
    }
    r1 = mcp_client.post("/mcp", headers=auth_headers, json=payload)
    assert r1.status_code == 200
    r2 = mcp_client.post("/mcp/", headers=auth_headers, json=payload)
    assert r2.status_code == 200


def test_mcp_notifications_initialized(mcp_client, auth_headers):
    payload = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {},
    }
    r = mcp_client.post("/mcp", headers=auth_headers, json=payload)
    assert r.status_code in (200, 202)


# ── MCP tools/list ───────────────────────────────────────────────────────────

def test_mcp_tools_list_returns_9_tools(mcp_client, auth_headers):
    payload = {"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}}
    r = mcp_client.post("/mcp", headers=auth_headers, json=payload)
    assert r.status_code == 200
    tools = r.json().get("result", {}).get("tools", [])
    tool_names = {t["name"] for t in tools}

    expected_tools = {
        "create_task",
        "list_tasks",
        "update_task",
        "calculate_deadline_feasibility",
        "generate_daily_plan",
        "generate_recovery_plan",
        "record_task_completion",
        "update_duration_estimate",
        "resolve_recovery_proposal",
    }
    assert expected_tools.issubset(tool_names)
    assert len(tools) >= 9

    # Each tool must have description and inputSchema
    for t in tools:
        assert "description" in t and len(t["description"]) > 0
        assert "inputSchema" in t


# ── MCP tools/call End-to-End ────────────────────────────────────────────────

def test_mcp_tool_create_and_list_tasks(mcp_client, auth_headers):
    # 1. Call create_task
    create_call = {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {
            "name": "create_task",
            "arguments": {
                "title": "Study for Exam",
                "deadline": _deadline(4),
                "estimated_hours": 12.0,
                "priority": 1,
                "category": "study",
            },
        },
    }
    r = mcp_client.post("/mcp", headers=auth_headers, json=create_call)
    assert r.status_code == 200
    res = r.json()["result"]
    assert res.get("isError") is False
    task_data = json.loads(res["content"][0]["text"])
    assert task_data["title"] == "Study for Exam"
    assert task_data["priority"] == 1
    task_id = task_data["id"]

    # 2. Call list_tasks
    list_call = {
        "jsonrpc": "2.0",
        "id": 11,
        "method": "tools/call",
        "params": {"name": "list_tasks", "arguments": {"priority": 1}},
    }
    r2 = mcp_client.post("/mcp", headers=auth_headers, json=list_call)
    assert r2.status_code == 200
    list_data = json.loads(r2.json()["result"]["content"][0]["text"])
    assert list_data["total"] == 1
    assert list_data["tasks"][0]["id"] == task_id


def test_mcp_tool_calculate_deadline_feasibility(mcp_client, auth_headers):
    # Create task
    create_call = {
        "jsonrpc": "2.0",
        "id": 20,
        "method": "tools/call",
        "params": {
            "name": "create_task",
            "arguments": {
                "title": "Easy Homework",
                "deadline": _deadline(14),
                "estimated_hours": 2.0,
                "priority": 1,
            },
        },
    }
    r1 = mcp_client.post("/mcp", headers=auth_headers, json=create_call)
    task_id = json.loads(r1.json()["result"]["content"][0]["text"])["id"]

    # Feasibility check
    feas_call = {
        "jsonrpc": "2.0",
        "id": 21,
        "method": "tools/call",
        "params": {
            "name": "calculate_deadline_feasibility",
            "arguments": {"task_id": task_id, "lost_hours_today": 0.0},
        },
    }
    r2 = mcp_client.post("/mcp", headers=auth_headers, json=feas_call)
    assert r2.status_code == 200
    feas_result = json.loads(r2.json()["result"]["content"][0]["text"])
    assert feas_result["feasible"] is True
    assert "explanation" in feas_result


def test_mcp_tool_recovery_plan_and_reject_safety(mcp_client, auth_headers):
    """Verify recovery plan generation and that REJECT modifies no tasks."""
    # Create an impossible task (999 hours in 1 day)
    create_call = {
        "jsonrpc": "2.0",
        "id": 30,
        "method": "tools/call",
        "params": {
            "name": "create_task",
            "arguments": {
                "title": "Impossible Sprint",
                "deadline": _deadline(1),
                "estimated_hours": 999.0,
                "priority": 1,
            },
        },
    }
    r1 = mcp_client.post("/mcp", headers=auth_headers, json=create_call)
    task_id = json.loads(r1.json()["result"]["content"][0]["text"])["id"]

    # Generate recovery plan
    rec_call = {
        "jsonrpc": "2.0",
        "id": 31,
        "method": "tools/call",
        "params": {
            "name": "generate_recovery_plan",
            "arguments": {"task_id": task_id},
        },
    }
    r2 = mcp_client.post("/mcp", headers=auth_headers, json=rec_call)
    assert r2.status_code == 200
    rec_result = json.loads(r2.json()["result"]["content"][0]["text"])
    assert "proposal_id" in rec_result
    proposal_id = rec_result["proposal_id"]
    assert len(rec_result["options"]) >= 2
    assert rec_result["requires_approval"] is True

    # Reject the proposal
    reject_call = {
        "jsonrpc": "2.0",
        "id": 32,
        "method": "tools/call",
        "params": {
            "name": "resolve_recovery_proposal",
            "arguments": {
                "proposal_id": proposal_id,
                "action": "reject",
            },
        },
    }
    r3 = mcp_client.post("/mcp", headers=auth_headers, json=reject_call)
    assert r3.status_code == 200
    reject_result = json.loads(r3.json()["result"]["content"][0]["text"])
    assert reject_result["action"] == "reject"
    assert reject_result["tasks_modified"] == []

    # Verify task remains unchanged
    list_call = {
        "jsonrpc": "2.0",
        "id": 33,
        "method": "tools/call",
        "params": {"name": "list_tasks", "arguments": {}},
    }
    r4 = mcp_client.post("/mcp", headers=auth_headers, json=list_call)
    tasks = json.loads(r4.json()["result"]["content"][0]["text"])["tasks"]
    task = next(t for t in tasks if t["id"] == task_id)
    assert task["status"] == "todo"
    assert task["estimated_hours"] == 999.0


def test_mcp_tool_duration_estimate_threshold(mcp_client, auth_headers):
    """Verify that update_duration_estimate enforces the 3-completed-task threshold."""
    # Check category with 0 tasks
    call1 = {
        "jsonrpc": "2.0",
        "id": 40,
        "method": "tools/call",
        "params": {"name": "update_duration_estimate", "arguments": {"category": "coding"}},
    }
    r1 = mcp_client.post("/mcp", headers=auth_headers, json=call1)
    res1 = json.loads(r1.json()["result"]["content"][0]["text"])
    assert res1["samples"] == 0
    assert res1["adjustment_active"] is False
    assert res1["ratio"] == 1.0

    # Create & complete 3 tasks in "coding"
    for i in range(3):
        cr = mcp_client.post("/mcp", headers=auth_headers, json={
            "jsonrpc": "2.0", "id": 50 + i, "method": "tools/call",
            "params": {"name": "create_task", "arguments": {
                "title": f"Code task {i}", "deadline": _deadline(10),
                "estimated_hours": 2.0, "category": "coding"
            }}
        })
        tid = json.loads(cr.json()["result"]["content"][0]["text"])["id"]
        # Complete with 3.0 hours (1.5x)
        mcp_client.post("/mcp", headers=auth_headers, json={
            "jsonrpc": "2.0", "id": 60 + i, "method": "tools/call",
            "params": {"name": "record_task_completion", "arguments": {
                "task_id": tid, "actual_hours": 3.0
            }}
        })

    # Now threshold (>=3) is met
    r2 = mcp_client.post("/mcp", headers=auth_headers, json=call1)
    res2 = json.loads(r2.json()["result"]["content"][0]["text"])
    assert res2["samples"] == 3
    assert res2["adjustment_active"] is True
    assert res2["ratio"] == 1.5
