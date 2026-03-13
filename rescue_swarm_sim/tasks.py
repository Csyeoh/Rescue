import json

try:
    from crewai import Task
except Exception as e:  # pragma: no cover
    Task = None
    _CREWAI_IMPORT_ERROR = e


RISK_MAP_PROMPT = """
You are the Terrain Analyst.

Use the tool read_world_state to fetch:
- grid: list of {x,y,altitude,is_obstacle}
- environment: {global_water_level, water_speed}

Produce a Flood Risk Map for every tile in the 20x20 grid:
- Priority 1: Flooding Soon
- Priority 2: Safe

Use a simple, explicit rule based on altitude, global_water_level, and projected rise over the next 30 seconds:
projected_water = global_water_level + (water_speed * 30)
Priority 1 if altitude <= projected_water, else Priority 2.

Return ONLY valid JSON of the form:
{
  "rule": "...",
  "environment": {"global_water_level": number, "water_speed": number, "projected_water": number},
  "priority_1": [{"x":int,"y":int}, ...],
  "priority_2": [{"x":int,"y":int}, ...]
}

Do not wrap the JSON in markdown fences. Do not include any text outside the JSON.
"""


SWARM_DEPLOYMENT_PROMPT = """
You are the Swarm Commander.

Inputs:
- The previous task output is the Flood Risk Map JSON.
- You MUST call read_world_state to get current drones (id,x,y,battery).

Mission:
1) Cluster Priority 1 tiles into K clusters, where K = number of active drones.
   - You may use sklearn.cluster.KMeans if available in your environment, otherwise implement a simple centroid-based clustering heuristic.
2) For each drone, pick a cluster (centroid or representative tile) to dispatch toward.
3) BEFORE moving a drone, you MUST call calculate_path_and_battery(start_x,start_y,target_x,target_y).
   - Enforce the 10% Reserve Constraint:
     dispatch only if (current_battery - battery_required) >= 10
4) Execute movement by stepping through the returned path, using execute_drone_move for each (x,y) step.
5) If any execute_drone_move response indicates a faint thermal aura, immediately call execute_thermal_scan for that drone.

Output requirements:
- Return ONLY valid JSON.
- Include an explicit Battery Math Audit per attempted dispatch with:
  - drone_id, current_battery, steps_to_target, steps_to_base, battery_required, reserve_after, allowed (true/false)
- Include a compact Mission Log list of strings summarizing actions taken.

JSON shape:
{
  "assignments": [{"drone_id":"...", "target":{"x":int,"y":int}, "cluster_size":int}],
  "battery_audit": [{"drone_id":"...", "current_battery":int, "steps_to_target":int, "steps_to_base":int, "battery_required":int, "reserve_after":int, "allowed":bool}],
  "mission_log": ["...", "..."]
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
        expected_output="JSON Flood Risk Map with Priority 1 and Priority 2 tile lists.",
        agent=terrain_analyst,
    )

    t2 = Task(
        description=SWARM_DEPLOYMENT_PROMPT.strip(),
        expected_output="JSON mission result with assignments, battery audit, and mission log.",
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
