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
                    thought_text = ""
                    parts = getattr(event.content, "parts", []) or []
                    
                    for p in parts:
                        if hasattr(p, "text") and p.text: content_parts.append(p.text)
                        if hasattr(p, "thought") and p.thought:
                            content_parts.append(f"\n[THOUGHT: {p.thought}]\n")
                    
                    if content_parts:
                        full_content = "".join(content_parts)
                        
                        # Extract summary (from SUMMARY: line)
                        import re
                        summary_match = re.search(r"(?i)SUMMARY:\s*(.*)", full_content)
                        user_summary = summary_match.group(1).strip() if summary_match else full_content.split('\n')[0][:150]

                        # Extract thought sentence (text after [THOUGHT: True] up to SUMMARY:)
                        thought_match = re.search(r"\[THOUGHT:\s*True\]\s*\n(.*?)(?:\nSUMMARY:|\Z)", full_content, re.DOTALL)
                        thought_text = thought_match.group(1).strip() if thought_match else ""

                        # Log full reasoning to file only (for download)
                        self.log_to_file(f"REASONING ({author}):\n{full_content}", target=log_target)
                        
                        # Broadcast lightweight data to UI
                        websocket_manager.send_to_ui("agent_reasoning", {
                            "agent": (event.author or agent.name).upper(),
                            "summary": user_summary,
                            "thought": thought_text,
                        })
                        if event.is_final_response(): final_text = full_content

                # 2. Capture Tool Calls
                calls = event.get_function_calls()
                if calls:
                    for call in calls:
                        self.log_to_file(f"TOOL CALL ({event.author or agent.name}): {call.name}({json.dumps(call.args)})", target=log_target)
                        
                        clean_tool_name = call.name.split("__")[-1] if "__" in call.name else call.name
                        
                        # Early broadcast for thermal scan visualization
                        if clean_tool_name == "thermal_scan":
                            try:
                                d_id = call.args.get("drone_id")
                                cluster_id = call.args.get("cluster_id")
                                
                                # Resolve actual drone position from simulation
                                cx, cy = 9.5, 9.5
                                if simulation.sim_world:
                                    for a in simulation.sim_world.schedule.agents:
                                        if getattr(a, 'unique_id', None) == d_id:
                                            cx, cy = a.pos
                                            break
                                
                                # Calculate angle from cluster_id
                                angle = 0.0
                                if cluster_id:
                                    import db
                                    conn = db.get_db_conn()
                                    cursor = conn.cursor()
                                    cursor.execute("SELECT cx, cy FROM building_clusters WHERE id=?", (cluster_id,))
                                    row = cursor.fetchone()
                                    conn.close()
                                    if row:
                                        # Use the same bearing logic as the tool
                                        dx, dy = row[0] - cx, row[1] - cy
                                        import math
                                        angle = math.degrees(math.atan2(dx, dy)) % 360
                                
                                websocket_manager.send_to_ui("thermal_scan_event", {
                                    "cx": round(float(cx), 2),
                                    "cy": round(float(cy), 2),
                                    "angle": float(angle),
                                    "arc": 60.0,
                                    "radius": 6.0
                                })
                            except Exception as e:
                                self.log_to_file(f"ERROR: Failed early thermal broadcast: {e}")

                        websocket_manager.send_to_ui("tool_call", {
                            "agent": (event.author or agent.name).upper(),
                            "tool_name": clean_tool_name,
                            "tool_args": call.args if call.args else {},
                        })

                # 3. Capture Tool Responses
                responses = event.get_function_responses()
                if responses:
                    for resp in responses:
                        self.log_to_file(f"TOOL RESPONSE ({event.author or agent.name}): {resp.name} -> {resp.response}", target=log_target)
                        
                        raw = resp.response
                        result_message = str(raw)
                        
                        # The MCP response might have our dict encoded as a JSON string under content > text,
                        # or it might be raw dictionary, or it might be in structuredContent.
                        if isinstance(raw, dict):
                            # Try structuredContent first
                            sc = raw.get("structuredContent", {})
                            if isinstance(sc, dict) and "summary" in sc:
                                result_message = str(sc["summary"])
                            else:
                                content_list = raw.get("content", [])
                                if isinstance(content_list, list) and len(content_list) > 0:
                                    text_val = content_list[0].get("text", "")
                                    try:
                                        parsed = json.loads(text_val)
                                        if isinstance(parsed, dict) and "summary" in parsed:
                                            result_message = str(parsed["summary"])
                                        else:
                                            result_message = text_val
                                    except Exception:
                                        result_message = text_val
                                        
                        # Strip any namespacing from tool name (e.g. DispacherSwarm__tool -> tool)
                        clean_tool_name = resp.name.split("__")[-1] if "__" in resp.name else resp.name
                                        
                        websocket_manager.send_to_ui("tool_response", {
                            "agent": (event.author or agent.name).upper(),
                            "tool_name": clean_tool_name,
                            "result_message": result_message,
                        })

                        # Special case: navigate_to tool broadcast waypoints to UI
                        if clean_tool_name == "navigate_to":
                            try:
                                # The response might be a JSON string or dict depending on the MCP server type
                                waypoints = None
                                if isinstance(raw, dict):
                                    sc = raw.get("structuredContent", {})
                                    if isinstance(sc, dict) and "waypoints" in sc:
                                        waypoints = sc["waypoints"]
                                    else:
                                        content_list = raw.get("content", [])
                                        if content_list and "text" in content_list[0]:
                                            parsed = json.loads(content_list[0]["text"])
                                            waypoints = parsed.get("waypoints")
                                
                                if waypoints:
                                    websocket_manager.send_to_ui("path_update", {
                                        "drone_id": (event.author or agent.name),
                                        "waypoints": waypoints
                                    })
                            except Exception as e:
                                self.log_to_file(f"ERROR: Failed to broadcast waypoints: {e}")

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
        
        # Inject dynamic situation report
        user_msg = "Analyze mission status and coordinate the swarm."
        fresh_session_id = f"dispatcher_tick_{tick_count}"
        await self.run_agent(dispatcher, user_msg, session_id=fresh_session_id)
        
        # Sync dispatcher-written fields (status, assigned_sector) from DB → Mesa
        simulation.sim_world.dispatcher_step()
        
        # Broadcast ONLY dispatcher-modified data (statuses + sectors)
        from .tools.state_reader import get_dispatcher_state
        dispatcher_state = get_dispatcher_state()
        websocket_manager.send_to_ui("dispatcher_update", dispatcher_state)

        # 2. Execution Phase: PARALLEL Drone Execution
        self.log_to_file(f"PHASE: Execution - Running {len(drones)} drone agents via ParallelAgent...")
        
        drone_ids = [d.unique_id for d in drones]
        
        # Run agents automatically using the ParallelAgent
        parallel_agent = self.rescue_crew.get_parallel_pilot_agent(drone_ids)
        await self.run_agent(parallel_agent, f"Determine your next tactical move.", session_id="mission_drones_parallel")
                
        # 3. Physics Step
        self.log_to_file("PHASE: Physics - Syncing world state.")
        simulation.sim_world.step()
        
        # 4. UI Update
        from .tools.state_reader import get_current_map_state, get_coverage_state
        state = get_current_map_state()
        websocket_manager.send_to_ui("tick_update", state)
        
        # Dedicated coverage update (Fog of War)
        coverage = get_coverage_state()
        websocket_manager.send_to_ui("coverage_update", coverage)

        if simulation.sim_world and simulation.sim_world.mission_complete:
            msg = None
            logs = getattr(simulation.sim_world, "mission_logs", None)
            if isinstance(logs, list):
                sys_evt = next((l for l in reversed(logs) if isinstance(l, dict) and l.get("drone_id") == "SYSTEM"), None)
                if isinstance(sys_evt, dict):
                    msg = sys_evt.get("message")
            websocket_manager.send_to_ui("mission_complete", {
                "message": msg or "MISSION COMPLETE: all survivors rescued."
            })
        elif simulation.sim_world and getattr(simulation.sim_world, "mission_failed", False):
            msg = None
            logs = getattr(simulation.sim_world, "mission_logs", None)
            if isinstance(logs, list):
                sys_evt = next((l for l in reversed(logs) if isinstance(l, dict) and l.get("drone_id") == "SYSTEM"), None)
                if isinstance(sys_evt, dict):
                    msg = sys_evt.get("message")
            websocket_manager.send_to_ui("mission_failed", {
                "message": msg or "MISSION FAILED: one or more drones lost."
            })
        
        self.log_to_file(f"--- TICK {tick_count} COMPLETED (Duration: {time.time() - self.tick_start_time:.2f}s) ---")

def kickoff():
    flow = SwarmCombinedFlow()
    asyncio.run(flow.kickoff())

if __name__ == "__main__":
    kickoff()
