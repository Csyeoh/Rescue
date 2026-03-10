# 🚁 Rescue Swarm Simulation: First Responder of the Future

An autonomous, 2D Agentic AI simulation environment built for the "First Responder of the Future" hackathon. 

This project simulates a decentralized drone swarm navigating a post-disaster zone (earthquake/super typhoon) to locate hidden survivors. It enforces strict physical constraints (battery logistics, impassable debris) to test the Chain-of-Thought reasoning and resource management of an autonomous AI Commander.

## 🏗️ System Architecture

This environment uses a decoupled, event-driven microservice architecture:

* **The Physics Engine (`simulation.py`):** Powered by the Python `mesa` library. Maintains a strict 20x20 grid, handles out-of-bounds checks, and calculates obstacle collisions.
* **The Data Layer (`database.py`):** A local, serverless SQLite database (`swarm_state.db`). Acts as the single source of truth for drone coordinates, battery levels, survivor locations, and mission logs.
* **The API Bridge (`api.py`):** A FastAPI server that continuously reads the SQLite database and broadcasts the world state via a RESTful JSON endpoint.
* **The UI Dashboard (`rescue-ui/`):** A Next.js (React) frontend styled with Tailwind CSS. It polls the API to render a real-time, color-coded map and a scrolling hacker-style mission terminal.
* **The Orchestrator (`main.py`):** A multi-process execution script that boots the backend API and frontend UI simultaneously.

## ✨ Core Features & Constraints

To prevent the AI from "cheating," the environment enforces the following physical rules:
* **Battery Logistics:** Every valid move costs `5%` battery. The engine rejects movement commands if the battery is critically low.
* **Base Camp Recharging:** Drones routed to coordinate `(0, 0)` instantly recharge their battery to `100%`.
* **Earthquake Debris:** Impassable structural debris is scattered randomly across the grid. Attempting to enter a debris cell returns a failed status, forcing the AI to pathfind.
* **Thermal Scanning:** Real-world thermal mechanics are simulated. The system checks drone coordinates against hidden survivor coordinates to mark them as discovered.

## 🛠️ Prerequisites

* **Python 3.10+**
* **Node.js 18+** (for the Next.js frontend)

## 🚀 Installation & Quick Start

**1. Clone the repository and navigate to the backend folder:**
```bash
cd rescue_swarm_sim
```

**2. Set up the Python virtual environment:**
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate
```

**3. Install backend dependencies:**
```bash
pip install mesa fastapi uvicorn
```

**4. Install frontend dependencies:**
```bash
cd rescue-ui
npm install
cd ..
```

**5. Launch the Swarm Control Nexus:**
```bash
python main.py
```
*The master script will automatically boot the FastAPI backend on `localhost:8000` and the Next.js UI on `localhost:3000`.*

## 📜 "The Contract" (Simulation API)

For the **MCP Engineer**, the following Python functions are fully tested and ready to be exposed as tools to the AI Agent. *Do not hardcode movement; all actions must route through these tools.*

* `discover_drones() -> list[str]`: Returns an array of active drone IDs.
* `get_battery_status(drone_id: str) -> int`: Returns current battery from 0 to 100.
* `thermal_scan(drone_id: str) -> bool`: Checks the drone's coordinates against the hidden survivor table.
* `move_to(drone_id: str, x: int, y: int) -> dict`: Updates the grid, drains battery, logs the action, and syncs to SQLite. Returns a dictionary with the move's success or failure reason.