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
        
        # Log File Paths
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.log_dispatcher_path = os.path.join(base_dir, "log_dispatcher.txt")
        self.log_drone_path = os.path.join(base_dir, "log_drone.txt")
        
        # Initialize log files
        header = f"--- Mission Log Started: {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n\n"
        for p in [self.log_dispatcher_path, self.log_drone_path]:
            with open(p, "w", encoding="utf-8") as f:
                f.write(header)

    def log_to_file(self, message: str, target: str = "mission", print_to_stdout: bool = True):
        """Routes logs to dispatcher, drone, or both (mission) files."""
        tick_count = simulation.sim_world.tick_count if simulation.sim_world else 0
        timestamp = time.strftime('%H:%M:%S')
        log_entry = f"[TICK {tick_count}] [{timestamp}]\n{message}\n\n"
        
        targets = []
        if target == "dispatcher": targets = [self.log_dispatcher_path]
        elif target == "drone": targets = [self.log_drone_path]
        else: targets = [self.log_dispatcher_path, self.log_drone_path]

        for p in targets:
            with open(p, "a", encoding="utf-8") as f:
                f.write(log_entry)
        
        if print_to_stdout:
            print(f"[{timestamp}] [TICK {tick_count}] {message.splitlines()[0]}")

    async def run_agent(self, agent: Agent, user_message: str, session_id: str = "current_mission") -> str:
        """Helper to run an ADK agent and broadcast its events to the UI and log file."""
        user_id, app_name = "swarm_commander", "rescue_swarm"
        
        # Determine log routing
        is_dispatcher = "dispatcher" in agent.name.lower()
        log_target = "dispatcher" if is_dispatcher else "drone"
        self.log_to_file(f"START AGENT: {agent.name} (Task: {user_message})", target=log_target)

        try:
            # Ensure session exists
            if not await self.session_service.get_session(app_name=app_name, user_id=user_id, session_id=session_id):
                await self.session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)

            runner = Runner(agent=agent, app_name=app_name, session_service=self.session_service)
            final_text = ""
            new_message = Content(role="user", parts=[Part(text=user_message)])

            async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=new_message):
                # 1. Capture All Model Content (Reasoning/Thoughts)
                if event.content and event.author not in ["user", "tool"]:
                    author = event.author or agent.name
                    content_parts = []
                    parts = getattr(event.content, "parts", []) or []
                    
                    for p in parts:
                        if hasattr(p, "text") and p.text: content_parts.append(p.text)
                        if hasattr(p, "thought") and p.thought: content_parts.append(f"\n[THOUGHT: {p.thought}]\n")
                    
                    if content_parts:
                        full_content = "".join(content_parts)
                        
                        # Simple Summary Extraction
                        import re
                        summary_match = re.search(r"(?i)SUMMARY:\s*(.*)", full_content)
                        user_summary = summary_match.group(1).strip() if summary_match else full_content.split('\n')[0][:150]

                        # Log everything to the routed file
                        self.log_to_file(f"REASONING ({author}):\n{full_content}", target=log_target)
                        
                        websocket_manager.send_to_ui("agent_reasoning_completed", {
                            "agent_role": agent.description or agent.name,
                            "plan": user_summary,
                            "ready": event.is_final_response()
                        })
                        if event.is_final_response(): final_text = full_content

                # 2. Capture Tool Calls
                calls = event.get_function_calls()
                if calls:
                    for call in calls:
                        self.log_to_file(f"TOOL CALL ({event.author or agent.name}): {call.name}({json.dumps(call.args)})", target=log_target)
                        websocket_manager.send_to_ui("mcp_tool_execution_completed", {
                            "tool_name": call.name, "tool_args": call.args, "result": "Executing...", "execution_duration_ms": 0
                        })

                # 3. Capture Tool Responses
                responses = event.get_function_responses()
                if responses:
                    for resp in responses:
                        self.log_to_file(f"TOOL RESPONSE ({event.author or agent.name}): {resp.name} -> {resp.response}", target=log_target)
                        websocket_manager.send_to_ui("mcp_tool_execution_completed", {
                            "tool_name": resp.name, "tool_args": {}, "result": str(resp.response), "execution_duration_ms": 0
                        })

            await runner.close()
            return final_text
        except (Exception, BaseExceptionGroup) as e:
            error_msg = str(e)
            if hasattr(e, "exceptions"):
                error_msg = f"{type(e).__name__}: {str(e)} (Sub-exceptions: {', '.join([f'[{type(se).__name__}] {se}' for se in e.exceptions])})"
            self.log_to_file(f"CRITICAL ERROR: {error_msg}", target=log_target)
            websocket_manager.send_to_ui("flow_error", {"message": error_msg})
            raise e

    async def kickoff(self):
        self.log_to_file("🚀 [ADK] Starting Swarm Orchestration Loop...")
        websocket_manager.send_to_ui("partitioning_start", {"message": "Initializing Swarm Dispatcher..."})
        
        if simulation.sim_world: 
            simulation.sim_world.sync_to_db()

        while self.simulation_active:
            await self.swarm_tick()
            
            if not simulation.sim_world: break
            
            if simulation.sim_world.mission_complete or getattr(simulation.sim_world, "mission_failed", False):
                self.log_to_file("Ending Mission: Mission Complete or Failed.")
                self.simulation_active = False
                break
            
            await asyncio.sleep(0.1)
        self.log_to_file("Mission Concluded.")

    async def swarm_tick(self):
        self.tick_start_time = time.time()
        tick_count = simulation.sim_world.tick_count if simulation.sim_world else 0
        self.log_to_file(f"--- STARTING SWARM TICK {tick_count} ---")
        
        if not simulation.sim_world: 
            return

        from simulation import DroneAgent
        drones = [a for a in simulation.sim_world.schedule.agents if isinstance(a, DroneAgent) and not getattr(a, 'is_destroyed', False)]
        if not drones:
            self.log_to_file("PHASE: TERMINATING - No active drones remaining.")
            self.simulation_active = False
            return

        # 1. Dispatcher Phase: Run dispatcher to coordinate the swarm
        self.log_to_file("PHASE: Dispatcher - Coordinating swarm.")
        dispatcher = self.rescue_crew.get_dispatcher_agent()
        await self.run_agent(dispatcher, "Analyze mission status and coordinate the swarm.", session_id="mission_dispatcher")

        # 2. Execution Phase: PARALLEL Drone Execution
        self.log_to_file(f"PHASE: Execution - Running {len(drones)} drone agents via ParallelAgent...")
        
        drone_ids = [d.unique_id for d in drones]
        
        # Run agents automatically using the ParallelAgent
        parallel_agent = self.rescue_crew.get_parallel_pilot_agent(drone_ids)
        await self.run_agent(parallel_agent, f"Determine your next tactical move.", session_id="mission_drones_parallel")
                
        # Extract individual intents from ParallelAgent session state
        batch_intents = {}
        
        session = await self.session_service.get_session(app_name="rescue_swarm", user_id="swarm_commander", session_id="mission_drones_parallel")
        for d_id in drone_ids:
            intent_data = session.state.get(f"raw_intent_{d_id}") if session else None
            
            if intent_data:
                try:
                    if isinstance(intent_data, str):
                        intent_obj = json.loads(intent_data)
                    elif hasattr(intent_data, "model_dump"): # Handle pydantic object
                        intent_obj = intent_data.model_dump()
                    elif isinstance(intent_data, dict):
                        intent_obj = intent_data
                    else:
                        intent_obj = dict(intent_data)
                    
                    if "drone_id" not in intent_obj:
                         intent_obj["drone_id"] = d_id
                    batch_intents[d_id] = intent_obj
                except Exception as e:
                    self.log_to_file(f"[ERROR] Failed to parse intent for {d_id}: {e}")
            else:
                self.log_to_file(f"[WARNING] No intent found in session state for {d_id}.")

        # 3. Physics Step
        self.log_to_file(f"PHASE: Physics - Applying {len(batch_intents)} drone intents.")
        simulation.sim_world.step(batch_intents)
        
        # 4. UI Update
        from .tools.state_reader import get_current_map_state
        state = get_current_map_state()
        websocket_manager.send_to_ui("tick_update", state)
        
        self.log_to_file(f"--- TICK {tick_count} COMPLETED (Duration: {time.time() - self.tick_start_time:.2f}s) ---")

def kickoff():
    flow = SwarmCombinedFlow()
    asyncio.run(flow.kickoff())

if __name__ == "__main__":
    kickoff()
