import os
import yaml
from pathlib import Path
from pydantic import BaseModel, Field
from crewai import Agent, Crew, Task
from crewai.mcp import MCPServerStdio

class DroneIntent(BaseModel):
    drone_id: str = Field(..., description="The ID of the drone")
    action: str = Field(..., description="The decisive action tool call to make or status assignment")
    rationale: str = Field(..., description="The rationale for the action, specifically including battery/cost math")

rescue_mcp_server = MCPServerStdio(
    command="python", 
    args=[os.path.join(os.path.dirname(__file__), "mcp_server.py")]
)

class RescueCrew:
    """Provides the instantiated Agent and dynamic Task configurations for the Swarm."""
    def __init__(self):
        # Load configs
        base_path = Path(__file__).parent / 'config'
        with open(base_path / 'agents.yaml', 'r') as f:
            self.agents_config = yaml.safe_load(f)
        with open(base_path / 'tasks.yaml', 'r') as f:
            self.tasks_config = yaml.safe_load(f)
            
    def search_and_rescue_drone(self) -> Agent:
        return Agent(
            config=self.agents_config['search_and_rescue_drone'],
            mcps=[rescue_mcp_server],
            verbose=True
        )

    def build_task(self, task_name: str, d_id: str) -> Task:
        """Hydrates a task configuration into a CrewAI Task dynamically."""
        task_config = self.tasks_config[task_name].copy()
        
        desc = task_config['description'].format(drone_id=d_id)
        exp_out = task_config['expected_output'].format(drone_id=d_id)
        
        return Task(
            description=desc,
            expected_output=exp_out,
            agent=self.search_and_rescue_drone(),
            async_execution=task_config.get('async_execution', True),
            output_pydantic=DroneIntent
        )
        
    def crew(self, tasks: list[Task]) -> Crew:
        return Crew(
            agents=[self.search_and_rescue_drone()],
            tasks=tasks,
            verbose=True
        )
