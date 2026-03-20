import json
import time
import threading
import os
import httpx

import ai_tools
from autopilot import autopilot_tick

API_URL = "http://localhost:8000/api"

def mcp_call(method: str, path: str, payload: dict = None):
    """Synchronous wrapper for MCP-equivalent API calls."""
    try:
        with httpx.Client(timeout=10.0) as client:
            if method == "GET":
                r = client.get(f"{API_URL}{path}")
            elif method == "POST":
                r = client.post(f"{API_URL}{path}", json=payload)
            elif method == "DELETE":
                r = client.delete(f"{API_URL}{path}")
            else:
                return None
            return r.json()
    except Exception as e:
        print(f"MCP Call Error ({path}): {e}")
        return None

def _log_system(message: str):
    """Replaces direct DB log with MCP post_log equivalent."""
    mcp_call("POST", "/logs", {"agent_id": "SYSTEM", "message": message})

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
    mission_complete = False

    while True:
        try:
            # ── AGENT AMNESIA: Reset if no drones exist ──
            drones_list = mcp_call("GET", "/drones")
            drone_count = len(drones_list) if isinstance(drones_list, list) else 0

            if drone_count == 0:
                if mission_complete:
                    print("♻️ Simulation Reset detected. Clearing mission state.")
                    mission_complete = False
                time.sleep(2.0)
                continue

            # ── PHASE 0: Check Win Condition ─
            status = mcp_call("GET", "/mission/status")
            if status and not mission_complete:
                if status.get("is_complete"):
                    print("🎉 MISSION ACCOMPLISHED: Initiating global RTB Protocol.")
                    
                    # Hard-sync the simulation engine killswitch (MCP: trigger_global_killswitch)
                    mcp_call("POST", "/mission/killswitch")

                    # 1. Clear all existing waypoints (MCP: clear_all_assignments)
                    mcp_call("DELETE", "/waypoints")
                    
                    # 2. Assign RTB waypoint (9, 9) (MCP: assign_mission_waypoints)
                    for d_id in drones_list:
                        mcp_call("POST", "/waypoints/assign", {
                            "drone_id": d_id,
                            "waypoints": [{"x": 9, "y": 9}]
                        })
                    
                    # 4. Log the accomplishment
                    _log_system("🎉 MISSION ACCOMPLISHED: Initiating global RTB Protocol.")
                    mission_complete = True

            if mission_complete:
                time.sleep(5.0)
                continue

            # ── PHASE 2: Check for idle/unassigned drones (every 10s) ─
            now = time.time()
            if not mission_complete and now - last_check_time > 10.0 and not _ai_running.is_set():
                last_check_time = now

                status_data = ai_tools.get_drone_status()
                drones = status_data.get("drones", [])

                if len(drones) == 0:
                    time.sleep(1.0)
                    continue

                # RE-DEPLOYMENT FIX: Identify drones that are both idle AND charged
                idle_ids = ai_tools.get_idle_drones()
                
                # Filter for drones with > 95% battery
                ready_for_redeployment = []
                for d in drones:
                    if d['id'] in idle_ids and d.get('battery', 0) > 95:
                        ready_for_redeployment.append(d['id'])

                # Check if we need initial partition or if any charged drones are idle
                wp_status = mcp_call("GET", "/waypoints/status")
                wp_count = wp_status.get("pending_waypoints", 0) if wp_status else 0

                if wp_count == 0 or ready_for_redeployment:
                    # SAFETY CHECK: Don't re-deploy if mission is already complete
                    safety = mcp_call("GET", "/mission/status")
                    if safety and safety.get("is_complete"):
                        time.sleep(1.0)
                        continue

                    if ready_for_redeployment:
                        print(f"🔄 Re-deploying {len(ready_for_redeployment)} fully charged drones: {ready_for_redeployment}")
                        _log_system(f"RE-DEPLOY: {len(ready_for_redeployment)} drones recharged and ready.")
                    
                    _ai_running.set()
                    t = threading.Thread(target=_run_flow_orchestrator, daemon=True)
                    t.start()

        except Exception as e:
            _log_system(f"Main Loop ERROR: {e}")

        time.sleep(1.0)


if __name__ == "__main__":
    run_swarm_commander()
