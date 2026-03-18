# AI Project Handoff — Rescue Swarm Simulator (First Responder of the Future)

This document is a comprehensive handover for the next AI assistant taking over `D:\Project\Rescue`.

## 1. Project Overview

**Hackathon goal (“First Responder of the Future”)**: simulate a multi-drone search-and-rescue mission where autonomous agents coordinate to explore a disaster zone, avoid obstacles, detect thermal “aura” signals near survivors, and confirm rescues via scans.

**Current end-to-end system (active path)**:
- **Backend**: FastAPI + Mesa simulation (`rescue_swarm_sim/`)
- **AI swarm logic**: CrewAI tasks per drone (`rescue_swarm_sim/swarm_flow/`)
- **MCP transport**: FastMCP HTTP server exposing tools; CrewAI connects over MCP HTTP to call tools (`rescue_swarm_sim/swarm_flow/crews/rescue_crew/mcp_server.py`)
- **Frontend**: Vite/React dashboard (`new_rescue_ui/`) connected via HTTP + WebSocket to the backend

**Important context**: this repo contains **two generations** of architecture:
- A **legacy DB-driven system** (SQLite `swarm_state.db`) under `rescue_swarm_sim/archive/` that is not currently wired into the running stack.
- The **current in-memory authoritative simulation** where Mesa state is the source of truth and the UI is updated via WebSocket events.

## 2. File Structure & Architecture

### Repository Top-Level
- `rescue_swarm_sim/`: Python backend + sim + AI loop
- `new_rescue_ui/`: current Vite/React UI (preferred)
- `rescue-ui/`: older Next.js UI (still present; can be used as fallback)
- `ARCHITECTURE_MAP.md`: high-level architecture notes (partially outdated vs current code paths)
- `.antigravityrules`: “always check ARCHITECTURE_MAP.md before changes”

### Backend & Simulation (Authoritative State)
Location: `rescue_swarm_sim/`
- `api.py`: FastAPI endpoints + mission start + MCP bridge endpoints + WS endpoint
- `simulation.py`: Mesa model (`DisasterZoneModel`) + agents + intent resolver
- `websocket_manager.py`: thread-safe WebSocket broadcast manager
- `map_generator.py` + `prompts/map_builder.py`: blueprint + terrain generation

### AI Swarm Control Loop (CrewAI)
Location: `rescue_swarm_sim/swarm_flow/`
- `main.py`: controller loop (partition, build per-drone tasks, kickoff CrewAI each tick)
- `tools/partition.py`: deterministic greedy BFS partitioner; assigns `priority_searching_list` to each drone
- `crews/rescue_crew/`
  - `rescue_crew.py`: LLM config + CrewAI agent creation + per-tick task building
  - `config/agents.yaml`: agent role/goals/backstory constraints
  - `config/tasks.yaml`: “SEARCHING/CHARGING/RETURNING/IDLE” task scripts and tool usage contract
  - `mcp_server.py`: FastMCP tool server (HTTP transport) used by CrewAI
  - `http_tools.py`: legacy fallback tools (non-MCP) (not primary path now)

### Frontends
- `new_rescue_ui/`: Vite React (current). Talks to backend:
  - HTTP: `/api/generate_map`, `/api/start_mission`
  - WS: `/ws` events: `partitioning_complete`, `tick_update`, `mission_complete`
- `rescue-ui/`: Next.js (older). Similar concept; can be used if needed.

### Legacy Database-Based Stack (Not Current Source of Truth)
Location: `rescue_swarm_sim/archive/`
- `database.py`: defines SQLite schema around `swarm_state.db`
- `flow.py`: old CrewAI Flow + DB reads/writes
- `ai_tools.py`: old “tools” layer writing to DB (explicitly notes A* not used anymore)
- `agent.py`, `autopilot.py`, `tasks.py`: older orchestrations/prompts

## 3. The AI Engine (CrewAI)

### Current, Active Agent (Search Drone)
**Single agent config**: `search_and_rescue_drone` in `swarm_flow/crews/rescue_crew/config/agents.yaml`
- Role: “Autonomous Edge-AI Search Pilot”
- Objective: explore assigned sector, prioritize thermal signals, avoid obstacles, obey battery safety threshold.
- State machine: `CHARGING`, `SEARCHING`, `RETURNING`, `IDLE`

**Task execution model**
- The controller loop in `swarm_flow/main.py` partitions the grid and then, each tick:
  - Builds one task per drone based on its current `status`
  - Runs CrewAI kickoff for all tasks (forced to synchronous execution per tick in `RescueCrew.crew()`).
- Tasks are defined as instruction scripts in `config/tasks.yaml`. They enforce “end your task by calling `localhost_9001_mcp_submit_intent`”.

### Terrain Analyst & Swarm Commander (Legacy / Not Actively Used)
The user-facing docs mention:
- **Terrain Analyst** (“Geospatial Data Analyst”)
- **Swarm Commander** (“Central Swarm Commander”)

These exist conceptually in legacy code:
- `rescue_swarm_sim/agents.py` defines `build_agents()` that creates these agents, but it imports `ai_tools` in a way that is not currently wired into the running system and appears to belong to an older DB-centric version.
- `rescue_swarm_sim/archive/flow.py` uses a commander-style narration step, writing reasoning to DB logs via `log_mission_reasoning_tool`.

**If you need these roles again**, you should decide whether to:
- Re-enable the DB-based pipeline in `archive/`, or
- Re-implement these roles against the current API/Mesa-authoritative state (recommended).

## 4. The MCP Bridge

### Current MCP Bridge (Active)
**MCP server**: `rescue_swarm_sim/swarm_flow/crews/rescue_crew/mcp_server.py`
- Runs FastMCP in HTTP transport mode (orchestrator starts it on port `9001`).
- Exposes tools like:
  - `check_battery`, `get_status`, `get_current_pos`
  - `get_next_waypoint` (top remaining waypoint)
  - `get_thermal_memory`
  - `scan_adjacent` (4-neighborhood sensing)
  - `step_towards` (backend computes valid next step)
  - `thermal_scan_preview`
  - `submit_intent` (posts intent to backend)
  - `get_distance_to_base`, `get_mission_data`

**CrewAI → MCP**: `rescue_swarm_sim/swarm_flow/crews/rescue_crew/rescue_crew.py`
- Uses `MCPServerHTTP(url="http://localhost:9001/mcp", streamable=True, cache_tools_list=True)` when `CREW_MCP_TRANSPORT=http`.

**MCP → Backend**:
- The MCP server calls FastAPI endpoints under `http://127.0.0.1:8000/api/mcp/...`
- Intent submission is POSTed to `/api/mcp/intent` (see below).

### Intent Application & WebSocket Updates
Backend: `rescue_swarm_sim/api.py`
- `POST /api/mcp/intent`: authoritative state update entry point for drone decisions.
  - Two modes:
    - `INTENT_APPLY_MODE=sequential` (default in current code): apply immediately
    - batch mode: buffer until all drones submit; auto-flush after `INTENT_BATCH_TIMEOUT_S`
- After applying intents, backend broadcasts a `tick_update` WebSocket payload including:
  - `drone_states`: positions, battery, status
  - `map_updates`: incremental cell updates
  - `events`: simulation events (WARN/BLOCKED/etc.)
  - `agent_logs`: the LLM rationale attached to each intent

### Pathfinding (Reality Check)
- The current `/api/mcp/drone/{drone_id}/step_towards` uses **grid BFS shortest-path** (not A*).
- Partitioning is a **deterministic greedy weighted BFS** (`swarm_flow/tools/partition.py`) that assigns each drone a prioritized list of coordinates (`priority_searching_list`).

### Battery Rules (Reality Check)
- **Actual drain in the Mesa sim**: `simulation.py` drains **1% battery per move** (`DroneAgent._apply_move()`).
- **Safety check used by tools**: `get_distance_to_base` returns `safe_to_continue = batt > dist + 5` (a 5% buffer above Manhattan distance).
- **Agent prompt claims “10% safety buffer”** (in `agents.yaml`), but code uses `+5`. This is currently inconsistent.

If “Bingo Fuel math” must be strictly 10% reserve, you should adjust `get_distance_to_base` (and any other battery safety logic) to match the policy, then update prompts to match.

### Important Fixes Recently Added in MCP Layer
The MCP tool `submit_intent` contains guardrails to reduce bad LLM tool calls:
- Converts status-like actions (`SEARCHING`, `CHARGING`, `RETURNING`) into a valid action + `new_status`
- Forces MOVE targets to be valid 1-step moves by coercing through `step_towards`
- Converts “MOVE to current cell” into `IDLE` to avoid clamp-driven random drift

## 5. Current State & Database

### Current Source of Truth (Active System)
There is **no SQLite database** in the active flow. No `*.db` file is present at repo root.

The source of truth is **in-memory Mesa state**:
- `simulation.sim_world`: global instance of `DisasterZoneModel`
- Drone state: position, battery, status (`DroneAgent`)
- Shared map memory:
  - `global_discovered_cells`: cells the mission has truly “visited/scanned” (used to filter remaining waypoints)
  - per-drone `thermal_memory`: cached thermal alert coordinates

The UI is updated via WebSocket broadcasts, not DB polling.

### Legacy DB (`swarm_state.db`) (Archive Only)
The DB-driven design exists under `rescue_swarm_sim/archive/`:
- `archive/database.py` defines schema and manages `swarm_state.db`.
- The tables include drones, question/answer plane, survivors, logs, waypoints, etc.
- This pipeline is not currently used by `rescue_swarm_sim/main.py` or `rescue_swarm_sim/api.py`.

If you must re-enable a DB “source of truth”, expect non-trivial reintegration work.

## 6. What Is Done vs. What Is Next

### Done (Recently Completed)
- **Rewired “new UI”**: `new_rescue_ui/` now behaves like the backend-driven dashboard (HTTP + WS); local simulation loop removed.
- **MCP transport stabilized**: moved to FastMCP HTTP server on port `9001` and CrewAI MCP HTTP client.
- **Authoritative intent application**: drones submit intents via `/api/mcp/intent`; backend applies and broadcasts `tick_update`.
- **Movement correctness guardrails**:
  - Simulation clamps illegal MOVE to a 1-step adjacent move.
  - MCP `submit_intent` coerces MOVE targets to 1-step via `step_towards`.
  - “MOVE to same cell” converts to IDLE to avoid random clamp drift.
- **Adjacent sensing added**:
  - Drones “sense” 4 adjacent cells for obstacle discovery and thermal/survivor signals.
  - Important fix: sensing no longer marks those cells as globally “visited”, so it does not erase waypoint queues.

### Immediate Next Steps (High-Leverage)
1. **Unify battery policy**:
   - Decide whether the true safety buffer is “+5” or “10% reserve”.
   - Update both the tool logic and the agent prompts to match.
2. **Reduce IDLE spam / enforce action schema**:
   - The agent still sometimes emits status as action; prompts help but may need tighter structured output enforcement.
3. **Improve search behavior**:
   - Current strategy is “thermal_memory first, otherwise waypoint list”.
   - Add logic to actively move toward adjacent thermal aura detection (not just log it).
4. **Frontend polish / stability**:
   - Confirm WebSocket reconnect behavior and “abort mission” behavior (currently not implemented; Ctrl+C backend stops all).

## 7. Instructions for the New AI (Strict)

You are taking over an AI-assisted disaster-response simulator. You must **not** invent rules that do not exist in code. When making changes:
- Treat the **Mesa simulation state** as authoritative unless the project is explicitly migrated back to a DB.
- Do not “cheat” by letting the agent know hidden obstacles/survivors; the UI has “god view” only for the human.
- Never break battery safety policy (“Bingo Fuel math”). If the policy is 10% reserve, enforce it everywhere consistently (tools + simulation + prompts).
- Ensure MOVE is always a **single-step move**; use `step_towards` to compute it.
- Any intent that changes the simulation must go through `/api/mcp/intent` (or a single authoritative equivalent).
- When unsure about what’s running, start from the orchestrator and validate with `/api/health` and WebSocket logs.

### How to Run (Current)
1. Backend (Python):
   - Create venv, install `rescue_swarm_sim/requirements.txt`
2. Frontend:
   - `cd new_rescue_ui && npm install`
3. Start everything:
   - `cd rescue_swarm_sim && python main.py`
4. Open:
   - UI: `http://localhost:3000`
   - API: `http://localhost:8000`

### Key Environment Variables (Common)
- `GEMINI_API_KEY` or `OPENROUTER_API_KEY` (cloud LLM)
- `USE_LOCAL_LLM=true`, `LOCAL_MODEL=ollama/llama3.1`, `OLLAMA_API_BASE=http://localhost:11434` (local LLM)
- `INTENT_APPLY_MODE=sequential|batch`
- `INTENT_BATCH_TIMEOUT_S=3.0`
- `SIM_TICK_S=1.0`, `CONTROLLER_TICK_S=1.0`
- `RESCUE_UI_PATH` (override UI folder if needed)

