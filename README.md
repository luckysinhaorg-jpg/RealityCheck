# RealityCheck ⏱️

> **Know what matters, know how much time it really needs, and know what must change to finish on time.**

Built for the **Build, Ship, Shape: Amazon Developer Hackathon 2026** — *Alexa+ Track*.

---

## 🚀 Overview

**RealityCheck** is a deterministic deadline-recovery planner with an integrated **Model Context Protocol (MCP)** server and browser-based client simulation. 

When you fall behind or lose working hours, RealityCheck evaluates your entire portfolio, proves whether your Priority 1 deadline is mathematically feasible, and generates actionable recovery proposals with clear trade-offs — **never modifying your database without explicit user approval**.

Crucially, **RealityCheck does not trust an LLM for calendar math, time arithmetic, scheduling, or database integrity.** All scheduling logic is 100% deterministic pure Python.

---

## 🛠️ Technology Stack

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| **Backend API** | Python / FastAPI | 3.14.1 / 0.143 | REST endpoints & ASGI application |
| **Database** | SQLite + SQLModel (SQLAlchemy) | 0.0.48 | Persistent task & proposal storage (WAL mode) |
| **MCP Protocol** | Official Python MCP SDK (`mcp`) | 2.3.0 | Streamable HTTP server (spec `2025-11-25`) |
| **Scheduler** | Pure Deterministic Python | — | Priority protection, break rules, buffer calculation |
| **Frontend** | React + TypeScript + Vite | 19.2 / 8.3 | Dashboard, Timetable, & Conversational Simulation |
| **Test Suite** | pytest + anyio | 9.1.1 / 4.15 | 74 comprehensive unit & integration tests |

---

## 🏗️ Architecture

```mermaid
flowchart TD
    subgraph Browser ["Web Client (React + TS)"]
        UI["Dashboard & Timetable\nPriority Analysis\nRecovery Center"]
        MCPClient["MCP Client Simulation\n(Streamable HTTP 2025-11-25)"]
        IntentRouter["Deterministic Intent Router\n(No LLM Math)"]
    end

    subgraph Backend ["RealityCheck Backend (FastAPI)"]
        AuthMiddleware["MCP Bearer Auth Middleware\n(Authorization: Bearer <token>)"]
        MCPServer["MCPServer Sub-Application\n(Mounted at /mcp)"]
        RestRouters["FastAPI REST Routers\n(/api/tasks, /api/plans, etc.)"]
        
        subgraph Engine ["Deterministic Logic Engine"]
            Avail["Availability Calculator\n(Breaks & Buffers)"]
            Feas["Feasibility Service\n(P1 Proof & Validator)"]
            Sched["Portfolio Scheduler\n(Dependencies & Sessions)"]
            Recov["Recovery Engine\n(Multi-Option Proposals)"]
            Estim["Duration Estimator\n(>=3 Completion Threshold)"]
        end

        DB[(SQLite Database\nWAL Mode)]
    end

    UI -->|HTTP REST| RestRouters
    MCPClient -->|POST /mcp (JSON-RPC)| AuthMiddleware
    AuthMiddleware --> MCPServer
    IntentRouter --> MCPClient

    RestRouters --> Engine
    MCPServer --> Engine
    Engine --> DB
```

---

## 🔧 MCP Tools (All 9 Implemented & Tested)

RealityCheck exposes its entire scheduling engine through real MCP tools calling shared database models:

1. `create_task` — Create a new task with deadlines, estimates, dependencies, and priorities.
2. `list_tasks` — List and filter active tasks by priority, category, or status.
3. `update_task` — Update task estimates, status, or deadlines.
4. `calculate_deadline_feasibility` — Analyze whether a task can complete on time with exact mathematical proofs.
5. `generate_daily_plan` — Deterministically schedule work sessions honoring priority and working windows.
6. `generate_recovery_plan` — Generate 2–3 recovery options when time is lost or deadlines conflict.
7. `record_task_completion` — Log actual completion hours and update historical category ratios.
8. `update_duration_estimate` — Calculate category duration ratios (enforces $\ge 3$ sample threshold).
9. `resolve_recovery_proposal` — Explicitly accept or reject a recovery proposal (**reject provably changes nothing**).

---

## 🧪 Test Results (74/74 Passing)

Run the full automated test suite:

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/ -v
```

```
collected 74 items

backend/tests/test_api.py ......................                         [ 29%]
backend/tests/test_availability.py ..........                            [ 43%]
backend/tests/test_mcp_integration.py ..........                         [ 56%]
backend/tests/test_scenarios.py ...................                      [ 82%]
backend/tests/test_task_service.py .............                         [100%]

============================= 74 passed in 3.78s ==============================
```

All 10 required hackathon scenarios are covered:
- Scenario 1: Everything fits.
- Scenario 2: Priority 1 feasible only if other tasks move.
- Scenario 3: Priority 1 is impossible.
- Scenario 4: Two conflicting Priority 1 deadlines.
- Scenario 5: Task overruns estimate.
- Scenario 6: Lost working hours.
- Scenario 7: Unfinished dependency blocks work.
- Scenario 8: New urgent task inserted.
- Scenario 9: Rejected recovery plan causes zero changes.
- Scenario 10: Changed availability triggers recalculation.

---

## ⚡ Quick Start & Run Instructions

### 1. Backend Setup

```powershell
# Navigate to backend
cd backend

# Create & activate Python virtual environment
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Seed the database with realistic hackathon sample data
python seed.py

# Launch the FastAPI + MCP server (runs on http://127.0.0.1:8000)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Frontend Setup

In a separate terminal:

```powershell
# Navigate to frontend
cd frontend

# Install npm dependencies
npm install

# Start Vite development server (runs on http://localhost:5173)
npm run dev
```

Visit **`http://localhost:5173`** to access:
- **Dashboard & Timetable:** View portfolio workload, schedule sessions, and simulate lost hours.
- **All Tasks:** Inventory with completion logging and dependency views.
- **Priority Analysis:** Exact mathematical proof of deadline feasibility.
- **Recovery Center:** Multi-option proposals with Accept / Reject safety.
- **MCP Assistant Simulation:** Conversational interface making real MCP protocol calls over Streamable HTTP!

---

## 🌐 Remote HTTPS Access (Cloudflare Tunnel)

For remote testing or Alexa testbench access:

```powershell
# Run free temporary tunnel to local backend
cloudflared tunnel --url http://127.0.0.1:8000
```

Use the generated URL (e.g. `https://<tunnel-id>.trycloudflare.com/mcp`) with header `Authorization: Bearer rc_alexa_dev_token_2026_streamable_http`.

---

## 📄 License & Attribution

Built for the **Build, Ship, Shape: Amazon Developer Hackathon 2026**.  
See [`docs/COMPLIANCE.md`](docs/COMPLIANCE.md) for the official protocol audit and [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) for the 3-minute presentation script.
