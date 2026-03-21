# SaveMePls: Decentralized Swarm Intelligent Drone Rescue - Project Context

This document provides essential context for Gemini CLI to understand and interact with the **SaveMePls** project.

## 🚀 Project Overview
**SaveMePls** is an autonomous, AI-orchestrated drone rescue system designed for post-disaster scenarios. It combines **Swarm Intelligence** with **Large Language Models (LLMs)** to coordinate a fleet of drones in a simulated environment to find survivors.

### Core Technologies
- **Backend**: Python 3.10+, FastAPI, [Mesa](https://mesa.readthedocs.io/) (Agent-Based Modeling).
- **Orchestration**: [CrewAI](https://www.crewai.com/) (Agent Flows and Tasks).
- **Intelligence Layer**: [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) via FastMCP for tool-calling.
- **AI Models**: Gemini 2.5 Flash/Pro (Map Generation & Agent Reasoning), Local LLMs via Ollama (optional).
- **Frontend**: Next.js 15, Tailwind CSS, Framer Motion, Lucide React.
- **Communication**: WebSockets for real-time simulation updates.

## 🏗️ Architecture & Structure

### Backend (`/rescue_swarm_sim`)
- `main.py`: The master orchestrator script. Starts the FastAPI server and Next.js frontend simultaneously.
- `api.py`: FastAPI server handling HTTP requests (map generation, mission start) and WebSockets (`/ws`) for live state streaming.
- `simulation.py`: Core Mesa simulation logic. Defines `DroneAgent`, `SurvivorAgent`, and `CellAgent`.
- `map_generator.py`: Procedural map generation using Gemini to create semantic blueprints (topography, buildings, survivors).
- `zone_partitioner.py`: Implements a **Greedy Weighted BFS** algorithm to divide search sectors among drones based on terrain priority.
- `swarm_flow/`: Contains CrewAI logic.
    - `main.py`: The `SwarmCombinedFlow` that manages the mission lifecycle (Partitioning -> Swarm Loop -> Physical Tick).
    - `crews/rescue_crew/`: Defines the AI agents and tasks.
    - `crews/rescue_crew/mcp_server.py`: The MCP server providing tools to agents (e.g., `move_drone`, `thermal_scan`, `check_battery`).

### Frontend (`/rescue-ui`)
- Next.js application providing a real-time dashboard.
- Displays the grid-based disaster zone, drone movements, battery levels, and mission logs.
- Uses WebSockets to receive `tick_update` events from the backend.

## 🛠️ Key Commands

### Setup
```bash
# Backend
cd rescue_swarm_sim
python -m venv venv
source venv/bin/activate # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Frontend
cd rescue-ui
npm install
```

### Running the Project
```bash
# Launch both Backend and Frontend via the master orchestrator
cd rescue_swarm_sim
python main.py
```
- **Dashboard**: `http://localhost:3000`
- **API Docs**: `http://localhost:8000/docs`

## 🧠 Development Conventions

### Simulation State Machine
Drones operate on a deterministic state machine managed by CrewAI agents:
1.  **SEARCHING**: Executing search patterns in assigned sectors.
2.  **CHARGING**: Returning to base (9, 9) and waiting for battery recharge.
3.  **RETURNING**: Low battery or mission completion flight back to base.
4.  **IDLE**: Awaiting sector rebalancing or assignment.

### MCP Tools
Agents interact with the simulation *only* through MCP tools defined in `mcp_server.py`. These tools bridge the LLM reasoning with the Mesa physical environment.

### Map Generation
Maps are 20x20 grids. Gemini generates a `MapBlueprint` (topography anchors, building types, survivor locations) which is then translated into a physical terrain matrix in `map_generator.py`.

### Safety Thresholds
- **Battery Buffer**: Drones must always maintain a ~10-15% battery reserve to ensure return to base.
- **Collision Avoidance**: Drones should not move into cells marked as `is_obstacle`.

