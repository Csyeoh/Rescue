import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

try:
    from crewai import Agent
except Exception as e:  # pragma: no cover
    Agent = None
    _CREWAI_IMPORT_ERROR = e

import ai_tools


def _ensure_google_api_key():
    load_dotenv()
    if os.getenv("GOOGLE_API_KEY"):
        return
    if os.getenv("GEMINI_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]


def build_llm():
    _ensure_google_api_key()
    return ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0.2)


def build_agents():
    if Agent is None:
        raise RuntimeError(
            f"crewai is not installed or failed to import: {_CREWAI_IMPORT_ERROR}. "
            "Install with: pip install crewai"
        )

    llm = build_llm()

    tools = []
    if (
        getattr(ai_tools, "read_world_state_tool", None)
        and getattr(ai_tools, "calculate_path_and_battery_tool", None)
        and getattr(ai_tools, "execute_drone_move_tool", None)
        and getattr(ai_tools, "execute_thermal_scan_tool", None)
    ):
        tools = [
            ai_tools.read_world_state_tool,
            ai_tools.calculate_path_and_battery_tool,
            ai_tools.execute_drone_move_tool,
            ai_tools.execute_thermal_scan_tool,
        ]

    terrain_analyst = Agent(
        role="Geospatial Data Analyst",
        goal="Transform live terrain + water physics into a clear Flood Risk Map (Priority 1 vs Priority 2) for all 20x20 tiles.",
        backstory="You are a GIS analyst for disaster response operations. You produce crisp, machine-readable risk maps from live sensor and elevation data.",
        llm=llm,
        tools=tools,
        allow_delegation=False,
        verbose=True,
    )

    swarm_commander = Agent(
        role="Tactical Swarm Commander",
        goal="Assign drones to Priority 1 clusters while enforcing the 10% reserve constraint and the Bingo Fuel check before dispatch.",
        backstory="You command autonomous rescue drones under extreme flooding conditions. You never violate safety reserves and you exploit thermal-aura cues immediately.",
        llm=llm,
        tools=tools,
        allow_delegation=False,
        verbose=True,
    )

    return terrain_analyst, swarm_commander
