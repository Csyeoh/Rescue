import os
import yaml
import threading
from pathlib import Path
from typing import Optional, Literal
from pydantic import BaseModel, Field
from crewai import Agent, Crew, Task, LLM
from crewai.events import (
    AgentExecutionStartedEvent,
    AgentExecutionCompletedEvent,
    LLMCallCompletedEvent,
    ToolUsageStartedEvent,
    ToolUsageFinishedEvent,
)
from crewai.events import BaseEventListener
try:
    from crewai.mcp import MCPServerHTTP
except Exception:
    MCPServerHTTP = None

# Load .env from project root
from dotenv import load_dotenv
_env_path = Path(__file__).resolve().parents[3] / '.env'  # rescue_swarm_sim/.env
load_dotenv(_env_path)


# ──────────────────────────────────────────────
# LLM Configuration — reads from .env
# ──────────────────────────────────────────────

def _build_llm() -> LLM:
    """Resolve the LLM provider from environment variables."""
    use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"

    if use_local:
        model = os.getenv("LOCAL_MODEL", "ollama/llama3.1")
        base_url = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
        print(f"[LLM] {model} @ {base_url}")
        return LLM(
            model=model,
            base_url=base_url,
        )
    else:
        # Fallback: Gemini via OpenRouter or direct API key
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        openrouter_key = os.getenv("OPENROUTER_API_KEY", "")

        if gemini_key:
            print("[LLM] gemini/gemini-2.5-flash (via API key)")
            return LLM(
                model="gemini/gemini-2.5-flash",
                api_key=gemini_key,
            )
        elif openrouter_key:
            print("[LLM] openrouter (via API key)")
            return LLM(
                model="openrouter/google/gemini-2.5-flash",
                api_key=openrouter_key,
            )
        else:
            raise RuntimeError(
                "No LLM configured! Set USE_LOCAL_LLM=true with OLLAMA_API_BASE, "
                "or provide GEMINI_API_KEY or OPENROUTER_API_KEY in .env"
            )

# Build once at import time
_llm = _build_llm()


# ──────────────────────────────────────────────
# Structured intent the LLM must output per tick
# ──────────────────────────────────────────────

class DroneIntent(BaseModel):
    drone_id: str = Field(..., description="The ID of the drone making this decision")
    action: Literal["MOVE", "CONTINUE_CHARGING", "RETURN_TO_BASE", "THERMAL_SCAN", "IDLE"] = Field(
        ...,
        description=(
            "The single decisive action for this tick. "
            "MOVE: move 1 step (requires target_x/target_y). "
            "CONTINUE_CHARGING: stay at base, already charging. "
            "RETURN_TO_BASE: set status to RETURNING, navigate home next ticks. "
            "THERMAL_SCAN: scan current cell for survivors. "
            "IDLE: no action this tick."
        )
    )
    target_x: Optional[int] = Field(
        None,
        description="Target X coordinate for MOVE action (use step_towards tool to compute this)"
    )
    target_y: Optional[int] = Field(
        None,
        description="Target Y coordinate for MOVE action (use step_towards tool to compute this)"
    )
    new_status: Optional[Literal["SEARCHING", "CHARGING", "RETURNING", "IDLE"]] = Field(
        None,
        description="Optional status transition to apply alongside the action"
    )
    rationale: str = Field(
        ...,
        description="Concise reasoning including exact battery math (e.g. 'battery=63, dist_to_base=8, safe_margin=2, 63>10=true, continuing search')"
    )


# ──────────────────────────────────────────────
# Agent Thinking Logger (CrewAI Event Listener)
# Collects per-tick reasoning and tool calls for
# the WebSocket broadcast after each tick.
# ──────────────────────────────────────────────

class AgentThinkingLogger(BaseEventListener):
    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self._logs: list[dict] = []

    def setup_listeners(self, crewai_event_bus):

        @crewai_event_bus.on(AgentExecutionStartedEvent)
        def on_agent_start(source, event):
            drone_id = getattr(event, 'drone_id', None) or getattr(source, 'drone_id', None) or "unknown"
            role = getattr(event.agent, 'role', 'Drone Agent')
            entry = {"type": "agent_thinking_start", "drone_id": drone_id, "role": role}
            with self._lock:
                self._logs.append(entry)
            print(f"[AGENT] [{role}] started thinking...")

        @crewai_event_bus.on(LLMCallCompletedEvent)
        def on_llm_response(source, event):
            output = getattr(event, 'output', None) or getattr(event, 'response', '')
            entry = {"type": "llm_response", "output": str(output)[:500]}
            with self._lock:
                self._logs.append(entry)

        @crewai_event_bus.on(ToolUsageStartedEvent)
        def on_tool_use(source, event):
            tool_name = getattr(event, 'tool_name', 'unknown')
            tool_input = getattr(event, 'tool_input', {})
            entry = {"type": "tool_call", "tool": tool_name, "input": str(tool_input)}
            with self._lock:
                self._logs.append(entry)
            print(f"[TOOL] called: {tool_name}({tool_input})")

        @crewai_event_bus.on(ToolUsageFinishedEvent)
        def on_tool_done(source, event):
            tool_name = getattr(event, 'tool_name', 'unknown')
            result = getattr(event, 'output', getattr(event, 'result', ''))
            entry = {"type": "tool_result", "tool": tool_name, "result": str(result)[:300]}
            with self._lock:
                self._logs.append(entry)
            print(f"[OK] {tool_name} result: {str(result)[:100]}")

        @crewai_event_bus.on(AgentExecutionCompletedEvent)
        def on_agent_done(source, event):
            output = getattr(event, 'output', '')
            role = getattr(event.agent, 'role', 'Drone Agent')
            entry = {"type": "agent_done", "role": role, "output": str(output)[:300]}
            with self._lock:
                self._logs.append(entry)
            print(f"[DONE] [{role}] completed. Final: {str(output)[:80]}...")

    def get_and_flush_logs(self) -> list[dict]:
        """Returns all buffered log entries and clears the buffer. Call after each tick."""
        with self._lock:
            logs = list(self._logs)
            self._logs.clear()
        return logs


# Singleton instance — used by the flow to harvest logs after each tick
thinking_logger = AgentThinkingLogger()


# ──────────────────────────────────────────────
# RescueCrew
# ──────────────────────────────────────────────

from .http_tools import (
    check_battery_tool,
    get_status_tool,
    get_current_pos_tool,
    get_next_waypoint_tool,
    get_thermal_memory_tool,
    step_towards_tool,
    thermal_scan_preview_tool,
    submit_intent_tool,
    get_distance_to_base_tool,
    get_mission_data_tool,
)


class RescueCrew:
    """Provides the instantiated Agent and dynamic Task configurations for the Swarm."""
    def __init__(self):
        base_path = Path(__file__).parent / 'config'
        with open(base_path / 'agents.yaml', 'r') as f:
            self.agents_config = yaml.safe_load(f)
        with open(base_path / 'tasks.yaml', 'r') as f:
            self.tasks_config = yaml.safe_load(f)

    def search_and_rescue_drone(self) -> Agent:
        """Returns a the agent instance."""
        transport = os.getenv("CREW_MCP_TRANSPORT", "http").lower()
        if transport == "http" and MCPServerHTTP is not None:
            url = os.getenv("RESCUE_MCP_HTTP_URL", "http://localhost:9001/mcp")
            return Agent(
                config=self.agents_config['search_and_rescue_drone'],
                llm=_llm,
                mcps=[MCPServerHTTP(url=url, streamable=True, cache_tools_list=True)],
                verbose=True
            )
        tools = [
            check_battery_tool,
            get_status_tool,
            get_current_pos_tool,
            get_next_waypoint_tool,
            get_thermal_memory_tool,
            step_towards_tool,
            thermal_scan_preview_tool,
            submit_intent_tool,
            get_distance_to_base_tool,
            get_mission_data_tool,
        ]
        tools = [t for t in tools if t]
        return Agent(
            config=self.agents_config['search_and_rescue_drone'],
            llm=_llm,
            tools=tools,
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
            async_execution=task_config.get('async_execution', True)
        )

    def crew(self, tasks: list[Task]) -> Crew:
        if tasks:
            for t in tasks:
                t.async_execution = False

        crew_instance = Crew(
            agents=[t.agent for t in tasks if t.agent],
            tasks=tasks,
            verbose=True,
            cache=False,  # Disable caching: each drone must query live sim state
        )
        # Register the thinking logger to capture tool calls and logic for the UI
        try:
            thinking_logger.setup_listeners(crew_instance.event_bus)
        except Exception as e:
            print(f"[RESCUE CREW] Warning: Could not setup listeners: {e}")
            
        return crew_instance
