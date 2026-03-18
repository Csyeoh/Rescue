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
        controller_tick_s = float(os.getenv("CONTROLLER_TICK_S", "1.0"))

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
            
            agent_logs = thinking_logger.get_and_flush_logs()
            print(f"[Controller] Captured {len(agent_logs)} thinking logs from event bus (ID: {id(thinking_logger)}).")

            # 6. Check End
            if simulation.sim_world and getattr(simulation.sim_world, "mission_complete", False):
                print("[Controller] MISSION COMPLETE!")
                break
            
            time.sleep(controller_tick_s)

def kickoff():
    controller = SimpleSwarmController()
    controller.run()


if __name__ == "__main__":
    kickoff()
