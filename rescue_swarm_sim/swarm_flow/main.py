#!/usr/bin/env python
from typing import List
from crewai.flow.flow import Flow, listen, start, router
from pydantic import BaseModel
import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import simulation
import websocket_manager
from .crews.rescue_crew.rescue_crew import RescueCrew
from .crews.rescue_crew.reasoning_logger import ReasoningLogger


class SwarmMissionState(FlowState):
    simulation_active: bool = True
    active_drones: List[str] = []
    current_intents: dict = {}
    tick_start_time: float = 0.0

customListener = ReasoningLogger()
class SwarmCombinedFlow(Flow[SwarmMissionState]):
    def __init__(self):
        super().__init__(tracing=True)
        self.rescue_crew = RescueCrew()

    @start()
    def startFlow(self):
        pass
    
    @router(startFlow)
    def on_startFlow(self):
        websocket_manager.send_to_ui("partitioning_start", {"message": "Initializing Swarm Dispatcher..."})
        if simulation.sim_world: simulation.sim_world.sync_to_db()
        return "swarm_loop"

    @listen("swarm_loop")
    def gather_intents(self):
        self.state.tick_start_time = time.time()
        print(f"\n--- Swarm Tick {simulation.sim_world.tick_count if simulation.sim_world else 0} ---")
        if not simulation.sim_world: return "end_mission"

        from simulation import DroneAgent
        drones = [a for a in simulation.sim_world.schedule.agents if isinstance(a, DroneAgent) and not getattr(a, 'is_destroyed', False)]
        if not drones: return "end_mission"

        tasks = []
        
        # 1. Add the Dispatcher Task ONLY if there are IDLE drones
        has_idle_drones = any(d.status == "IDLE" for d in drones)
        if has_idle_drones:
            print("Dispatcher: IDLE drones detected. Adding dispatch task...")
            tasks.append(self.rescue_crew.build_dispatch_task())
        else:
            print("Dispatcher: All drones are busy. Skipping dispatch task.")

        # 2. Add Batch Drone Task
        fleet_state_lines = []
        for drone in drones:
            fleet_state_lines.append(f"- Drone ID: {drone.unique_id}, Status: {drone.status}")
        fleet_state_str = "\n".join(fleet_state_lines)
        
        tasks.append(self.rescue_crew.build_batch_task(fleet_state_str))
        
        # Parallel execution with Sync Anchor
        t_crew_start = time.time()
        crew = self.rescue_crew.crew(tasks)
        result = crew.kickoff()
        t_crew_end = time.time()
        print(f"⏱️ [Timing] CrewAI Kickoff (Agent Reasoning + MCP Tools) took {t_crew_end - t_crew_start:.2f}s")
        
        # Extract intents from the validated Pydantic models in tasks_output
        batch_intents = {}
        for task_output in result.tasks_output:
            out_model = getattr(task_output, "pydantic", None)
            if out_model:
                if hasattr(out_model, 'intents') and isinstance(out_model.intents, list):
                    for intent in out_model.intents:
                        if hasattr(intent, 'drone_id') and getattr(intent, 'drone_id') != "swarm":
                            batch_intents[intent.drone_id] = intent.model_dump()
                            print(f"Captured Intent: {intent.drone_id} -> {intent.action} ({intent.status}) -> ({intent.x}, {intent.y})")
        
        self.state.current_intents = batch_intents

    @router(gather_intents)
    def execute_tick(self):
        if not simulation.sim_world: return "end_mission"
        
        # Physics Step
        t_phys_start = time.time()
        simulation.sim_world.step(self.state.current_intents)
        t_phys_end = time.time()
        print(f"⏱️ [Timing] Simulation Physics & DB Sync took {t_phys_end - t_phys_start:.4f}s")
        
        # UI Update (Immediate Broadcast)
        from .tools.state_reader import get_current_map_state
        state = get_current_map_state()
        websocket_manager.send_to_ui("tick_update", state)
        
        t_total = time.time() - self.state.tick_start_time
        print(f"⏱️ [Timing] Total Tick Duration: {t_total:.2f}s\n")
        
        if simulation.sim_world.mission_complete or getattr(simulation.sim_world, "mission_failed", False):
            print("Ending Mission: Mission Complete or Failed.")
            return "end_mission"
        return "swarm_loop"

    @listen("end_mission")
    def conclude(self):
        print("Mission Concluded.")
        self.state.simulation_active = False
        return

def kickoff():
    flow = SwarmCombinedFlow()
    flow.kickoff()

if __name__ == "__main__":
    kickoff()
