"""
FastAPI application entry point — with MCP server mounted at /mcp.

MCP integration (Milestone 4):
  - MCPServer built from mcp.server.mcpserver (mcp 2.3.0)
  - streamable_http_app(path="/") creates ASGI sub-app, mounted at /mcp
  - Starlette strips /mcp prefix, internal route at "/" receives request
  - Bearer token validated by MCPBearerMiddleware before /mcp handler
  - Trailing-slash redirect handled via route registration
  - notifications/initialized and MCP-Protocol-Version forwarded as-is by client
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import get_settings
from app.database import get_engine, init_db
from app.routers import plans, recovery, settings, tasks

logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_settings()
    engine = get_engine()
    init_db(engine)

    if cfg.mcp_bearer_token:
        logger.info(
            "MCP bearer token configured (length %d). "
            "Requests to /mcp must include: Authorization: Bearer <token>",
            len(cfg.mcp_bearer_token),
        )
    else:
        logger.warning("MCP_BEARER_TOKEN not set — /mcp endpoint UNPROTECTED.")

    # MCP session manager lifecycle
    from app.mcp.server import mcp_lifespan
    mcp_app = getattr(app.state, "mcp_asgi_app", None)
    async with mcp_lifespan(mcp_app):
        logger.info("RealityCheck started — REST at /api/*, MCP at /mcp")
        yield

    logger.info("RealityCheck shutdown complete.")


# ── Bearer-token middleware for /mcp ─────────────────────────────────────────

class MCPBearerMiddleware(BaseHTTPMiddleware):
    """
    Validates Authorization: Bearer <token> on all /mcp/* requests.
    Returns 401 JSON if missing or invalid.
    Does NOT affect /api/* or other routes.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path.rstrip("/")
        if path == "/mcp" or path.startswith("/mcp/"):
            cfg = get_settings()
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer ") or auth[7:] != cfg.mcp_bearer_token:
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "Unauthorized",
                        "detail": (
                            "A valid Bearer token is required for the /mcp endpoint. "
                            "Set MCP_BEARER_TOKEN in .env and pass "
                            "Authorization: Bearer <token> in your request."
                        ),
                    },
                    headers={"WWW-Authenticate": "Bearer"},
                )
            # Normalize /mcp to /mcp/ to prevent 307 temporary redirect
            if request.scope.get("path") == "/mcp":
                request.scope["path"] = "/mcp/"

            # Ensure Accept header includes application/json to satisfy MCP SDK content negotiation
            accept = request.headers.get("accept", "")
            if not accept or "*/*" in accept or "application/json" not in accept:
                headers = [h for h in request.scope.get("headers", []) if h[0].lower() != b"accept"]
                headers.append((b"accept", b"application/json, text/event-stream, */*"))
                request.scope["headers"] = headers

            response = await call_next(request)
            response.headers["MCP-Protocol-Version"] = "2025-11-25"
            return response
        return await call_next(request)


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="RealityCheck",
        description=(
            "Deadline-recovery planner with MCP integration.\n\n"
            "**MCP endpoint:** `POST /mcp` — requires `Authorization: Bearer <MCP_BEARER_TOKEN>`\n"
            "**Protocol:** Streamable HTTP, MCP spec 2025-11-25\n"
            "**Assistant simulation:** Browser-based at the frontend /assistant page."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=[
            "*",
            "Mcp-Session-Id",
            "Mcp-Protocol-Version",
            "Authorization",
        ],
        expose_headers=["Mcp-Session-Id", "Mcp-Protocol-Version"],
    )

    # ── Bearer auth for /mcp ──────────────────────────────────────────────────
    app.add_middleware(MCPBearerMiddleware)

    # ── REST routers ──────────────────────────────────────────────────────────
    app.include_router(tasks.router,    prefix="/api/tasks",    tags=["tasks"])
    app.include_router(plans.router,    prefix="/api/plans",    tags=["plans"])
    app.include_router(recovery.router, prefix="/api/recovery", tags=["recovery"])
    app.include_router(settings.router, prefix="/api/settings", tags=["settings"])

    # ── MCP endpoint (Streamable HTTP) ────────────────────────────────────────
    # The MCP ASGI app is a Starlette sub-application with internal route at "/".
    # Mounting at "/mcp" makes Starlette strip the prefix before dispatching,
    # so POST /mcp → internal handler at "/".
    from app.mcp.server import create_mcp_asgi_app
    mcp_asgi = create_mcp_asgi_app()
    app.state.mcp_asgi_app = mcp_asgi
    app.mount("/mcp", mcp_asgi)

    # ── Health ────────────────────────────────────────────────────────────────
    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok", "service": "RealityCheck", "version": "0.1.0"}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    cfg = get_settings()
    uvicorn.run("app.main:app", host=cfg.api_host, port=cfg.api_port, reload=cfg.app_debug)
