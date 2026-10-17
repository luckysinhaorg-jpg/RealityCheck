# RealityCheck — 3-Minute Demo Rehearsal Script

**Build, Ship, Shape: Amazon Developer Hackathon 2026 — Alexa+ Track**

---

### Timing Breakdown
- **0:00 – 0:30:** The Problem & The RealityCheck Core Promise
- **0:30 – 1:15:** Dashboard & The Deterministic Timetable
- **1:15 – 2:30:** The Conversational MCP Assistant Simulation
- **2:30 – 3:00:** Architecture, Protocol Audit & 74 Passing Tests

---

### Step-by-Step Script

#### [0:00 - 0:30] Hook & Problem
> *"Hi judges, welcome to RealityCheck. Standard to-do apps tell you what you wanted to do, but they lie about whether you actually have the hours to do it. When you lose time or fall behind, they pile on guilt without giving you a path forward.*
>
> *RealityCheck is a deadline-recovery planner built for the Alexa+ Track. Our promise is simple: Know what matters, know how much time it really needs, and know what must change to finish on time. And crucially: our scheduling arithmetic is 100% deterministic pure Python. We never trust an LLM for calendar arithmetic or database integrity."*

#### [0:30 - 1:15] Dashboard & Priority 1 Focus
> *(Switch to Dashboard view)*
> *"Here on the dashboard, RealityCheck tracks our active portfolio. Right now, our centerpiece Priority 1 task is the 'CS5001 Final Exam Prep' with 16 remaining hours due in 5 days.*
>
> *Notice our deterministic timetable below: it reserves fixed working windows, deducts break rules, reserves a safety buffer, and places sessions by priority and dependency.*
>
> *(Drag the Lost Hours slider to 3 hours)*
> *Watch what happens when life happens: if I lose 3 hours today, the system immediately recalculates. It warns us that our Priority 1 task is now INFEASIBLE with a 2.5-hour shortfall before the deadline."*

#### [1:15 - 2:30] Conversational MCP Assistant Simulation
> *(Click 'MCP Assistant Simulation' tab)*
> *"Now let's switch to our Conversational Assistant. This is not a simulated UI mock — this browser client is connected directly to our running backend MCP server over Streamable HTTP using the 2025-11-25 specification.*
>
> *(Click sample prompt: 'Can I finish my highest-priority task by Friday?')*
> *Notice what happens in real time: the user query is deterministically mapped to the `calculate_deadline_feasibility` tool. Look at the inspectable JSON-RPC frame: it called our Python engine, received the structured mathematical proof, and delivered an instant natural explanation.*
>
> *(Click sample prompt: 'I lost three hours today. Recalculate my plan.')*
> *Now let's recover: the assistant calls `generate_recovery_plan`. It returns two concrete options: Option 1 moves our lower-priority Architecture Review to free up hours; Option 2 negotiates a deadline.*
>
> *(Click 'Reject All (Change Nothing)')*
> *Notice rule #9 in action: when the user rejects the proposal, zero tasks in the database are modified. Total safety.*
>
> *(Click 'Accept Option 1')*
> *When we accept Option 1, the proposal is resolved, the lower-priority work is safely deferred, and our Priority 1 task is fully protected!"*

#### [2:30 - 3:00] Technical Wrap-Up
> *"Under the hood:*
> - *Official Python MCP SDK 2.3.0 running Streamable HTTP.*
> - *All 9 real application tools exposed and protected by Bearer token authentication.*
> - *74 automated tests passing across models, scheduling algorithms, and real MCP integration.*
>
> *RealityCheck gives users clarity, confidence, and a verifiable recovery plan when time is running out. Thank you!"*
