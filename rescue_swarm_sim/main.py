import subprocess
import sys
import time
import os

def start_services():
    print("🚀 Booting Swarm Control Nexus...")
    processes = []

    try:
        # 1. Start the FastAPI Backend (Simulation & Database API)
        print("--> Starting Python Simulation Backend (Port 8000)...")
        backend_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "api:app", "--port", "8000"],
            cwd=os.getcwd() 
        )
        processes.append(backend_process)

        # Give the backend a quick second to spin up before the frontend hits it
        time.sleep(2)

        # 2. Start the Next.js Frontend (Live React Map)
        print("--> Starting Next.js Live Map (Port 3000)...")
        npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
        # Look one directory UP from the current folder, then find rescue-ui
        ui_path = os.path.join(os.path.dirname(os.getcwd()), "rescue-ui")
        
        frontend_process = subprocess.Popen(
            [npm_cmd, "run", "dev"],
            cwd=ui_path,
            shell=(os.name == "nt")  # Required for Windows npm execution
        )
        processes.append(frontend_process)

        # ==========================================
        # 3. AI SWARM COMMANDER (Ready for next step!)
        # ==========================================
        # Once we build agent.py, uncomment these three lines to boot the AI automatically!
        
        # print("--> Awakening AI Swarm Commander...")
        # ai_process = subprocess.Popen([sys.executable, "agent.py"], cwd=os.getcwd())
        # processes.append(ai_process)

        print("\n✅ All systems nominal. Dashboard available at http://localhost:3000")
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