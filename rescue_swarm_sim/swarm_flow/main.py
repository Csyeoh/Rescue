#!/usr/bin/env python
from typing import Dict, List, Any
from crewai.flow.flow import Flow, listen, start, router
from pydantic import BaseModel
import sys
import os
import time

# Add parent dir to path so we can import simulation
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from .crews.rescue_crew.rescue_crew import RescueCrew, DroneIntent

class SwarmMissionState(BaseModel):
    simulation_active: bool = True
    active_drones: List[str] = []

class SwarmCombinedFlow(Flow[SwarmMissionState]):
    def __init__(self):
        super().__init__()
        self.rescue_crew = RescueCrew()

    @start()
    def partition_map(self):
        import simulation
        import websocket_manager
        from .tools.partition import get_active_drone_count, partition_grid_greedy_bfs
        
        # Get drone count directly
        num_drones = get_active_drone_count()
        base_x, base_y = 9, 9
        
        if num_drones > 0:
            # Notify frontend: Partitioning is starting
            try:
                websocket_manager.send_to_ui("partitioning_start", {"message": f"Calculating search sectors for {num_drones} drones — please wait..."})
            except:
                pass 
                
            # Run deterministic partition (State dynamically injected to `sim_world` by partition function)
            partitions = partition_grid_greedy_bfs(num_drones, base_x, base_y)
            self.state.active_drones = sorted(list(partitions.keys()), key=lambda x: int(x.split("_")[1]))
            
            print(f"Partitioning Complete for {num_drones} drones.")
            return "swarm_loop" # Trigger the first swarm step
        else:
            print("No drones found in simulation to partition.")
            self.state.simulation_active = False
            return "end_mission"

    @listen("swarm_loop")
    def get_states_and_build_tasks(self):
        """Phase 1: Deterministic Routing based on Python physical truth."""
        print(f"\n--- [RescueSwarmFlow] Initiating Swarm Step (Tick {int(time.time() % 1000)}) ---")
        tasks = []
        
        import simulation
        from simulation import DroneAgent
        
        # We query the environment ONCE before the agents think
        global_states = {}
        if simulation.sim_world:
            for agent in simulation.sim_world.schedule.agents:
                if isinstance(agent, DroneAgent):
                    global_states[agent.unique_id] = agent.status
        
        for d_id in self.state.active_drones:
            state = global_states.get(d_id, "IDLE")
            
            # Deterministic Routing
            if state == "SEARCHING":
                tasks.append(self.rescue_crew.build_task("searching_task", d_id))
            elif state == "CHARGING":
                tasks.append(self.rescue_crew.build_task("charging_task", d_id))
            elif state == "RETURNING":
                tasks.append(self.rescue_crew.build_task("returning_task", d_id))
            elif state == "IDLE":
                tasks.append(self.rescue_crew.build_task("idle_task", d_id))
                
        return tasks

    @listen(get_states_and_build_tasks)
    def execute_concurrent_crew(self, tasks):
        """Phase 2: All agents evaluate their specific task simultaneously."""
        if not tasks: return []

        tick_crew = self.rescue_crew.crew(tasks)
        
        # async_execution=True on the tasks makes this run in parallel
        tick_crew.kickoff()
        return tick_crew.tasks

    @listen(execute_concurrent_crew)
    def gather_and_execute_physical_tick(self, completed_tasks):
        """Phase 3: Extract intents and step Mesa."""
        import simulation
        batch_intents = []
        
        for task in completed_tasks:
            intent = getattr(task.output, 'pydantic', None)
            if intent:
                batch_intents.append(intent.model_dump())
                print(f"[{intent.drone_id}] {intent.action} -> Rationale: {intent.rationale}")
        
        # Step the mesa simulation once all agents have taken their actions
        if simulation.sim_world:
            simulation.sim_world.step()
            print("--- TICK RESOLVED: Mesa Simulation Step Completed ---")
            
        return batch_intents

    @router(gather_and_execute_physical_tick)
    def check_simulation_status(self):
        """Checks if the mission objective is reached after the swarm step."""
        if not self.state.simulation_active:
            return "end_mission"
            
        print("\n[RescueSwarmFlow] Checking Global Mission Status...")
        import simulation
        
        if simulation.sim_world:
            try:
                if getattr(simulation.sim_world, "mission_complete", False):
                    print("[RescueSwarmFlow] Mission AccomplISHED. Halting Swarm.")
                    self.state.simulation_active = False
                    return "end_mission"
            except Exception as e:
                print(f"Error checking status: {e}")
        
        # If not complete, loop back to the next swarm step
        return "swarm_loop"

    @listen("end_mission")
    def final_report(self):
        print("\nMISSION CONCLUDED")


def kickoff():
    flow = SwarmCombinedFlow()
    flow.kickoff()
    
if __name__ == "__main__":
    kickoff()

