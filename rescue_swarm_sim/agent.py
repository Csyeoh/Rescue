import json
import time
import threading
import os

import database
import ai_tools
import simulation
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
    mission_complete = False

    while True:
        try:
            # ── AGENT AMNESIA: Reset if no drones exist ──
            conn = database._connect()
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM drones")
            drone_count = c.fetchone()[0]
            conn.close()

            if drone_count == 0:
                if mission_complete:
                    print("♻️ Simulation Reset detected. Clearing mission state.")
                    mission_complete = False
                time.sleep(2.0)
                continue

            # ── PHASE 0: Check Win Condition ─
            if not mission_complete:
                conn = database._connect()
                c = conn.cursor()
                c.execute("SELECT COUNT(*), SUM(is_discovered) FROM survivors")
                row = c.fetchone()
                conn.close()

                if row and row[0] > 0 and row[0] == (row[1] if row[1] is not None else 0):
                    print("🎉 MISSION ACCOMPLISHED: Initiating global RTB Protocol.")
                    
                    # Hard-sync the simulation engine killswitch
                    if simulation.sim_world:
                        simulation.sim_world.mission_complete = True

                    with database.DB_WRITE_LOCK:
                        conn = database._connect()
                        cursor = conn.cursor()
                        
                        # 1. Clear all existing waypoints
                        cursor.execute("DELETE FROM drone_waypoints")
                        
                        # 2. Get all active drones
                        cursor.execute("SELECT drone_id FROM drones WHERE is_active=1")
                        drones = [r[0] for r in cursor.fetchall()]
                        
                        # 3. Assign RTB waypoint (9, 9)
                        for d_id in drones:
                            cursor.execute("INSERT INTO drone_waypoints (drone_id, seq, x, y, is_done) VALUES (?, 0, 9, 9, 0)", (d_id,))
                        
                        # 4. Log the accomplishment
                        cursor.execute("INSERT INTO logs (drone_id, message) VALUES ('SYSTEM', '🎉 MISSION ACCOMPLISHED: Initiating global RTB Protocol.')")
                        
                        conn.commit()
                        conn.close()
                    
                    mission_complete = True

            if mission_complete:
                time.sleep(5.0)
                continue

            # ── PHASE 1: Deterministic Autopilot (always runs, never blocked) ─
            # autopilot_tick()

            # ── PHASE 2: Check for idle/unassigned drones (every 10s) ─
            now = time.time()
            if not mission_complete and now - last_check_time > 10.0 and not _ai_running.is_set():
                last_check_time = now

                status = ai_tools.get_drone_status()
                drones = status.get("drones", [])

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
                conn = database._connect()
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM drone_waypoints")
                wp_count = c.fetchone()[0]
                conn.close()

                if wp_count == 0 or ready_for_redeployment:
                    # SAFETY CHECK: Don't re-deploy if mission is already complete
                    conn_safety = database._connect()
                    c_safety = conn_safety.cursor()
                    c_safety.execute("SELECT COUNT(*), SUM(is_discovered) FROM survivors")
                    row_safety = c_safety.fetchone()
                    conn_safety.close()

                    if row_safety and row_safety[0] > 0 and row_safety[0] == (row_safety[1] if row_safety[1] is not None else 0):
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
