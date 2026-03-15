import json

try:
    from crewai import Task
except Exception as e:  # pragma: no cover
    Task = None
    _CREWAI_IMPORT_ERROR = e


RISK_MAP_PROMPT = """
You are the Geospatial Data Analyst.

Your job is to preemptively map the terrain.
The entire map is 0-19 on X and 0-19 on Y.

Instantly partition the entire 20x20 grid into 4 distinct, non-overlapping Bounding Boxes (Quadrants).
Do NOT overthink this. Just divide the map into 4 equal rectangles.

Return ONLY valid JSON of the form:
{
  "hazard_zones": [
     {"name": "Northwest", "x_min": 0, "x_max": 9, "y_min": 0, "y_max": 9, "priority": 1},
     {"name": "Northeast", "x_min": 10, "x_max": 19, "y_min": 0, "y_max": 9, "priority": 1},
     ...
  ]
}
Do not wrap the JSON in markdown fences. Do not include any text outside the JSON.
"""

SWARM_DEPLOYMENT_PROMPT = """
You are the Central Swarm Commander. You MUST reason out loud before every action.

Step 1: Call `get_drone_status` to retrieve all drones and their battery levels and zone assignments.

Step 2: For each idle drone (UNASSIGNED or is_complete=true), write a reasoning statement like:
  "drone_1 has 84% battery. The NW quadrant is nearby. Assigning drone_1 to X:0-9, Y:0-9."
  "drone_2 has 31% battery. Battery is low, so I will assign it the smallest closest zone."

Step 3: Based on your battery reasoning, call `assign_drone_zone(drone_id, x_min, x_max, y_min, y_max)` 
for each idle drone. Use the 4 Quadrants from the Analyst:
  - NW: x_min=0, x_max=9, y_min=0, y_max=9
  - NE: x_min=10, x_max=19, y_min=0, y_max=9
  - SW: x_min=0, x_max=9, y_min=10, y_max=19
  - SE: x_min=10, x_max=19, y_min=10, y_max=19
  Do NOT assign overlapping zones.

Return ONLY valid JSON with your reasoning and actions:
{
  "mission_log": [
    "REASONING: drone_1 has 84% battery — assigning it the large NW quadrant (0-9, 0-9) since it has enough fuel.",
    "ACTION: Assigned drone_1 to X:0-9, Y:0-9.",
    "REASONING: drone_2 has 32% battery — assigning the closer NE quadrant to conserve return fuel.",
    "ACTION: Assigned drone_2 to X:10-19, Y:0-9."
  ]
}

Do not wrap the JSON in markdown fences. Do not include any text outside the JSON.
"""


def build_tasks(terrain_analyst, swarm_commander):
    if Task is None:
        raise RuntimeError(
            f"crewai is not installed or failed to import: {_CREWAI_IMPORT_ERROR}. "
            "Install with: pip install crewai"
        )

    t1 = Task(
        description=RISK_MAP_PROMPT.strip(),
        expected_output="JSON list of hazard zone bounding boxes.",
        agent=terrain_analyst,
    )

    t2 = Task(
        description=SWARM_DEPLOYMENT_PROMPT.strip(),
        expected_output="JSON mission log confirming zone assignments.",
        agent=swarm_commander,
        context=[t1],
    )

    return t1, t2


def parse_json_or_none(text: str):
    if not text:
        return None

    raw = text.strip()
    if raw.startswith("```"):
        first_nl = raw.find("\n")
        if first_nl != -1:
            raw = raw[first_nl + 1 :]
        end_fence = raw.rfind("```")
        if end_fence != -1:
            raw = raw[:end_fence].strip()

    try:
        return json.loads(raw)
    except Exception:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = raw[start : end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            return None

    return None
