# 🚁 Rescue Swarm Simulator

An autonomous, multi-agent drone simulation orchestrating disaster response using **CrewAI**, a deterministic **Greedy Weighted BFS** algorithm, and a **Next.js** live dashboard.

## 🚀 The Architecture
This codebase has been upgraded to replace fragile LLM-based bounding-box grid coordinates with mathematically precise search paths, managed flawlessly by an AI-driven state machine.

*   **CrewAI Flow (`SwarmCommanderFlow`)**: Orchestrates the mission lifecycle. It retrieves real-time arrays of drones and terrain, branches logic based on drone statuses, and triggers workload re-assignments.
*   **Agentic Reasoning (Chain-of-Thought)**: The Swarm Commander (powered by Gemini via `google-genai` and CrewAI) analyzes the BFS coordinates and drone battery levels to narrate logical, human-readable tactical decisions into the mission DB logs.
*   **Greedy Weighted BFS**: A deterministic Python algorithm that prioritizes unmapped single-story buildings (high priority) and accounts for battery constraints to prevent search overlaps.
*   **Live Next.js UI**: A dynamic dashboard visualizing the drone pathing and active database logs in real-time.

---

## 🛠 Prerequisites
*   **Python 3.10+**
*   **Node.js 18+**
*   **Google Gemini API Key**

---

## 🏃‍♂️ How to Run the Project

### 1. Configure API Keys
Create a `.env` file in the `rescue_swarm_sim` directory and add your Gemini API Key:
```env
GEMINI_API_KEY="your_api_key_here"
```

### 2. Install Backend Dependencies
```bash
cd rescue_swarm_sim
python -m venv venv

# Activate the virtual environment (Windows):
venv\Scripts\activate  

# Activate the virtual environment (Mac/Linux):
# source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 3. Setup the Frontend Dashboard
```bash
# Open a new terminal or tab
cd rescue-ui
npm install
```

### 4. Launch the System
Run the master orchestrator script from the `rescue_swarm_sim` directory (ensure your Python virtual environment is active). This will simultaneously boot the FastAPI backend, initialize the SQLite database, and start the Next.js frontend.

```bash
cd rescue_swarm_sim
python main.py
```

Once the terminal confirms all systems are nominal, access the application at:
*   **Live Dashboard:** `http://localhost:3000`
*   **Backend API:** `http://localhost:8000`

*Note: To cleanly shut down all servers, press `Ctrl+C` in the terminal running `main.py`.*
