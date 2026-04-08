import os
import yaml
import sys
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, Field
from google.adk import Agent
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
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
        base_path = Path(__file__).parent / 'config'
        with open(base_path / 'agents.yaml', 'r') as f:
            self.agents_config = yaml.safe_load(f)
        with open(base_path / 'tasks.yaml', 'r') as f:
            self.tasks_config = yaml.safe_load(f)
        
        self.model = "gemini-2.5-flash"
        
        # Initialize MCP Servers
        dispatcher_mcp_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "mcp_server_dispatcher.py"))
        self.dispatcher_mcp_toolset = McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable, 
                    args=[dispatcher_mcp_path]
                )
            )
        )

        drone_mcp_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "mcp_server_drone.py"))
        self.drone_mcp_toolset = McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable, 
                    args=[drone_mcp_path]
                )
            )
        )

    def get_dispatcher_agent(self) -> Agent:
        config = self.agents_config['swarm_dispatcher']
        task_config = self.tasks_config['dispatch_task']
        
        instruction = f"{config['goal']}\n{config['backstory']}\n\nTask: {task_config['description']}"
        
        agent = Agent(
            name="swarm_dispatcher",
            description=config['role'],
            instruction=instruction,
            model=self.model,
            tools=[self.dispatcher_mcp_toolset]
        )
        return agent

    # def get_operator_agent(self, fleet_state: str) -> Agent:
    #     config = self.agents_config['swarm_drone_operator']
    #     task_config = self.tasks_config['batch_drone_task']
        
    #     instruction = f"{config['goal']}\n{config['backstory']}\n\nTask: {task_config['description'].format(fleet_state=fleet_state)}"
        
    #     agent = Agent(
    #         name="swarm_drone_operator",
    #         description=config['role'],
    #         instruction=instruction,
    #         model=self.model,
    #         tools=[self.mcp_toolset],
    #         output_schema=BatchDroneIntents,
    #         disallow_transfer_to_parent=True,
    #         disallow_transfer_to_peers=True
    #     )
    #     return agent

    def get_drone_agent(self, drone_id: str) -> Agent:
        config = self.agents_config['single_drone_agent']
        task_config = self.tasks_config['drone_move_task']
        
        # Use .format to inject drone_id into goal and backstory if needed
        # Or just pass it in instruction
        goal = config['goal'].format(drone_id=drone_id)
        backstory = config['backstory'].format(drone_id=drone_id)
        task_desc = task_config['description'].format(drone_id=drone_id)
        
        instruction = f"{goal}\n{backstory}\n\nTask: {task_desc}"
        
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
