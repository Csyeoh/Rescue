# Development Guide: Rescue Swarm Simulation

This document provides an overview of the `rescue_swarm_sim` backend architecture, folder structure, and best practices for development.

## 📁 Folder Structure

```text
rescue_swarm_sim/
├── api.py                # FastAPI backend (Mission Control API)
├── db.py                 # SQLite database layer (Shared State)
├── main.py               # Master entry point (Starts Backend + Frontend)
├── map_generator.py      # AI-powered map generation (Gemini)
├── simulation.py         # Mesa-based physics simulation
├── websocket_manager.py  # Real-time UI updates (WebSockets)
├── log.txt               # Centralized agent mission logs
├── archive/              # Obsolete or legacy files
├── prompts/              # System prompts for map building
└── swarm_flow/           # ADK Agent Orchestration
    ├── main.py           # The "Swarm Orchestration Loop" (Tick logic)
    ├── crews/            # Agent definitions and MCP tools
    │   └── rescue_crew/
    │       ├── rescue_crew.py           # Agent Factory (Persistence logic)
    │       ├── mcp_server_dispatcher.py # High-level coordination tools
    │       ├── mcp_server_drone.py      # Low-level tactical tools
    │       └── prompts/                 # Markdown-based agent instructions
    └── tools/            # Utilities for agents
        ├── ascii_map.py     # Grid-to-ASCII conversion for LLMs
        └── state_reader.py  # Grid-to-JSON conversion for UI
```

## 🛠️ Core Components

### 1. The Shared State (Source of Truth)
The system uses a SQLite database (`live_state.db`) as the bridge between the **Simulation** (Mesa) and the **Agents** (ADK).
- **Simulation**: Writes its state to the DB every tick.
- **MCP Tools**: Read from the DB to provide context to agents and write back "Intents" (e.g., `allocate_drone_sector`).
- **Sync Logic**: Found in `simulation.py` (`sync_to_db` and `step`).

### 2. ADK Swarm Orchestration
The orchestration loop in `swarm_flow/main.py` follows this sequence:
1. **Intelligence**: Dispatcher assesses the global map.
2. **Strategy**: Dispatcher allocates cells to IDLE drones.
3. **Tactics**: Drones execute moves in parallel based on their local maps.
4. **Physics**: The simulation applies moves and calculates collisions/discoveries.

### 3. MCP Toolsets
Tools are split into two servers to maintain separation of concerns:
- **Dispatcher Tools**: Focused on "God-View" reporting and sector allocation.
- **Drone Tools**: Focused on localized scanning, navigation steps, and battery checks.

### 4. Agent Persistence & Reuse
To improve performance and maintain consistent conversational state, agents are initialized only once within the `RescueCrew` factory.
- **Dispatcher**: Cached as `self._dispatcher_agent`.
- **Pilots**: Cached in a `self._drone_agents` dictionary keyed by drone ID.
- **Parallel Pilot**: The `ParallelAgent` is also cached based on the set of active drone IDs. If a drone is destroyed, a new `ParallelAgent` is formed, but the sub-agents are correctly detached from their previous parent to avoid validation errors.
This prevents the overhead of rebuilding agent instructions and toolsets every simulation tick.

### 5. Centralized Mission Logging
The system maintains a comprehensive `log.txt` file in the root directory.
- **Content**: Captures `/*PLANNING*/`, `/*REASONING*/`, and `/*ACTION*/` tags from the `PlanReActPlanner`.
- **Tool Events**: Logs all MCP tool calls and their corresponding responses with timestamps.
- **Usage**: Use this file for deep debugging of agent logic and strategic decision-making.

## 🚀 Best Practices

### 1. Agent Instructions (Markdown over YAML)
Always use the `.md` files in `swarm_flow/crews/rescue_crew/prompts/`. Markdown allows for better structure, lists, and legibility for the LLM. 
- Use **CAPITALIZED** keywords for strict constraints.
- Provide examples of expected output or tool call patterns.

### 2. Path Management
The MCP servers run as independent sub-processes. Always ensure `sys.path` is updated at the **very top** of any new MCP server file:
```python
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
```

### 3. Database Transactions
When writing tools that modify the database (like `allocate_drone_sector`), always use a connection context or explicitly call `conn.commit()` to ensure the simulation engine sees the changes in the next tick.

### 4. Persistence First
If adding a new agent type, ensure it is integrated into the `RescueCrew` caching logic to avoid redundant initialization.

### 5. SSL Bypass (Development Only)
If using `ngrok` or other tunnels for model hosting, refer to `rescue_crew.py` for the global SSL bypass configuration. **Never use this in production.**

---
*Maintained by the Swarm Engineering Team.*
