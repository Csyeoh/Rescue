# Architecture Map: Rescue Swarm Simulation

This document provides a high-level overview of the system architecture, data flow, and core components of the Rescue Swarm Simulation project.

## 1. Core Tech Stack
*   **Frontend**: [Next.js](https://nextjs.org/) (React 19), TypeScript, Tailwind CSS.
*   **Backend**: [FastAPI](https://fastapi.tiangolo.com/) (Python), Uvicorn, Pydantic.
*   **Simulation Engine**: [Mesa](https://mesa.readthedocs.io/) (Agent-Based Modeling framework).
*   **AI Swarm Logic**: [CrewAI](https://www.crewai.com/) (Agent orchestration), [LangChain](https://www.langchain.com/), and [Google Gemini](https://ai.google.dev/) (via LiteLLM).
*   **Real-time Communication**: WebSockets for live telemetry and log streaming.

## 2. Directory Structure
```text
D:\Project\Rescue\
├── rescue-ui/              # Next.js Frontend
│   ├── app/                # Main dashboard page and layout
│   ├── components/         # UI components (Map, Config, Logs, Telemetry)
│   └── public/             # Static assets
├── rescue_swarm_sim/       # Python Backend & Simulation
│   ├── api.py              # FastAPI endpoints and WebSocket handling
│   ├── simulation.py       # Mesa model and agent definitions (Drone, Survivor)
│   ├── websocket_manager.py# Real-time broadcast management
│   ├── map_generator.py    # AI-driven terrain and mission generation
│   ├── swarm_flow/         # CrewAI logic for swarm coordination
│   └── main.py             # Orchestrator script to boot UI and Backend
└── ARCHITECTURE_MAP.md     # This document
```

## 3. State & Global Variables
### Backend (Simulation)
*   **`sim_world` (`DisasterZoneModel`)**: Held in `simulation.py`. Contains the 2D grid, agent schedules, and the global discovery map.
*   **`_flow_running`**: A global boolean in `api.py` to prevent multiple concurrent swarm executions.
*   **`global_discovered_cells`**: A set in the simulation model tracking areas scanned by any drone.

### Frontend (UI)
*   **`worldState`**: Centralized state in `Dashboard.tsx` containing the grid, terrain discovery status, drone positions, battery levels, and mission logs.
*   **`config`**: Stores user-defined parameters for the next mission (drone count, battery, difficulty).

## 4. Data Flow
1.  **Map Generation**: UI sends mission parameters to `/api/generate_map`. Backend uses AI to create a blueprint and returns map data.
2.  **Mission Deployment**: UI calls `/api/start_mission`. Backend initializes the Mesa `DisasterZoneModel` and kicks off a background thread for the `swarm_flow`.
3.  **Simulation Loop**: The Mesa engine advances physics every 1s. Simultaneously, the CrewAI "brain" processes LLM-driven decisions for each drone.
4.  **Telemetry Streaming**: The backend broadcasts `tick_update` messages via WebSockets (`/ws`) using the `websocket_manager`.
5.  **UI Rendering**: The React frontend listens for WebSocket messages and performs surgical updates to the `worldState`, which re-renders the visualizer and logs.

## 5. Core Components
1.  **`MapVisualizer` (Frontend)**: A 2D grid renderer that displays the disaster zone, drone movement, and discovered survivors.
2.  **`DroneAgent` (Backend)**: The simulation entity responsible for movement, battery consumption, and thermal scanning.
3.  **`SwarmFlow` (CrewAI)**: The multi-agent orchestration layer that handles high-level strategy (e.g., "Drone 1 search sector A").
4.  **`DisasterZoneModel` (Backend)**: The environment manager that enforces physical constraints and resolves drone intents (e.g., preventing collisions with obstacles).
5.  **`ConfigPanel` (Frontend)**: The control interface for setting up mission scenarios and drone parameters.
6.  **`LogPanel` (Frontend)**: A real-time stream of "agent thoughts" and system events, providing transparency into AI decision-making.
