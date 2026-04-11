#!/usr/bin/env python
from typing import List, Dict, Any
import sys
import os
import time
import json
import asyncio
from google.adk import Runner, Agent
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.events import Event
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import simulation
import websocket_manager
from .crews.rescue_crew.rescue_crew import RescueCrew

class SwarmCombinedFlow:
    def __init__(self):
        self.rescue_crew = RescueCrew()
        self.simulation_active = True
        self.current_intents = {}
        self.tick_start_time = 0.0
        self.session_service = InMemorySessionService()

    async def run_agent(self, agent: Agent, user_message: str) -> str:
        """Helper to run an ADK agent and broadcast its events to the UI."""
        user_id = "swarm_commander"
        session_id = "current_mission"
        app_name = "rescue_swarm"

        try:
            # Ensure session exists before running
            session = await self.session_service.get_session(app_name=app_name, user_id=user_id, session_id=session_id)
            if not session:
                await self.session_service.create_session(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id
                )

            runner = Runner(
                agent=agent, 
                app_name=app_name,
                session_service=self.session_service
            )
            final_text = ""

            # runner.run_async expects a Content object
            new_message = Content(role="user", parts=[Part(text=user_message)])

            async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=new_message):
                # Check for content from the model (text or thoughts)
                if event.content and event.author != "user" and event.author != "tool":
                    parts_to_ui = []
                    # Safely iterate over parts if they exist
                    parts = getattr(event.content, 'parts', []) or []
                    for p in parts:
                        if hasattr(p, 'text') and p.text:
                            parts_to_ui.append(p.text)

                    if parts_to_ui:
                        combined_content = "".join(parts_to_ui)
                        payload = {
                            "agent_role": agent.description or agent.name,
                            "task_id": event.id,
                            "plan": combined_content,
                            "ready": event.is_final_response()
                        }
                        websocket_manager.send_to_ui("agent_reasoning_completed", payload)
                        if event.is_final_response():
                            final_text = combined_content

                # Check for Tool Calls
                calls = event.get_function_calls()
                if calls:
                    for call in calls:
                        payload = {
                            "tool_name": call.name,
                            "tool_args": call.args,
                            "result": "Executing...",
                            "execution_duration_ms": 0
                        }
                        websocket_manager.send_to_ui("mcp_tool_execution_completed", payload)

                # Check for Tool Responses
                responses = event.get_function_responses()
                if responses:
                    for resp in responses:
                        payload = {
                            "tool_name": resp.name,
                            "tool_args": {}, 
                            "result": str(resp.response),
                            "execution_duration_ms": 0
                        }
                        websocket_manager.send_to_ui("mcp_tool_execution_completed", payload)

            await runner.close()

            return final_text
        except (Exception, BaseExceptionGroup) as e:
            # Enhanced error logging for TaskGroups and ExceptionGroups
            error_msg = str(e)
            if hasattr(e, 'exceptions'):
                # It's an ExceptionGroup or BaseExceptionGroup
                sub_errors = []
                for sub_e in e.exceptions:
                    sub_errors.append(f"[{type(sub_e).__name__}] {str(sub_e)}")
                error_msg = f"{type(e).__name__}: {str(e)} (Sub-exceptions: {', '.join(sub_errors)})"

            print(f"Error in run_agent: {error_msg}")
            websocket_manager.send_to_ui("flow_error", {"message": error_msg})
            raise e
    async def kickoff(self):
        print("🚀 [ADK] Starting Swarm Orchestration Loop...")
        websocket_manager.send_to_ui("partitioning_start", {"message": "Initializing Swarm Dispatcher..."})
        
        if simulation.sim_world: 
            simulation.sim_world.sync_to_db()

        while self.simulation_active:
            await self.swarm_tick()
            
            if not simulation.sim_world: break
            
            if simulation.sim_world.mission_complete or getattr(simulation.sim_world, "mission_failed", False):
                print("Ending Mission: Mission Complete or Failed.")
                self.simulation_active = False
                break
            
            await asyncio.sleep(0.1)
        print("Mission Concluded.")

    async def swarm_tick(self):
        self.tick_start_time = time.time()
        tick_count = simulation.sim_world.tick_count if simulation.sim_world else 0
        print(f"\n--- Swarm Tick {tick_count} ---")
        
        if not simulation.sim_world: 
            return

        from simulation import DroneAgent
        drones = [a for a in simulation.sim_world.schedule.agents if isinstance(a, DroneAgent) and not getattr(a, 'is_destroyed', False)]
        if not drones:
            self.simulation_active = False
            return

        # 1. Dispatcher Phase: If there are IDLE drones
        has_idle_drones = any(d.status == "IDLE" for d in drones)
        if has_idle_drones:
            print("Dispatcher: IDLE drones detected. Running dispatcher agent...")
            dispatcher = self.rescue_crew.get_dispatcher_agent()
            await self.run_agent(dispatcher, "Analyze map and allocate sectors to IDLE drones.")
        else:
            print("Dispatcher: All drones are busy. Skipping dispatcher agent.")

        # 2. Execution Phase: PARALLEL Drone Execution
        print(f"Execution: Running {len(drones)} drone agents in PARALLEL...")
        t_crew_start = time.time()
        
        # Create sub-agents for each drone
        sub_agents = [self.rescue_crew.get_drone_agent(d.unique_id) for d in drones]
        
        # Create ParallelAgent
        parallel_agent = ParallelAgent(
            name="swarm_parallel_pilot",
            description="Executes all drone pilots concurrently.",
            sub_agents=sub_agents
        )
        
        # Run ParallelAgent
        # Note: run_agent will broadcast events from all sub-agents to UI
        await self.run_agent(parallel_agent, "Each pilot: determine your next tactical move.")
        
        t_crew_end = time.time()
        
        # Extract results from session state
        batch_intents = {}
        session = await self.session_service.get_session(app_name="rescue_swarm", user_id="swarm_commander", session_id="current_mission")
        
        for d in drones:
            output_key = f"intent_{d.unique_id}"
            intent_data = session.state.get(output_key)
            if intent_data:
                try:
                    # ADK stores schema-validated output as dict or JSON string in state
                    if isinstance(intent_data, str):
                        intent = json.loads(intent_data)
                    else:
                        intent = intent_data
                    
                    batch_intents[d.unique_id] = intent
                    print(f"Captured Parallel Intent: {d.unique_id} -> {intent['action']} ({intent['status']}) -> ({intent.get('x')}, {intent.get('y')})")
                except Exception as e:
                    print(f"[ERROR] Failed to parse parallel intent for {d.unique_id}: {e}")

        # 3. Physics Step
        t_phys_start = time.time()
        simulation.sim_world.step(batch_intents)
        t_phys_end = time.time()
        
        # 4. UI Update
        from .tools.state_reader import get_current_map_state
        state = get_current_map_state()
        websocket_manager.send_to_ui("tick_update", state)
        
        t_total = time.time() - self.tick_start_time

def kickoff():
    flow = SwarmCombinedFlow()
    asyncio.run(flow.kickoff())

if __name__ == "__main__":
    kickoff()
