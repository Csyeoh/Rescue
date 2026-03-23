#!/usr/bin/env python
from typing import List
from crewai.flow.flow import Flow, listen, start, router
from pydantic import BaseModel
import sys
import os
import time
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import simulation
import websocket_manager
from .crews.rescue_crew.rescue_crew import RescueCrew
from crewai.hooks import after_llm_call, before_tool_call, after_tool_call
# --- Agent Thinking & Tool Hooks ---

# def _get_drone_id(context):
#     """Helper to extract drone_id from the current task context."""
#     desc = getattr(context.task, 'description', '')
#     import re
#     match = re.search(r'drone_\d+', desc)
#     return match.group(0) if match else "Swarm"

# @after_llm_call
# def log_thinking(context):
#     """Broadcasts agent reasoning to the UI."""
#     drone_id = _get_drone_id(context)
#     message = f"🧠 Thought: {context.response}"
#     websocket_manager.send_to_ui("agent_log", {
#         "agent": drone_id,
#         "message": message,
#         "type": "info"
#     })

# @before_tool_call
# def log_tool_input(context):
#     """Broadcasts tool initiation to the UI."""
#     drone_id = _get_drone_id(context)
#     message = f"🔧 Calling tool: {context.tool_name} (Input: {context.tool_input})"
#     websocket_manager.send_to_ui("agent_log", {
#         "agent": drone_id,
#         "message": message,
#         "type": "warning"
#     })

# @after_tool_call
# def log_tool_output(context):
#     """Broadcasts tool results to the UI."""
#     drone_id = _get_drone_id(context)
#     message = f"✅ {context.tool_name} result: {context.tool_result}"
#     websocket_manager.send_to_ui("agent_log", {
#         "agent": drone_id,
#         "message": message,
#         "type": "success"
#     })


class SwarmMissionState(BaseModel):
    simulation_active: bool = True
    active_drones: List[str] = []

class SwarmCombinedFlow(Flow[SwarmMissionState]):
    def __init__(self):
        super().__init__(tracing=True)
        self.rescue_crew = RescueCrew()

    @start()
    def startFlow(self):
        pass
    
    @router(startFlow)
    def partition_map(self):
        from .tools.partition import get_active_drone_count, partition_grid_greedy_bfs
        num_drones = get_active_drone_count()
        if num_drones > 0:
            websocket_manager.send_to_ui("partitioning_start", {"message": "Initializing drone sectors..."})
            partitions = partition_grid_greedy_bfs(num_drones, 9, 9)
            self.state.active_drones = sorted(list(partitions.keys()))
            # Ensure the database knows about the new search lists before we start
            if simulation.sim_world: simulation.sim_world.sync_to_db()
            return "swarm_loop"
        return "end_mission"

    @listen("swarm_loop")
    def gather_intents(self):
        print(f"\n--- Swarm Tick {simulation.sim_world.tick_count if simulation.sim_world else 0} ---")
        if not simulation.sim_world: return "end_mission"

        from simulation import DroneAgent
        drones = [a for a in simulation.sim_world.schedule.agents if isinstance(a, DroneAgent) and not getattr(a, 'is_destroyed', False)]
        if not drones: return "end_mission"

        tasks = []
        for i, drone in enumerate(drones):
            d_id = drone.unique_id
            state = drone.status
            task_map = {
                "SEARCHING": "searching_task",
                "RETURNING": "returning_task",
                "CHARGING": "charging_task",
                "IDLE": "idle_task"
            }
            # The "Anchor" Logic: Last task is synchronous (is_async=False)
            is_last = (i == len(drones) - 1)
            tasks.append(self.rescue_crew.build_task(task_map.get(state, "idle_task"), d_id, is_async=not is_last))
        
        # Parallel execution with Sync Anchor
        crew = self.rescue_crew.crew(tasks)
        result = crew.kickoff()
        
        # Extract intents from the validated Pydantic models in tasks_output
        batch_intents = {}
        for task_output in result.tasks_output:
            intent = task_output.pydantic
            if intent:
                batch_intents[intent.drone_id] = intent.model_dump()
                print(f"Captured Intent: {intent.drone_id} -> {intent.action} ({intent.status}) -> ({intent.x}, {intent.y})")
        
        return batch_intents

    @router(gather_intents)
    def execute_tick(self, batch_intents):
        if not simulation.sim_world: return "end_mission"
        
        # Physics Step
        simulation.sim_world.step(batch_intents)
        
        # UI Update (Immediate Broadcast)
        from .tools.partition import get_current_map_state
        state = get_current_map_state()
        websocket_manager.send_to_ui("tick_update", state)
        
        if simulation.sim_world.mission_complete or getattr(simulation.sim_world, "mission_failed", False):
            return "end_mission"
        return "swarm_loop"

    @listen("end_mission")
    def conclude(self):
        print("Mission Concluded.")
        self.state.simulation_active = False

def kickoff():
    flow = SwarmCombinedFlow()
    flow.kickoff()

if __name__ == "__main__":
    kickoff()
