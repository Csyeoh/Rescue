# GEMINI_CHANGELOG

## [2026-03-22]

### GEMINI.md
- Added frontend structure and styling documentation.

### globals.css
- Refined theme variables and base styles.
- Added custom scrollbar and resize handle styles.
- Standardized typography and palette.

### App Layout (src/app/page.tsx)
- Implemented log height state and resizability logic.
- Added smooth view transitions with `AnimatePresence`.
- Refactored ConfigPage to be full-page and animated.

### Configuration Page (src/components/Config/ConfigPage.tsx)
- Redesigned as a full-page dashboard layout.
- Removed excessive uppercase and improved grouping of parameters.
- Added motion transitions and full-screen responsive layout.
- **Validation:** Enforced new survivor input range (5-20) and drone count (3-5).

### Mission Log Panel (src/components/MissionLog/MissionLogPanel.tsx)
- Implemented a draggable resize handle at the top.
- Used `framer-motion` for log entry animations.
- Refined typography and spacing for better readability.

### Layout Components (src/components/Layout/*)
- **Header:** Softened styling, added motion progress bars, and removed excessive uppercase.
- **SidebarConfig:** Improved button interactions and parameter grouping.
- **SwarmStatusPanel:** Implemented smooth expansion/collapse with `framer-motion`.

### Drone Components (src/components/Drone/DroneCard.tsx)
- Enhanced telemetry visualization with smoother battery/status transitions.
- Added `framer-motion` layout animations.

### Map Components (src/components/Map/*)
- **GridCell:** Refined tooltips and indicator animations.
- **MapContainer:** Cleaned up headers and legend with modern styling.

### Map Generation (rescue_swarm_sim/prompts/map_builder.py)
- Overhauled `MAP_BUILDER_PROMPT` with Expert Urban Planner logic.
- Implemented sparse distribution targets (15-25% coverage).
- Added explicit road network/corridor requirements for structured layouts.
- Defined scenario-specific placement rules (Avenues for Downtown, Yards for Suburban).
- Added "Mountain Outpost" scenario focused on topographic alignment.

### Swarm Orchestration & Tactical Overhaul
- **Mesa Simulation:** Implemented batch intent execution in `step()`, +2% autonomous charging, and fatal collision logic.
- **State Bridge:** Added `live_state.db` synchronization to allow external MCP processes to access simulation memory.
- **MCP Server:** Refactored tools to be process-independent by reading directly from SQLite.
- **Battery Safety:** Standardized battery buffer to 10% and updated `check_task_viability` to use A* pathfinding.
- **Strict Protocols:** Enforced "Scan-before-Move" interlock and "One-Step" non-diagonal movement rules.
- **Mission Tracking:** Added `mission_failed` state triggered when ANY drone unit is lost.
- **WebSocket:** Migrated to trigger-based UI updates (broadcast only after `step`) and removed periodic background tasks.

### Real-time Agent Monitoring
- **CrewAI Hooks:** Implemented `after_llm_call`, `before_tool_call`, and `after_tool_call` to capture internal agent logic.
- **Live Brain Feed:** Agent reasoning and tool interactions are now broadcast via WebSocket and rendered in the Mission Log.
- **Precise Attribution:** Each log entry is now correctly attributed to the specific drone ID (e.g., drone_1) instead of a generic role.
- **UI Feedback Loop:** Integrated `agent_log` message type in the frontend for immediate visual feedback of swarm intelligence.

### UI & Configuration
- **Randomization:** Updated `generateRandomMap` to randomize survivors (5-20) and drone count (3-5) in `useMissionControl.ts`.
- **Animations:** Implemented high-fidelity "AI Mapping" loading overlay in `ConfigPage`.
- **Button Polish:** Added pulsing "Generating..." text and spinning loader icons to all generation buttons for improved feedback.

## [2026-03-23]

### Map Multi-Agent Rendering
- **GridCell (src/components/Map/GridCell.tsx):** Replaced boolean `isDroneHere` prop with `dronesHere` array. Updated rendering logic to place multiple agent indicators (survivors and drones) into a `flex-wrap` container within the cell, scaled down slightly, to allow coexistence without overlapping.
- **MapContainer (src/components/Map/MapContainer.tsx):** Updated mapping logic to pass filtered `dronesHere` array for each cell instead of a single boolean.

### Progressive Map Reveal (Fog of War)
- **GridCell (src/components/Map/GridCell.tsx):** Changed unrevealed background color to a neutral Slate-400 grey. Removed the teal "Fog of War" overlay to allow the grey background to represent unmapped areas cleanly.
- **Map Utils (src/utils/map-utils.ts):** Updated `buildGridFromMapData` to initialize cells with `revealed: false` by default, except for the base station which remains always visible.
- **WebSocket Hook (src/hooks/useWebSocket.ts):** Refactored `tick_update` to remove the bulk-reveal of all cells. Implemented progressive discovery logic where drones reveal their current position and immediate surroundings (4-way adjacency) as they move. Added logic to reveal cells containing rescued survivors.

### Strict Map Reveal & Swarm Detail Tooltips
- **GridCell (src/components/Map/GridCell.tsx):** Simplified drone rendering to a single blue dot per cell, regardless of the number of drones present. Added a detailed section to the hover tooltip that lists all active drone IDs within that cell.
- **WebSocket Hook (src/hooks/useWebSocket.ts):** Refined the discovery logic to be strictly "one-by-one". Now, only the cell explicitly occupied by a drone is marked as `revealed: true`. Surrounding cells are illuminated but remain unrevealed until a drone moves onto them. Removed automatic revelation from the `map_updates` stream to ensure discovery is driven solely by drone presence.

### Realistic Discovery & Thermal Aura Management
- **Simulation (rescue_swarm_sim/simulation.py):**
  - Added `revealed` attribute to `CellAgent` and synchronized it with the SQLite database.
  - Implemented `update_thermal_auras()` to dynamically recalculate thermal signals based on remaining unfound survivors.
  - Enhanced `step()` to support multi-cell discovery and adjacent survivor detection (N, S, E, W, and Current) for both `move` and `scan` actions.
- **MCP Server (rescue_swarm_sim/swarm_flow/crews/rescue_crew/mcp_server.py):**
  - Updated `thermal_scan` to mark 5 cells (current + neighbors) as `revealed` in the database.
  - Added logic to "wipe out" coordinates from `thermal_memory` once the associated thermal aura has been cleared (survivor found).
- **Frontend (rescue-ui/src/hooks/useWebSocket.ts):**
  - Integrated `revealed` and `thermal_aura` states from the backend payload.
  - Replaced manual client-side discovery logic with authoritative backend-driven revelation.
- **UI (rescue-ui/src/components/Map/GridCell.tsx):**
  - Added a subtle pulsing orange indicator for cells with an active `thermal_aura`.

### Dynamic Dispatch & Sector Assignment
- **Orchestration (rescue_swarm_sim/swarm_flow/main.py):** Replaced the static, heavy up-front partitioning with a dynamic, LLM-driven `swarm_dispatcher` agent. The dispatcher runs at the start of each tick to assign optimal search sectors (bounding boxes) to IDLE drones.
- **Simulation (rescue_swarm_sim/simulation.py):** Migrated from `priority_list` to `assigned_sector` in the `drones` table and `DroneAgent` class. Updated synchronization logic to persist sectors. Fixed a bug where obstacles were not being correctly discovered during scans.
- **MCP Server (rescue_swarm_sim/swarm_flow/crews/rescue_crew/mcp_server.py):**
  - Added `get_unexplored_clusters()` to identify high-priority building zones for the dispatcher.
  - Added `assign_sector()` and `get_next_sector_step()` to manage autonomous sector sweeping.
  - Simplified drone tools to support the "Thermal Override" pattern, where drones prioritize heat signatures over their assigned sector.
- **Agent Protocols (rescue_swarm_sim/swarm_flow/crews/rescue_crew/config/):**
  - **agents.yaml:** Defined the `Tactical Swarm Dispatcher` role with reasoning capabilities for high-priority building searches.
  - **tasks.yaml:** Implemented the `dispatch_task` and updated `searching_task` to strictly follow the Heat Override -> Sector Sweep hierarchy.
- **Cleanup:** Removed obsolete `partition.py` and `zone_partitioner.py` logic. Created `state_reader.py` for clean UI state reporting.

### Agent-Driven Dynamic Cell Allocation
- **Database (rescue_swarm_sim/simulation.py):** Added `assigned_to` column to the `cells` table to prevent overlapping assignments. Implemented logic to clear assignments as soon as a cell is revealed.
- **MCP Tools (rescue_swarm_sim/swarm_flow/crews/rescue_crew/mcp_server.py):**
  - **`get_global_mission_state`:** Provides the Dispatcher with a compact list of all unrevealed cells (including ground truth type and current assignment) and all drone positions.
  - **`allocate_drone_sector`:** Allows the agent to manually commit a list of coordinates to a drone's search queue.
  - **`get_next_sector_step`:** Optimized to find the *nearest* unrevealed coordinate within the drone's assigned set.
- **Mission Flow (rescue_swarm_sim/swarm_flow/main.py):** Integrated a smart pre-check that only invokes the Tactical Dispatcher if there are IDLE drones in the swarm, reducing latency and token usage.
- **Swarm Intelligence (rescue_swarm_sim/swarm_flow/crews/rescue_crew/config/):**
  - **agents.yaml:** Updated Dispatcher backstory to emphasize the "Outdoor Phase" transition once building clusters are cleared.
  - **tasks.yaml:** Simplified drone search tasks to focus on coordinate list execution while maintaining the Thermal Override reflex.

### Mission Log Export
- **Simulation (`rescue_swarm_sim/simulation.py`):** Added `step_logs` variable to track coordinates, status, sector, and target cells for every step of each drone. Added `generate_log_file` function to export data to `log file.txt` upon simulation completion.
- **API (`rescue_swarm_sim/api.py`):** Called `generate_log_file()` inside `abort_mission` endpoint to ensure log data is saved even when the mission is artificially terminated.

### Bug Fixes
- **Drone Intents (`rescue_swarm_sim/swarm_flow/crews/rescue_crew/rescue_crew.py`):** Updated `DroneIntent` Pydantic model to use `int | None` for `x` and `y` coordinates. This ensures the mission doesn't crash if an agent provides `null` coordinates during non-movement tasks like `IDLE` or `CHARGING`.
- **MCP Server (`rescue_swarm_sim/swarm_flow/crews/rescue_crew/mcp_server.py`):** Implemented comprehensive safety checks for `json.loads` calls. Fixed a critical `TypeError: object of type 'NoneType' has no len()` by ensuring `assigned_sector` and `thermal_memory` default to empty lists when their database values are `null` or empty. This prevents tool crashes during the mission dispatch and search phases.
- **CrewAI Flows (`rescue_swarm_sim/swarm_flow/main.py`):** Refactored the mission lifecycle from a fragile `@router` pattern to a robust `@listen` state-loop. Implemented explicit state persistence for `current_intents` within `SwarmMissionState` to ensure reliable handoffs between gathering and executing intents.
- **Agent Intelligence (`rescue_swarm_sim/swarm_flow/crews/rescue_crew/config/`):**
  - **`agents.yaml`:** Updated drone backstory with "Optimized Charging" protocols, granting agents agency to evaluate mission urgency vs. battery safety.
  - **tasks.yaml:** Enhanced `charging_task` to require a tactical evaluation of the global map state. Drones can now autonomously decide to resume searching at >40% battery if critical building clusters remain unrevealed, optimizing total mission duration.

  ## [2026-03-25] - Agent Reasoning & Tool Execution Logs

  - **Backend:** Updated `rescue_swarm_sim/swarm_flow/crews/rescue_crew/reasoning_logger.py` to broadcast `AgentReasoningCompletedEvent` and `MCPToolExecutionCompletedEvent` to the frontend via WebSockets.
  - **Frontend Types:** Extended `LogEntry` in `rescue-ui/src/types/index.ts` to include a `details` field for capturing structured reasoning plans and tool execution data. Improved type safety by replacing `any` with `unknown` and `Record<string, unknown>`.
  - **Frontend Logic:** Updated `useMissionControl.ts` and `useWebSocket.ts` to handle, store, and type-check these new event types and their payloads.
  - **Frontend UI:** Enhanced `MissionLogPanel.tsx` to render detailed sub-panels for agent plans and tool execution results, including JSON arguments and execution durations, using a nested, responsive layout.
