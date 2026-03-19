import os

from dotenv import load_dotenv

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    ChatGoogleGenerativeAI = None

try:
    from crewai import Agent, LLM
except Exception as e:
    Agent = None
    LLM = None
    _CREWAI_IMPORT_ERROR = e

import ai_tools


# ─── Model selection ─────────────────────────────────────────────────────────
# Bypassing OpenRouter due to 402/404 blocking errors on free tiers.
# Using Google Direct API with Gemini 2.5 Flash for high speed and generous free limits.

def build_llm():
    load_dotenv()
    
    use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
    local_model = os.getenv("LOCAL_MODEL", "ollama/llama3.1")
    
    if use_local:
        if LLM is None:
            raise RuntimeError("crewai.LLM failed to import.")
            
        print(f"[LLM] Using Local Model → {local_model}")
        return LLM(
            model=local_model,
            base_url=os.getenv("OLLAMA_API_BASE", "http://localhost:11434"),
            temperature=0.1
        )

    # Enforce Google API Key usage
    google_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not google_key:
        raise ValueError("No GEMINI_API_KEY found in .env file (and USE_LOCAL_LLM is false).")
    
    os.environ["GOOGLE_API_KEY"] = google_key
    
    if ChatGoogleGenerativeAI is None:
        raise RuntimeError("langchain-google-genai is not installed.")
        
    print("[LLM] Using Google Direct → gemini-2.5-flash")
    return ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1)


def build_agents():
    if Agent is None:
        raise RuntimeError(
            f"crewai is not installed or failed to import: {_CREWAI_IMPORT_ERROR}. "
            "Install with: pip install crewai"
        )

    llm = build_llm()

    tools = []
    if getattr(ai_tools, "log_mission_reasoning_tool", None):
        tools = [ai_tools.log_mission_reasoning_tool]

    terrain_analyst = Agent(
        role="Geospatial Data Analyst",
        goal="Determine areas of challenging terrain based on the 'Answer Plane' (known altitude).",
        backstory="You are a GIS analyst mapping disaster contours. You identify bounding boxes covering difficult terrain.",
        llm=llm,
        tools=tools,
        allow_delegation=False,
        verbose=False,
    )

    swarm_commander = Agent(
        role="Central Swarm Commander",
        goal="Explain the strategic reasoning for the deterministic Greedy Weighted BFS zone partition and log it using `log_mission_reasoning_tool`.",
        backstory="You are a tactical coordinator. The deterministic algorithm has already partitioned the map based on terrain weight and drone battery. Your job is to narrate the tactical reasoning step-by-step for the mission log.",
        llm=llm,
        tools=tools,
        allow_delegation=False,
        verbose=False,
    )

    return terrain_analyst, swarm_commander
