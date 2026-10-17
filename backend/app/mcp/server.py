"""
RealityCheck MCP Server — Streamable HTTP, MCP spec 2025-11-25

SDK: mcp 2.3.0  (mcp.server.mcpserver.MCPServer)
Docs relied upon:
  - mcp 2.x migration guide:
    https://py.sdk.modelcontextprotocol.io/v2/migration/#fastmcp-renamed-to-mcpserver
    (read 2026-10-16)
  - MCPServer.streamable_http_app() inspected via inspect.signature() (2026-10-16)
  - Starlette Mount routing: https://www.starlette.io/routing/#submounting-routes
    (read 2026-10-16)

9 tools, all delegating to shared service layer (same DB as REST API).

MOUNTING NOTES
--------------
streamable_http_app(streamable_http_path="/") creates an internal route at "/".
FastAPI's app.mount("/mcp", mcp_asgi) strips the "/mcp" prefix, so the MCP
handler correctly sees "/" — requests reach POST /mcp correctly.

Bearer auth: validated BEFORE the MCP ASGI app via MCPBearerMiddleware in main.py.
"""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

from mcp.server.mcpserver import MCPServer
from starlette.applications import Starlette

from app.database import get_engine
from app.models.task import UserSettings

logger = logging.getLogger(__name__)


# ── Build MCPServer ───────────────────────────────────────────────────────────

def _build() -> MCPServer:
    server = MCPServer(
        name="realitycheck",
        title="RealityCheck Planner",
        instructions=(
            "RealityCheck deadline-recovery planner. All scheduling arithmetic "
            "is deterministic — no LLM involved. "
            "Bearer token authentication required: Authorization: Bearer <token>. "
            "This is a SIMULATION of an Alexa+ MCP skill, not a certified Alexa+ add-on."
        ),
    )

    # ── Tool 1: create_task ───────────────────────────────────────────────────
    @server.tool(description="Create a new task. Required: title, deadline (ISO 8601 UTC), estimated_hours.")
    async def create_task(
        title: str,
        deadline: str,
        estimated_hours: float,
        description: str = "",
        category: str = "general",
        priority: int = 3,
        depends_on: list[str] = [],
        splittable: bool = True,
        earliest_start: str = "",
        confidence: float = 1.0,
    ) -> str:
        from app.schemas.task import TaskCreate
        from app.services.task_service import TaskService, DuplicateTaskError, InvalidDependencyError
        with _db() as session:
            try:
                data = TaskCreate(
                    title=title, deadline=deadline, estimated_hours=estimated_hours,
                    description=description or None, category=category, priority=priority,
                    depends_on=depends_on, splittable=splittable,
                    earliest_start=earliest_start or None, confidence=confidence,
                )
                task = TaskService(session).create_task(data)
                return json.dumps(_task_dict(task))
            except DuplicateTaskError as e:
                return json.dumps({"error": "duplicate", "detail": str(e)})
            except InvalidDependencyError as e:
                return json.dumps({"error": "invalid_dependency", "detail": str(e)})
            except Exception as e:
                return json.dumps({"error": "validation_error", "detail": str(e)})

    # ── Tool 2: list_tasks ────────────────────────────────────────────────────
    @server.tool(description="List tasks. Optional filters: status, priority (1-5), category.")
    async def list_tasks(
        status: str = "",
        priority: int = 0,
        category: str = "",
    ) -> str:
        from app.services.task_service import TaskService
        with _db() as session:
            tasks = TaskService(session).list_tasks(
                status=status or None,
                priority=priority or None,
                category=category or None,
            )
            return json.dumps({"tasks": [_task_dict(t) for t in tasks], "total": len(tasks)})

    # ── Tool 3: update_task ───────────────────────────────────────────────────
    @server.tool(description="Update a task. Required: task_id. Optional: any field to change.")
    async def update_task(
        task_id: str,
        title: str = "",
        priority: int = 0,
        deadline: str = "",
        estimated_hours: float = 0.0,
        actual_hours: float = -1.0,
        remaining_hours: float = -1.0,
        status: str = "",
    ) -> str:
        from app.schemas.task import TaskUpdate
        from app.services.task_service import TaskService, TaskNotFoundError
        with _db() as session:
            try:
                upd: dict[str, Any] = {}
                if title: upd["title"] = title
                if priority: upd["priority"] = priority
                if deadline: upd["deadline"] = deadline
                if estimated_hours > 0: upd["estimated_hours"] = estimated_hours
                if actual_hours >= 0: upd["actual_hours"] = actual_hours
                if remaining_hours >= 0: upd["remaining_hours"] = remaining_hours
                if status: upd["status"] = status
                task = TaskService(session).update_task(task_id, TaskUpdate(**upd))
                return json.dumps(_task_dict(task))
            except TaskNotFoundError as e:
                return json.dumps({"error": "not_found", "detail": str(e)})
            except Exception as e:
                return json.dumps({"error": "error", "detail": str(e)})

    # ── Tool 4: calculate_deadline_feasibility ────────────────────────────────
    @server.tool(description=(
        "Analyse if a task can finish by its deadline. "
        "Returns: feasible, remaining_hours, usable hours, shortfall, explanation."
    ))
    async def calculate_deadline_feasibility(task_id: str, lost_hours_today: float = 0.0) -> str:
        from app.services.task_service import TaskService, TaskNotFoundError
        from app.services.feasibility import FeasibilityService
        with _db() as session:
            try:
                task = TaskService(session).get_task(task_id)
                settings = _settings(session)
                result = FeasibilityService(session).analyse_p1_feasibility(
                    task, settings, now=datetime.now(timezone.utc),
                    lost_hours_today=lost_hours_today,
                )
                return result.model_dump_json()
            except TaskNotFoundError as e:
                return json.dumps({"error": "not_found", "detail": str(e)})

    # ── Tool 5: generate_daily_plan ───────────────────────────────────────────
    @server.tool(description="Generate a daily schedule for all active tasks.")
    async def generate_daily_plan(days_ahead: int = 14, lost_hours_today: float = 0.0) -> str:
        from sqlmodel import select
        from app.models.task import Task
        from app.services.scheduler import SchedulerService
        with _db() as session:
            tasks = list(session.exec(select(Task)).all())
            settings = _settings(session)
            result = SchedulerService(
                session=session, settings=settings, tasks=tasks,
                now=datetime.now(timezone.utc),
                days_ahead=days_ahead, lost_hours_today=lost_hours_today,
            ).generate()
            return result.model_dump_json()

    # ── Tool 6: generate_recovery_plan ────────────────────────────────────────
    @server.tool(description=(
        "Generate a recovery plan (2–3 options) for a task. "
        "Returns proposal_id — use resolve_recovery_proposal to approve."
    ))
    async def generate_recovery_plan(task_id: str, lost_hours_today: float = 0.0) -> str:
        from app.services.task_service import TaskService, TaskNotFoundError
        from app.services.feasibility import FeasibilityService
        from app.services.recovery import RecoveryService
        with _db() as session:
            try:
                task = TaskService(session).get_task(task_id)
                settings = _settings(session)
                now = datetime.now(timezone.utc)
                feasibility = FeasibilityService(session).analyse_p1_feasibility(
                    task, settings, now=now, lost_hours_today=lost_hours_today,
                )
                proposal = RecoveryService(session).generate_recovery_plan(
                    feasibility, settings, now=now
                )
                return proposal.model_dump_json()
            except TaskNotFoundError as e:
                return json.dumps({"error": "not_found", "detail": str(e)})

    # ── Tool 7: record_task_completion ────────────────────────────────────────
    @server.tool(description="Record a task as completed with actual hours. Updates estimates.")
    async def record_task_completion(task_id: str, actual_hours: float) -> str:
        from app.services.estimator import EstimatorService
        from app.services.task_service import TaskNotFoundError
        with _db() as session:
            try:
                return json.dumps(EstimatorService(session).record_completion(task_id, actual_hours))
            except TaskNotFoundError as e:
                return json.dumps({"error": "not_found", "detail": str(e)})

    # ── Tool 8: update_duration_estimate ──────────────────────────────────────
    @server.tool(description="Get category duration ratio (actual/estimated). Needs ≥3 completions.")
    async def update_duration_estimate(category: str) -> str:
        from app.services.estimator import EstimatorService
        with _db() as session:
            return json.dumps(EstimatorService(session).category_ratio(category))

    # ── Tool 9: resolve_recovery_proposal ────────────────────────────────────
    @server.tool(description=(
        "Accept or reject a recovery proposal. "
        "REJECT changes nothing (tested). "
        "ACCEPT applies the chosen option. action: 'accept'|'reject'."
    ))
    async def resolve_recovery_proposal(
        proposal_id: str,
        action: str,
        option_index: int = -1,
    ) -> str:
        from app.services.recovery import RecoveryService
        with _db() as session:
            try:
                idx = option_index if option_index >= 0 else None
                result = RecoveryService(session).resolve_proposal(
                    proposal_id=proposal_id, action=action, option_index=idx,
                )
                return result.model_dump_json()
            except KeyError as e:
                return json.dumps({"error": "not_found", "detail": str(e)})
            except ValueError as e:
                return json.dumps({"error": "invalid_argument", "detail": str(e)})

    return server


# ── Singleton ─────────────────────────────────────────────────────────────────

def create_mcp_asgi_app() -> Starlette:
    """
    Create a fresh Starlette ASGI app for the MCP Streamable HTTP endpoint.

    IMPORTANT: streamable_http_path="/" because this app is mounted
    under /mcp by FastAPI. Starlette strips the mount prefix, so the
    internal route must be "/" not "/mcp".

    stateless_http=True + json_response=True → plain JSON responses (no SSE),
    no persistent sessions required — ideal for a browser fetch() client.
    """
    from mcp.server.transport_security import TransportSecuritySettings

    server = _build()
    sec = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    asgi_app = server.streamable_http_app(
        streamable_http_path="/",   # mounted at /mcp → internal path is /
        json_response=True,         # plain JSON — no SSE needed in browser client
        stateless_http=True,        # no persistent session state per connection
        transport_security=sec,     # allow localhost, testserver, tunnels
    )
    logger.info("MCP ASGI app created (stateless JSON mode, Streamable HTTP)")
    return asgi_app


_mcp_asgi_app: Optional[Starlette] = None


def get_mcp_asgi_app() -> Starlette:
    """Singleton getter for backwards compatibility."""
    global _mcp_asgi_app
    if _mcp_asgi_app is None:
        _mcp_asgi_app = create_mcp_asgi_app()
    return _mcp_asgi_app


# ── Lifespan helper for main.py ───────────────────────────────────────────────

@asynccontextmanager
async def mcp_lifespan(asgi_app: Optional[Starlette] = None) -> AsyncIterator[None]:
    """Ensure MCP ASGI app and its session manager are running during FastAPI startup."""
    app = asgi_app or get_mcp_asgi_app()
    sm = app.routes[0].app.session_manager
    async with sm.run():
        logger.info("MCP Streamable HTTP server & session manager ready at /mcp")
        yield
    logger.info("MCP server shutdown.")


# ── DB helpers ────────────────────────────────────────────────────────────────

@contextmanager
def _db():
    from sqlmodel import Session
    with Session(get_engine()) as s:
        yield s


def _settings(session) -> UserSettings:
    from app.config import get_settings as _cfg
    s = session.get(UserSettings, 1)
    if s is None:
        s = UserSettings(timezone=_cfg().default_timezone)
        session.add(s); session.commit(); session.refresh(s)
    return s


def _task_dict(task) -> dict:
    return {
        "id": task.id, "title": task.title, "description": task.description,
        "category": task.category, "priority": task.priority,
        "deadline": task.deadline, "estimated_hours": task.estimated_hours,
        "actual_hours": task.actual_hours, "remaining_hours": task.remaining_hours,
        "status": task.status, "depends_on": task.depends_on,
        "splittable": task.splittable, "confidence": task.confidence,
        "created_at": task.created_at, "updated_at": task.updated_at,
    }
