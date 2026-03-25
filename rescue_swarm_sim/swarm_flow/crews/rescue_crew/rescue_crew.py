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
    x: int | None = Field(None, description="Target X coordinate for move")
    y: int | None = Field(None, description="Target Y coordinate for move")
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

        # AGENT POOL: Reuse agents to avoid instantiation overhead
        self.agents_pool = {}
        self.drone_agent_config = self.agents_config['search_and_rescue_drone']
        self.dispatcher_config = self.agents_config['swarm_dispatcher']

    def _get_or_create_agent(self, agent_id: str, is_dispatcher: bool = False) -> Agent:
        """Retrieves an existing agent from the pool or creates a new one."""
        if agent_id in self.agents_pool:
            return self.agents_pool[agent_id]

        config = self.dispatcher_config if is_dispatcher else self.drone_agent_config
        
        # Include agent_id in role for identification in hooks
        role = config['role']
        if not is_dispatcher:
            role = f"{role} ({agent_id})"

        agent = Agent(
            role=role,
            goal=config['goal'],
            backstory=config['backstory'],
            mcps=[self.rescue_mcp_server],
            llm=self.llm,
            verbose=True,
            reasoning=True,
            max_retry_limit=3,
            allow_delegation=False
        )
        
        self.agents_pool[agent_id] = agent
        return agent
            
    def build_dispatch_task(self) -> Task:
        """Hydrates the dispatch task with the pooled swarm_dispatcher agent."""
        task_config = self.tasks_config["dispatch_task"].copy()
        agent = self._get_or_create_agent("swarm_dispatcher", is_dispatcher=True)
        
        return Task(
            description=task_config['description'],
            expected_output=task_config['expected_output'],
            agent=agent,
            async_execution=False
        )
            
    def build_task(self, task_name: str, d_id: str, is_async: bool = True) -> Task:
        """Hydrates a task configuration into a CrewAI Task using a pooled agent."""
        task_config = self.tasks_config[task_name].copy()
        desc = task_config['description'].format(drone_id=d_id)
        
        agent = self._get_or_create_agent(d_id)
        
        return Task(
            description=desc,
            expected_output=task_config['expected_output'],
            agent=agent,
            async_execution=is_async,
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
