import os
import sys
import ssl

# Fix for ngrok self-signed certificate errors
# MUST BE DONE BEFORE IMPORTING LITELLM OR ADK
os.environ["LITELLM_SSL_VERIFY"] = "False"
os.environ["SSL_VERIFY"] = "False"

import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import litellm
litellm.ssl_verify = False
# litellm.set_verbose = True # Uncomment for deep debugging

from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, Field
from google.adk import Agent
from google.adk.planners import PlanReActPlanner
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from google.adk.models import LiteLlm
from mcp.client.stdio import StdioServerParameters
from dotenv import load_dotenv

load_dotenv()

class DroneIntent(BaseModel):
    drone_id: str = Field(..., description="The ID of the drone")
    action: str = Field(..., description="The action: 'search', 'wait', or 'charge'")
    x: Optional[int] = Field(None, description="Target X coordinate for move")
    y: Optional[int] = Field(None, description="Target Y coordinate for move")
    status: str = Field(..., description="The new status of the drone (SEARCHING, IDLE, RETURNING, CHARGING)")

# class BatchDroneIntents(BaseModel):
#     intents: list[DroneIntent] = Field(..., description="List of intents for all drones processed")

class RescueCrew:
    def __init__(self):
        self.prompts_path = Path(__file__).parent / 'prompts'
        
        # self.model = LiteLlm(model="ollama_chat/qwen3.5:4b", api_base="https://fondling-reformer-splatter.ngrok-free.dev")
        self.model = "gemini-2.5-flash"
        
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

        drone_mcp_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "mcp_server_drone.py"))
        self.drone_mcp_toolset = McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable, 
                    args=[drone_mcp_path]
                ),
                timeout=60.0
            )
        )

    def get_dispatcher_agent(self) -> Agent:
        with open(self.prompts_path / 'dispatcher.md', 'r') as f:
            instruction = f.read()
        
        agent = Agent(
            name="swarm_dispatcher",
            description=" A swarm dispatcher that coordinate and assign sector in a disaster zone to the drone swarm",
            instruction=instruction,
            model=self.model,
            tools=[self.dispatcher_mcp_toolset],
            planner=PlanReActPlanner()
        )
        return agent

    def get_drone_agent(self, drone_id: str) -> Agent:
        with open(self.prompts_path / 'drone_pilot.md', 'r') as f:
            instruction_template = f.read()
        
        instruction = instruction_template.format(drone_id=drone_id)
        
        agent = Agent(
            name=f"pilot_{drone_id}",
            description=f"Pilot for {drone_id}",
            instruction=instruction,
            model=self.model,
            tools=[self.drone_mcp_toolset],
            output_schema=DroneIntent,
            output_key=f"intent_{drone_id}", # Unique key for ParallelAgent collection
            disallow_transfer_to_parent=True,
            disallow_transfer_to_peers=True
        )
        return agent
