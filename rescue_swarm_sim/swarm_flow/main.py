#!/usr/bin/env python
from typing import Dict, List, Any
from crewai.flow.flow import Flow, listen, start, router, FlowState
from pydantic import BaseModel, Field
import sys
import os
import time

# Add parent dir to path so we can import simulation
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from .crews.rescue_crew.rescue_crew import RescueCrew, DroneIntent, thinking_logger
print(f"[Controller] thinking_logger ID: {id(thinking_logger)}")


class SwarmMissionState(FlowState):
    simulation_active: bool = True
    active_drones: List[str] = []
    tick_count: int = 0


class SimpleSwarmController:
    def __init__(self):
        self.state = SwarmMissionState()
        self.rescue_crew = RescueCrew()

    def run(self):
        print("\n[Controller] Starting Mission Control Loop...")
        
        # Phase 0: Partition
        print("[Controller] Phase 0: Map Partitioning...")
        from .tools.partition import get_active_drone_count, partition_grid_greedy_bfs
        num_drones = get_active_drone_count()
        if num_drones > 0:
            partitions = partition_grid_greedy_bfs(num_drones, 9, 9)
            self.state.active_drones = sorted(list(partitions.keys()), key=lambda x: int(x.split("_")[1]))
            # Mark simulation as active
            self.state.simulation_active = True
            print(f"[Controller] Partitioned for {num_drones} drones: {self.state.active_drones}")
        else:
            print("[Controller] No drones found. Exiting.")
            return

        # Main Loop
        import simulation
        from simulation import DroneAgent, resolve_intent
        import websocket_manager
        from .crews.rescue_crew.rescue_crew import thinking_logger

        while self.state.simulation_active:
            self.state.tick_count += 1
            print(f"\n--- [Controller] TICK {self.state.tick_count} ---")

            # 1. Build Tasks
            tasks = []
            global_states = {}
            if simulation.sim_world:
                for agent in simulation.sim_world.schedule.agents:
                    if isinstance(agent, DroneAgent):
                        global_states[agent.unique_id] = agent.status

            for d_id in self.state.active_drones:
                state = global_states.get(d_id, "IDLE")
                if state == "SEARCHING":
                    tasks.append(self.rescue_crew.build_task("searching_task", d_id))
                elif state == "CHARGING":
                    tasks.append(self.rescue_crew.build_task("charging_task", d_id))
                elif state == "RETURNING":
                    tasks.append(self.rescue_crew.build_task("returning_task", d_id))
                elif state == "IDLE":
                    tasks.append(self.rescue_crew.build_task("idle_task", d_id))

            if not tasks:
                print("[Controller] No active tasks. Objective reached?")
                break

            # 2. Execute Crew
            print(f"[Controller] Executing Crew with {len(tasks)} tasks for {self.state.active_drones}...")
            tick_crew = self.rescue_crew.crew(tasks)
            tick_start = time.time()
            try:
                tick_crew.kickoff()
            except Exception as e:
                print(f"[Controller] Crew Execution ERROR: {e}")
            print(f"[Controller] Crew Done in {time.time() - tick_start:.2f}s")
            
            # 3. Resolve Intents
            agent_logs = thinking_logger.get_and_flush_logs()
            print(f"[Controller] Captured {len(agent_logs)} thinking logs from event bus (ID: {id(thinking_logger)}).")
            batch_intents = []
            handled_drones = set()
            
            # Diagnostic: print any tool calls found
            tool_calls = [l for l in agent_logs if l.get("type") == "tool_call"]
            tool_results = [l for l in agent_logs if l.get("type") == "tool_result"]
            print(f"[Controller] Tool Calls: {len(tool_calls)}, Tool Results: {len(tool_results)}")
            
            if tool_calls:
                print(f"[Controller] Tools detected: {[tc.get('tool') for tc in tool_calls]}")
            
            # Fallback: if no tool calls found, try to find in tool_results or agent outputs
            if not tool_calls and not tool_results:
                print("[Controller] WARNING: No tool activity captured in thinking logs!")
            
            # Priority 1: Tools
            for log in agent_logs:
                if log.get("type") == "tool_call" and "submit_intent" in log.get("tool", ""):
                    try:
                        import ast
                        raw_input = log.get("input", "{}")
                        if isinstance(raw_input, str):
                            # Handle potential JSON-like strings from LLM
                            raw_input = raw_input.replace("true", "True").replace("false", "False").replace("null", "None")
                            intent_dict = ast.literal_eval(raw_input)
                        else:
                            intent_dict = raw_input
                            
                        if intent_dict and intent_dict.get("drone_id"):
                            d_id = intent_dict["drone_id"]
                            if d_id in handled_drones:
                                batch_intents = [it for it in batch_intents if it.get("drone_id") != d_id]
                            batch_intents.append(intent_dict)
                            handled_drones.add(d_id)
                            print(f"[Controller] Captured Intent for {d_id}: {intent_dict.get('action')}")
                    except Exception as e:
                        print(f"[Controller] Error parsing intent: {e}")
            
            # 4. Physical Step — Update all states
            drone_states = []
            if simulation.sim_world:
                for agent in simulation.sim_world.schedule.agents:
                    if isinstance(agent, DroneAgent):
                        drone_states.append({
                            "id": agent.unique_id,
                            "x": agent.pos[0] if agent.pos else 9,
                            "y": agent.pos[1] if agent.pos else 9,
                            "battery": agent.battery,
                            "status": agent.status
                        })

            all_map_updates = []
            all_events = []
            for intent_dict in batch_intents:
                res = resolve_intent(simulation.sim_world, intent_dict)
                all_map_updates.extend(res["map_updates"])
                for evt in res["events"]:
                    all_events.append({"drone_id": res["drone_id"], "event": evt})
                    print(f"  [{res['drone_id']}] {evt}")

            if simulation.sim_world:
                simulation.sim_world.step()

            # 5. Broadcast (Matches Dashboard expected schema)
            payload = {
                "tick": self.state.tick_count,
                "drone_states": drone_states,
                "map_updates": all_map_updates,
                "events": all_events,
                "agent_logs": agent_logs
            }
            try: 
                websocket_manager.send_to_ui("tick_update", payload)
            except Exception as e:
                print(f"[Controller] Broadcast Error: {e}")

            # 6. Check End
            if simulation.sim_world and getattr(simulation.sim_world, "mission_complete", False):
                print("[Controller] MISSION COMPLETE!")
                break
            
            time.sleep(1) # Pace the loop

def kickoff():
    controller = SimpleSwarmController()
    controller.run()


if __name__ == "__main__":
    kickoff()
