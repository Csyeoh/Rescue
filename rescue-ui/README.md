# 🚁 Swarm Control Nexus: AI-Powered Disaster Recovery

**Swarm Control Nexus** is a decentralized search-and-rescue simulation designed for the *First Responder of the Future* hackathon. It utilizes **Agentic AI** to coordinate a swarm of drones through a high-stakes disaster zone.

The system is built on a "strict environment" philosophy: the AI cannot cheat. It must manage real-time battery levels, navigate impassable earthquake debris, and use thermal scanning to locate survivors—all through a standardized Model Context Protocol (MCP) interface.



---

## 🏗️ System Architecture

The project follows a decoupled, event-driven microservice architecture to ensure maximum scalability and model-agnostic control:

* **🌍 The Simulation (Mesa):** A Python-based physics engine enforcing a 20x20 grid with strict movement rules and obstacle collisions.
* **🗄️ The World State (SQLite):** A serverless database acting as the "Single Source of Truth" for drone telemetry, survivor status, and mission logs.
* **⚡ The Bridge (FastAPI):** A high-performance REST API that broadcasts the simulation state to external clients.
* **💻 The Nexus Dashboard (Next.js):** A real-time React dashboard with a live-updating map and a scrolling "Mission Action Log" terminal.
* **🔌 The Tool Layer (FastMCP):** A Model Context Protocol server that wraps the simulation logic into secure "tools" for an LLM to execute.



---

## ⚙️ Environment Rules & Constraints

To test the **Chain-of-Thought (CoT)** capabilities of the AI Commander, the environment enforces the following logic:

| Feature | Logic |
| :--- | :--- |
| **Battery Drain** | Every movement costs **5% battery**. |
| **Emergency Recharge** | Drones must be manually routed to **Base Camp (0,0)** to restore 100% battery. |
| **Debris Obstruction** | Randomly generated debris cells are impassable; the AI must pathfind around them. |
| **Thermal Signature** | Survivors are invisible to the map until a drone performs a successful `thermal_scan`. |

---

## 🚀 Quick Start

### Prerequisites
* **Python 3.10+**
* **Node.js 18+**

### 1. Setup Environment
```bash
# Clone the repo
git clone [https://github.com/Csyeoh/Rescue.git](https://github.com/Csyeoh/Rescue.git)
cd rescue_swarm_sim

# Create and activate virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate  

# Mac/Linux:
source venv/bin/activate

# Install Backend Dependencies
pip install mesa fastapi uvicorn fastmcp
```

### 2. Setup Dashboard
```bash
cd rescue-ui
npm install
cd ..
```

### 3. Launch System
Run the master orchestrator to boot the API, the Database, and the UI simultaneously:
```bash
python main.py
```
* **Access the Dashboard:** `http://localhost:3000`
* **Access the API:** `http://localhost:8000`

---

## 📜 The "Contract" (MCP Tool Definitions)

For the **AI Commander** to interact with the world, the following tools are exposed via `mcp_server.py`:

* **`discover_drones`**: Returns a list of active drones ready for deployment.
* **`get_battery_status`**: Queries the live battery percentage of a specific unit.
* **`move_drone(x, y)`**: Attempts to move a drone. Returns `Success` or `Failed` (if blocked by debris or out of power).
* **`thermal_scan`**: Triggers a heat-signature check at the drone's current coordinates.

---

## 👥 Team Roles

* **Simulation Architect:** (Tan Jing En) - Physics engine, SQLite schema, and FastAPI bridge.
* **MCP Engineer:** (Person 2) - Tool wrapping and FastMCP server implementation.
* **AI Commander:** (Person 3) - System prompting, Chain-of-Thought logic, and resource management.
* **Orchestrator:** (Person 4) - Deployment, `main.py` lifecycle management, and UI polish.