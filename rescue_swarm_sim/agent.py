import json
import time
import threading
import os

import database
import ai_tools
import tasks
from autopilot import autopilot_tick

def _log_system(message: str):
    try:
        database.log_action("SYSTEM", message)
    except Exception:
        pass

# ─── Threading state ──────────────────────────────────────────────────────────
_ai_running = threading.Event()

def _run_flow_orchestrator():
    """Runs the deterministic BFS partitioner and prompts LLM for log narrations."""
    try:
        from flow import SwarmCommanderFlow
        _log_system("Central Agent: Analyzing State and partitioning zones...")
        flow = SwarmCommanderFlow()
        flow.kickoff(inputs={"check_idle_only": False})
    except Exception as e:
        err_str = str(e)
        _log_system(f"AI ERROR: {err_str[:400]}")
        print(f"\n--- AI ORCHESTRATION ERROR ---\n{err_str}\n------------------------------\n")
    finally:
        _ai_running.clear()


def run_swarm_commander():
    _log_system("Central Intelligence and Drone Autopilot online.")
    last_check_time = 0.0

    while True:
        try:
            # ── PHASE 1: Deterministic Autopilot (always runs, never blocked) ─
            autopilot_tick()

            # ── PHASE 2: Check for idle/unassigned drones (every 10s) ─
            now = time.time()
            if now - last_check_time > 10.0 and not _ai_running.is_set():
                last_check_time = now

                status = ai_tools.get_drone_status()
                drones = status.get("drones", [])

                if len(drones) == 0:
                    time.sleep(1.0)
                    continue

                idle = ai_tools.get_idle_drones()
                
                # Check if we need initial partition
                conn = database._connect()
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM drone_waypoints")
                wp_count = c.fetchone()[0]
                conn.close()

                if wp_count == 0 or idle:
                    _ai_running.set()
                    t = threading.Thread(target=_run_flow_orchestrator, daemon=True)
                    t.start()

        except Exception as e:
            _log_system(f"Main Loop ERROR: {e}")

        time.sleep(1.0)


if __name__ == "__main__":
    run_swarm_commander()
