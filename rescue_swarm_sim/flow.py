import json
import time
from typing import Dict, List, Any
from pydantic import BaseModel
from crewai.flow.flow import Flow, listen, start, router, or_

import database
import ai_tools
import zone_partitioner
from agents import build_agents

class SwarmMissionState(BaseModel):
    drones_info: List[Dict[str, Any]] = []
    terrain_map: List[Dict[str, Any]] = []
    partition_assignments: Dict[str, List[tuple[int, int]]] = {}
    idle_drones: List[str] = []
    is_initial_partition: bool = True
    rebalance_events: List[Dict[str, Any]] = []
    check_idle_only: bool = False

class SwarmCommanderFlow(Flow[SwarmMissionState]):

    @start()
    def load_world_state(self):
        print("[FLOW] Fetching live swarm state...")
        # Fetch drones
        drone_data = ai_tools.get_drone_status()
        self.state.drones_info = drone_data.get("drones", [])
        
        # Fetch terrain mapping directly from DB
        conn = database._connect()
        c = conn.cursor()
        c.execute("SELECT x, y, terrain_type, altitude FROM answer_plane")
        terrain_rows = c.fetchall()
        self.state.terrain_map = [{"x": r[0], "y": r[1], "type": r[2], "alt": r[3]} for r in terrain_rows]
        conn.close()

    @router(load_world_state)
    def determine_action(self):
        idle_drones = ai_tools.get_idle_drones()
        self.state.idle_drones = idle_drones

        # If any drone has NEVER been assigned a zone, we need an initial partition
        # We can check if `drone_waypoints` table has any entries at all.
        conn = database._connect()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM drone_waypoints")
        wp_count = c.fetchone()[0]
        conn.close()

        if wp_count == 0:
            self.state.is_initial_partition = True
            return "initial_partition"
        
        if self.state.check_idle_only:
            if idle_drones:
                self.state.is_initial_partition = False
                return "rebalance"
            else:
                return "done"
                
        # Fallback if somehow called generically but waypoints exist
        if idle_drones:
            self.state.is_initial_partition = False
            return "rebalance"
            
        return "done"

    @listen("initial_partition")
    def run_bfs_partition(self):
        print("[FLOW] Running initial Greedy Weighted BFS Partition...")
        assignments = zone_partitioner.greedy_weighted_bfs(self.state.drones_info, self.state.terrain_map)
        self.state.partition_assignments = assignments
        return True

    @listen("rebalance")
    def compute_rebalance(self):
        print(f"[FLOW] Computing rebalance for Idle drones: {self.state.idle_drones}")
        # Build current queue mapping from DB
        conn = database._connect()
        c = conn.cursor()
        
        active_queues = {}
        for d in self.state.drones_info:
            did = d["id"]
            c.execute("SELECT x, y FROM drone_waypoints WHERE drone_id=? AND is_done=0 ORDER BY seq ASC", (did,))
            active_queues[did] = [(r[0], r[1]) for r in c.fetchall()]
        conn.close()
        
        # Find burdened drone (the one with the most remaining waypoints)
        burdened_drone = None
        max_len = 0
        for did, q in active_queues.items():
            if len(q) > max_len:
                max_len = len(q)
                burdened_drone = did
                
        if not burdened_drone or max_len < 2:
            print("[FLOW] No burdened drone found to offload.")
            return "done"
            
        batteries = {d["id"]: d["battery"] for d in self.state.drones_info}
        
        rebalance_events = []
        for idle_id in self.state.idle_drones:
            # Rebalance max half of burdened drone's queue, constrained by idle drone's battery
            transferred = zone_partitioner.compute_rebalance(idle_id, burdened_drone, active_queues, batteries)
            if transferred:
                # Remove transferred from burdened drone's queue
                active_queues[burdened_drone] = [wp for wp in active_queues[burdened_drone] if wp not in transferred]
                active_queues[idle_id] = transferred
                
                rebalance_events.append({
                    "idle": idle_id,
                    "burdened": burdened_drone,
                    "transferred_count": len(transferred),
                    "idle_battery": batteries.get(idle_id, 0),
                    "burdened_battery": batteries.get(burdened_drone, 0)
                })
                
        self.state.partition_assignments = active_queues
        self.state.rebalance_events = rebalance_events
        print("[FLOW] Rebalance computed successfully.")
        return True

    @listen(or_(run_bfs_partition, compute_rebalance))
    def narrate_plan(self, *args):
        print("[FLOW] Narrating plan via Strategy Agent for Mission Log...")
        try:
            from crewai import Crew, Task
            _, commander = build_agents()
            
            # 1. Gather distance metrics (Nearest-Neighbor benchmark)
            # We calculate total Manhattan distance for each drone's assigned path.
            drone_metrics = []
            for did, wps in self.state.partition_assignments.items():
                drone_obj = next((d for d in self.state.drones_info if d['id'] == did), None)
                batt = drone_obj['battery'] if drone_obj else 100
                
                total_dist = 0
                if wps:
                    curr = (drone_obj['x'], drone_obj['y']) if drone_obj else (9, 9)
                    for wp in wps:
                        total_dist += abs(wp[0] - curr[0]) + abs(wp[1] - curr[1])
                        curr = wp
                
                drone_metrics.append({
                    "id": did,
                    "battery": batt,
                    "waypoint_count": len(wps),
                    "estimated_distance": total_dist
                })

            if self.state.is_initial_partition:
                system_prompt = f"Initial Swarm Partition Metrics:\n"
                for m in drone_metrics:
                    system_prompt += f"- Drone {m['id']}: Battery {m['battery']}%, Assigned {m['waypoint_count']} waypoints, Total Route: {m['estimated_distance']}m.\n"
                    
                task_desc = f"""
                Analyze the greedy weighted BFS partition metrics above.
                
                STRICT REQUIREMENT: You must explain your step-by-step logic before finalizing the plan. 
                For example: 'Drone 1 has 80% battery and is assigned a 120m route, which is safe. Drone 2 has lower battery, so it gets the shorter 50m route.'
                
                Write a brief Chain-of-Thought reasoning (max 4 sentences) explaining WHY 
                these assignments make strategic sense based on drone battery levels and coverage limits. 
                Keep it in-character as the Swarm Commander logging a tactical decision.
                Use the `log_mission_reasoning` tool to log your explanation.
                
                Data:
                {system_prompt}
                """
            else:
                event_str = "Swarm Rebalance Metrics:\n"
                for ev in self.state.rebalance_events:
                    # Find estimated distance for the transferred waypoints
                    idle_drone = next((d for d in self.state.drones_info if d['id'] == ev['idle']), None)
                    # Note: state.partition_assignments already contains the transferred wps for the idle drone
                    wps = self.state.partition_assignments.get(ev['idle'], [])
                    total_dist = 0
                    if wps:
                        curr = (idle_drone['x'], idle_drone['y']) if idle_drone else (9, 9)
                        for wp in wps:
                            total_dist += abs(wp[0] - curr[0]) + abs(wp[1] - curr[1])
                            curr = wp
                    
                    event_str += f"- Drone {ev['idle']} ({ev['idle_battery']}% batt) takes {ev['transferred_count']} cells ({total_dist}m) from Drone {ev['burdened']} ({ev['burdened_battery']}% batt).\n"
                    
                task_desc = f"""
                Analyze the swarm rebalance metrics below.
                
                STRICT REQUIREMENT: You must explain your step-by-step logic before finalizing the plan.
                For example: 'Drone 1 has 80% battery and is assigned a 120m route, which is safe. Drone 2 has lower battery, so it gets the shorter 50m route.'

                Write a brief Chain-of-Thought reasoning (max 4 sentences) explaining WHY this re-partitioning 
                optimizes the mission timeline and respects battery constraints.
                Keep it in-character as the Swarm Commander logging a tactical decision.
                Use the `log_mission_reasoning` tool to log your explanation.
                
                Data:
                {event_str}
                """
            
            task = Task(
                description=task_desc,
                expected_output="A confirmation that the reasoning was logged via the tool.",
                agent=commander
            )
            
            crew = Crew(
                agents=[commander],
                tasks=[task],
                verbose=False
            )
            
            try:
                result = crew.kickoff()
                # Capture the LLM's generated response to Agent_Mission_Log.txt
                with open("Agent_Mission_Log.txt", "a", encoding="utf-8") as f:
                    f.write(f"\n--- {time.ctime()} ---\n")
                    f.write(str(result))
                    f.write("\n")
            except Exception as e:
                print(f"[FLOW WARNING] Strategy Agent completed but threw an output parsing error: {str(e)}")
            
        except ImportError:
            # Fallback if crewai is missing
            conn = database._connect()
            conn.cursor().execute("INSERT INTO logs (drone_id, message) VALUES (?, ?)", ("SYSTEM", "STRATEGY: Assigned waypoints based on terrain weight and battery levels."))
            conn.commit()
            conn.close()

    @listen(or_(run_bfs_partition, compute_rebalance))
    def write_zones_to_db(self, *args):
        print("[FLOW] Dispatching waypoints to drones via MCP Server...")
        for d_id, wps in self.state.partition_assignments.items():
            if wps:
                print(f"[FLOW] Writing {len(wps)} waypoints for {d_id}")
                ai_tools.assign_waypoints(d_id, wps)

    @listen(or_(narrate_plan, write_zones_to_db))
    def wrap_up(self, *args):
        print("[FLOW] Execution complete.")
