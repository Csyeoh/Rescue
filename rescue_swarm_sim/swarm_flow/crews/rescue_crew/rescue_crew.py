import os
import yaml
import sys
from pathlib import Path
from pydantic import BaseModel, Field
from crewai import Agent, Crew, Task, LLM
from crewai.mcp import MCPServerStdio
from dotenv import load_dotenv

load_dotenv()

class DroneIntent(BaseModel):
    drone_id: str = Field(..., description="The ID of the drone")
    action: str = Field(..., description="The action: 'move', 'wait', or 'scan'")
    x: int = Field(None, description="Target X coordinate for move")
    y: int = Field(None, description="Target Y coordinate for move")
    status: str = Field(..., description="The new status of the drone (SEARCHING, IDLE, RETURNING, CHARGING)")

class RescueCrew:
    def __init__(self):
        # Load configs
        base_path = Path(__file__).parent / 'config'
        with open(base_path / 'agents.yaml', 'r') as f:
            self.agents_config = yaml.safe_load(f)
        with open(base_path / 'tasks.yaml', 'r') as f:
            self.tasks_config = yaml.safe_load(f)
        
        # Configure Gemini
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment.")
        
        self.llm = LLM(model="gemini/gemini-2.5-flash")

        # Initialize MCP Server
        mcp_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "mcp_server.py"))
        self.rescue_mcp_server = MCPServerStdio(
            command=sys.executable, 
            args=[mcp_path]
        )

        # Store the agent config for per-task instantiation
        self.drone_agent_config = self.agents_config['search_and_rescue_drone']
            
    def build_task(self, task_name: str, d_id: str, is_async: bool = True) -> Task:
        """Hydrates a task configuration into a CrewAI Task."""
        task_config = self.tasks_config[task_name].copy()
        desc = task_config['description'].format(drone_id=d_id)
        
        # Instantiate a unique agent for this task
        agent = Agent(
            role=self.drone_agent_config['role'],
            goal=self.drone_agent_config['goal'],
            backstory=self.drone_agent_config['backstory'],
            mcps=[self.rescue_mcp_server],
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )
        
        return Task(
            description=desc,
            expected_output=task_config['expected_output'],
            agent=agent,
            async_execution=is_async, # Configurable for anchor pattern
            output_pydantic=DroneIntent
        )
        
    def crew(self, tasks: list[Task]) -> Crew:
        """Assembles the crew using the unique agents from the tasks."""
        return Crew(
            agents=[task.agent for task in tasks if task.agent],
            tasks=tasks,
            verbose=True,
            output_log_file='logs.json'
        )
