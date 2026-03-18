import subprocess
import sys
import time
import os

def start_services():
    print("🚀 Booting Swarm Control Nexus...")
    processes = []

    try:
        # 1. Start the FastAPI Backend (Simulation & Database API)
        print("--> Starting Python Simulation Backend (Port 8000) with access logs...")
        env = os.environ.copy()
        env["PYTHONPATH"] = os.getcwd()
        
        backend_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "api:app", "--port", "8000", "--log-level", "info"],
            cwd=os.getcwd(),
            env=env
        )
        processes.append(backend_process)

        # Give the backend a quick second to spin up before the frontend hits it
        time.sleep(2)

        print("--> Starting MCP Server (HTTP Transport, Port 9001)...")
        mcp_process = subprocess.Popen(
            [sys.executable, os.path.join("swarm_flow", "crews", "rescue_crew", "mcp_server.py"), "--transport", "http", "--host", "127.0.0.1", "--port", "9001"],
            cwd=os.getcwd(),
            env=env
        )
        processes.append(mcp_process)

        print("--> Starting UI (Port 3000)...")
        npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
        ui_override = os.environ.get("RESCUE_UI_PATH")
        if ui_override:
            ui_path = ui_override
        else:
            base_dir = os.path.dirname(os.getcwd())
            candidate_new = os.path.join(base_dir, "new_rescue_ui")
            candidate_old = os.path.join(base_dir, "rescue-ui")
            ui_path = candidate_new if os.path.isdir(candidate_new) else candidate_old
        
        frontend_process = subprocess.Popen(
            [npm_cmd, "run", "dev"],
            cwd=ui_path,
            shell=(os.name == "nt")  # Required for Windows npm execution
        )
        processes.append(frontend_process)

        # ==========================================
        # 3. AI SWARM COMMANDER (Ready for next step!)
        # ==========================================
        # The AI Swarm is now handled inside api.py -> start_mission!
        # DO NOT manually start agent.py here anymore.

        print("--> AI Swarm Commander will awaken upon 'Deploy Swarm' signal...")
        # ai_process = subprocess.Popen([sys.executable, "agent.py"], cwd=os.getcwd(), env=env)
        # processes.append(ai_process)

        print("\n✅ All systems nominal. UI available at http://localhost:3000")
        print("Press Ctrl+C to shut down all servers.")

        # Keep the master script alive while the subprocesses run
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Shutting down Swarm Control Nexus...")
        for p in processes:
            p.terminate()  # Kills the background servers cleanly
            p.wait()       # Waits for them to fully close before exiting
        print("System offline. Goodbye!")
        sys.exit(0)

if __name__ == "__main__":
    start_services()
