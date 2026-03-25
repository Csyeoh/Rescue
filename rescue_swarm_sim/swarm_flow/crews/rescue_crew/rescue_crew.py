import os
import yaml
import sys
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List
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

class BatchDroneIntents(BaseModel):
    intents: list[DroneIntent] = Field(..., description="List of intents for all drones processed")

class RescueCrew:
    def __init__(self):
        # Load configs
        base_path = Path(__file__).parent / 'config'
        with open(base_path / 'agents.yaml', 'r') as f:
            self.agents_config = yaml.safe_load(f)
        with open(base_path / 'tasks.yaml', 'r') as f:
            self.tasks_config = yaml.safe_load(f)
        
        # Configure Dual LLM Support (Local vs Gemini)
        use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
        if use_local:
            model = os.getenv("LOCAL_MODEL", "ollama/llama3.1")
            base_url = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
            print(f"[LLM] Using Local Model → {model} @ {base_url}")
            self.llm = LLM(model=model, base_url=base_url)
        else:
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY not found in environment (and USE_LOCAL_LLM is false).")
            print("[LLM] Using Gemini API → gemini-2.5-flash")
            self.llm = LLM(model="gemini/gemini-2.5-flash", api_key=api_key)

        # Initialize MCP Server
        mcp_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "mcp_server.py"))
        self.rescue_mcp_server = MCPServerStdio(
            command=sys.executable, 
            args=[mcp_path]
        )

        # AGENT POOL: Reuse agents to avoid instantiation overhead
        self.agents_pool = {}
        self.operator_config = self.agents_config['swarm_drone_operator']
        self.dispatcher_config = self.agents_config['swarm_dispatcher']

    def _get_or_create_agent(self, agent_id: str) -> Agent:
        """Retrieves an existing agent from the pool or creates a new one."""
        if agent_id in self.agents_pool:
            return self.agents_pool[agent_id]

        config = self.dispatcher_config if agent_id == "swarm_dispatcher" else self.operator_config
        
        agent = Agent(
            role=config['role'],
            goal=config['goal'],
            backstory=config['backstory'],
            mcps=[self.rescue_mcp_server],
            llm=self.llm,
            verbose=True,
            reasoning=True,
            max_retry_limit=10,
            allow_delegation=False
        )
        
        self.agents_pool[agent_id] = agent
        return agent
            
    def build_dispatch_task(self) -> Task:
        """Hydrates the dispatch task with the pooled swarm_dispatcher agent."""
        task_config = self.tasks_config["dispatch_task"].copy()
        agent = self._get_or_create_agent("swarm_dispatcher")
        
        return Task(
            description=task_config['description'],
            expected_output=task_config['expected_output'],
            agent=agent,
            async_execution=False
        )
            
    def build_batch_task(self, fleet_state_str: str) -> Task:
        """Hydrates the batch task configuration for the drone operator."""
        task_config = self.tasks_config["batch_drone_task"].copy()
        desc = task_config['description'].format(fleet_state=fleet_state_str)
        
        agent = self._get_or_create_agent("swarm_drone_operator")
        
        return Task(
            description=desc,
            expected_output=task_config['expected_output'],
            agent=agent,
            async_execution=False,
            output_pydantic=BatchDroneIntents
        )
        
    def crew(self, tasks: list[Task]) -> Crew:
        """Assembles the crew using the unique agents from the tasks."""
        return Crew(
            agents=[task.agent for task in tasks if task.agent],
            tasks=tasks,
            verbose=True
        )
