import os
import sys
import ssl

import ssl
ssl._create_default_https_context = ssl._create_unverified_context

from pathlib import Path
from typing import List
from pydantic import BaseModel, Field
from google.adk import Agent
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from google.adk.models import LiteLlm
from google.adk.planners import BuiltInPlanner
from google.genai import types
from mcp.client.stdio import StdioServerParameters
from dotenv import load_dotenv

load_dotenv()

class DroneIntent(BaseModel):
    drone_id: str  = Field(..., description="The ID of the drone")
    dx: float      = Field(0.0, description="Movement delta X (-1.0 to 1.0). Combined magnitude with dy must be ≤ 1.0.")
    dy: float      = Field(0.0, description="Movement delta Y (-1.0 to 1.0). Combined magnitude with dx must be ≤ 1.0.")
    status: str    = Field(..., description="The new status of the drone (SEARCHING, IDLE, RETURNING, CHARGING)")

class RescueCrew:
    def __init__(self):
        self.prompts_path = Path(__file__).parent / 'prompts'
        # --- NEW: Environment-Aware Model Routing ---
        use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
        
        if use_local:
            raw_model = os.getenv("LOCAL_MODEL", "qwen2.5-coder:7b")
            model_str = f"ollama/{raw_model}" if not raw_model.startswith("ollama/") else raw_model
            
            # Ensure Ollama base URL is set in the OS environment for LiteLLM
            os.environ["OLLAMA_API_BASE"] = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
            
            # Wrap the local model in ADK's LiteLlm adapter
            self.model = LiteLlm(model=model_str)
            print(f"🚀 [SYSTEM] Routing Swarm Intelligence to LOCAL GPU via {model_str}")
        else:
            self.model = "gemini-2.5-flash"
            print(f"☁️ [SYSTEM] Routing Swarm Intelligence to CLOUD via {self.model}")
        # --------------------------------------------
        
        # Initialize MCP Servers
        dispatcher_mcp_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "mcp_server_dispatcher.py"))
        self.dispatcher_mcp_toolset = McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable, 
                    args=[dispatcher_mcp_path]
                ),
                timeout=60.0
            )
        )

        # drone_mcp_path is defined when generating agents to ensure a fresh toolset instance per drone

        # Cache for initialized agents
        self._dispatcher_agent = None
        self._drone_agents = {}
        self._parallel_agents = {}

    def get_dispatcher_agent(self) -> Agent:
        if self._dispatcher_agent is None:
            with open(self.prompts_path / 'dispatcher.md', 'r') as f:
                instruction = f.read()
            
            self._dispatcher_agent = Agent(
                name="swarm_dispatcher",
                description="A swarm dispatcher that coordinate and assign sector in a disaster zone to the drone swarm",
                instruction=instruction,
                model=self.model,
                tools=[self.dispatcher_mcp_toolset],
                # planner=BuiltInPlanner(
                #     thinking_config=types.ThinkingConfig(
                #         include_thoughts=True,
                #         thinking_budget=-1,
                #     )
                # ),
                generate_content_config=types.GenerateContentConfig(
                    temperature=0.4,
                ),
            )
        return self._dispatcher_agent

    def get_drone_agent(self, drone_id: str) -> Agent:
        if drone_id not in self._drone_agents:
            with open(self.prompts_path / 'drone_pilot.md', 'r') as f:
                instruction_template = f.read()
            
            instruction = instruction_template.replace('{drone_id}', drone_id)
            
            drone_mcp_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "mcp_server_drone.py"))
            drone_mcp_toolset = McpToolset(
                connection_params=StdioConnectionParams(
                    server_params=StdioServerParameters(
                        command=sys.executable, 
                        args=[drone_mcp_path]
                    ),
                    timeout=60.0
                )
            )

            agent = Agent(
                name=f"pilot_{drone_id}",
                description=f"Pilot for {drone_id}",
                instruction=instruction,
                model=self.model,
                tools=[drone_mcp_toolset],
                output_key=f"raw_intent_{drone_id}", 
                
                # --- DISABLED FOR LOCAL LLM COMPATIBILITY ---
                # output_schema=DroneIntent,
                # planner=BuiltInPlanner(
                #     thinking_config=types.ThinkingConfig(
                #         include_thoughts=True,
                #         thinking_budget=300,
                #     )
                # ),
                # --------------------------------------------
                
                generate_content_config=types.GenerateContentConfig(
                    temperature=0.4,
                ),
                disallow_transfer_to_parent=True,
                disallow_transfer_to_peers=True
            )
            self._drone_agents[drone_id] = agent
        return self._drone_agents[drone_id]

    def get_parallel_pilot_agent(self, drone_ids: List[str]) -> ParallelAgent:
        """Returns a ParallelAgent that runs pilots in parallel."""
        cache_key = tuple(sorted(drone_ids))
        if cache_key not in self._parallel_agents:
            sub_agents = [self.get_drone_agent(d_id) for d_id in drone_ids]
            for agent in sub_agents:
                if hasattr(agent, 'parent_agent'): agent.parent_agent = None
            
            self._parallel_agents[cache_key] = ParallelAgent(
                name="swarm_parallel_pilot",
                description="Executes all drone pilots concurrently.",
                sub_agents=sub_agents
            )
            
        return self._parallel_agents[cache_key]