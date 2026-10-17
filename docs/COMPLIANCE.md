# RealityCheck — Alexa+ Track Compliance & Protocol Audit

**Build, Ship, Shape: Amazon Developer Hackathon 2026**  
**Track:** Alexa+  
**Target Specification:** Model Context Protocol (MCP) Streamable HTTP — Spec Version `2025-11-25`  
**Evaluation Date:** October 16, 2026  
**Auditor Status:** Senior Full-Stack Engineer / Hackathon Mentor  

---

## 1. Compliance Matrix

Legend:
- ✅ **VERIFIED & TESTED** — Passing automated test suite in `backend/tests/test_mcp_integration.py`
- ⚠️ **SIMULATED BY DESIGN** — Polished in-browser MCP client simulation; explicitly labeled as simulation
- 🔒 **PARTNER-GATED / UNVERIFIED** — Requires private Amazon developer partnership credentials

| # | Requirement | Status | Evidence / Reference URL | Read Date | Verification Test |
|---|---|:---:|---|---|---|
| 1 | Official Python MCP SDK | ✅ | `mcp==2.3.0` installed from PyPI. SDK migration reference: https://py.sdk.modelcontextprotocol.io/v2/migration/#fastmcp-renamed-to-mcpserver | 2026-10-16 | `backend/tests/test_mcp_integration.py` |
| 2 | Streamable HTTP (Not legacy SSE) | ✅ | `MCPServer.streamable_http_app(json_response=True, stateless_http=True)`. Specification reference: https://spec.modelcontextprotocol.io/specification/2025-11-25/basic/transports/#streamable-http | 2026-10-16 | `test_mcp_initialize`, `test_mcp_trailing_slash_normalization` |
| 3 | Target Spec `2025-11-25` or later | ✅ | MCP protocol handshake negotiates `protocolVersion: "2025-11-25"`. Header `MCP-Protocol-Version: 2025-11-25` emitted on all `/mcp` responses. | 2026-10-16 | `test_mcp_initialize` |
| 4 | Real App Tools via MCP (9 tools) | ✅ | All 9 tools (`create_task`, `list_tasks`, `update_task`, `calculate_deadline_feasibility`, `generate_daily_plan`, `generate_recovery_plan`, `record_task_completion`, `update_duration_estimate`, `resolve_recovery_proposal`) call shared service layer and database. | 2026-10-16 | `test_mcp_tools_list_returns_9_tools`, `test_mcp_tool_create_and_list_tasks` |
| 5 | Browser-based MCP Client | ✅ | `frontend/src/api/mcpClient.ts` performs real JSON-RPC over Streamable HTTP: `initialize` -> `notifications/initialized` -> `tools/list` -> `tools/call`. | 2026-10-16 | `npm run build`, verified in browser integration |
| 6 | Natural-Language Mapping | ✅ | `frontend/src/intent/intentRouter.ts` maps phrases directly to real MCP tool calls. Structured results returned from SQLite database & deterministic scheduling engine. | 2026-10-16 | `test_mcp_tool_calculate_deadline_feasibility` |
| 7 | Simulation vs Production Distinction | ✅ | Persistent UI pill and disclaimer: *"RealityCheck MCP Simulation — Not an official Alexa+ hardware connection"*. No fake claims of store certification. | 2026-10-16 | Visual verification in `frontend/src/pages/AssistantSimulation.tsx` |
| 8 | Bearer Token Authentication | ✅ | Middleware enforces `Authorization: Bearer <token>` from `.env`. Missing or invalid tokens return 401 with `WWW-Authenticate: Bearer`. | 2026-10-16 | `test_mcp_unauthorized_missing_token`, `test_mcp_unauthorized_invalid_token` |
| 9 | Recovery Proposal Reject Safety | ✅ | `resolve_recovery_proposal(proposal_id, 'reject')` leaves all database tasks unchanged. | 2026-10-16 | `test_mcp_tool_recovery_plan_and_reject_safety`, Scenario Test 9 |
| 10 | Duration Estimator 3-Sample Threshold | ✅ | `update_duration_estimate` enforces $\ge 3$ completed tasks in category before activating duration adjustment. | 2026-10-16 | `test_mcp_tool_duration_estimate_threshold` |
| 11 | Production Alexa+ Add-on Certification | 🔒 | UNVERIFIED / PARTNER-GATED. Public developer portal requires Alexa+ Developer Preview approval and Amazon Developer Account linking. | 2026-10-16 | Documented in `docs/ALEXA_PLUS_INVESTIGATION.md` |

---

## 2. Official Documentation URLs & Read Dates

1. **Model Context Protocol Specification (Version 2025-11-25):**  
   URL: `https://spec.modelcontextprotocol.io/specification/2025-11-25/`  
   Read Date: 2026-10-16  
   Key Details: Specifies Streamable HTTP request format, JSON-RPC 2.0 frames, header requirements, notification delivery, and error envelopes.

2. **Official Python MCP SDK Migration Guide (v2.x):**  
   URL: `https://py.sdk.modelcontextprotocol.io/v2/migration/#fastmcp-renamed-to-mcpserver`  
   Read Date: 2026-10-16  
   Key Details: FastMCP was renamed to MCPServer in `mcp 2.x`. Demonstrates `@server.tool()` decorators and `streamable_http_app()`.

3. **Amazon Alexa Developer Documentation:**  
   URL: `https://developer.amazon.com/en-US/docs/alexa`  
   Read Date: 2026-10-16  
   Status: Public quickstarts review standard Smart Home / Custom Skill SDK. Alexa+ MCP runtime registration is partner-gated under NDA preview.
