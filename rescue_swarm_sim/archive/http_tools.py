import os
from typing import Optional
import requests

try:
    from crewai.tools import tool as crewai_tool
except Exception:  # pragma: no cover
    crewai_tool = None


BASE_URL = os.getenv("MCP_BASE_URL", "http://127.0.0.1:8000/api/mcp")


def _get(path: str, *, params: Optional[dict] = None):
    r = requests.get(f"{BASE_URL}{path}", params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def _post(path: str, *, payload: dict):
    r = requests.post(f"{BASE_URL}{path}", json=payload, timeout=10)
    r.raise_for_status()
    return r.json()


check_battery_tool = None
get_status_tool = None
get_current_pos_tool = None
get_next_waypoint_tool = None
get_thermal_memory_tool = None
step_towards_tool = None
thermal_scan_preview_tool = None
submit_intent_tool = None
get_distance_to_base_tool = None
get_mission_data_tool = None


if crewai_tool:
    @crewai_tool("check_battery")
    def check_battery_tool(drone_id: str) -> int:
        """Return the current battery level (0-100) for a drone."""
        return int(_get(f"/drone/{drone_id}/battery"))

    @crewai_tool("get_status")
    def get_status_tool(drone_id: str) -> str:
        """Return the current status string for a drone."""
        return str(_get(f"/drone/{drone_id}/status"))

    @crewai_tool("get_current_pos")
    def get_current_pos_tool(drone_id: str) -> dict:
        """Return the current (x, y) position for a drone."""
        return _get(f"/drone/{drone_id}/pos")

    @crewai_tool("get_next_waypoint")
    def get_next_waypoint_tool(drone_id: str) -> dict:
        """Return the next undiscovered waypoint for the drone, if any."""
        wps = _get(f"/drone/{drone_id}/waypoints")
        if wps:
            return {"has_waypoint": True, "x": wps[0][0], "y": wps[0][1], "remaining_count": len(wps)}
        return {"has_waypoint": False, "remaining_count": 0}

    @crewai_tool("get_thermal_memory")
    def get_thermal_memory_tool(drone_id: str) -> list:
        """Return the drone's cached thermal memory coordinates."""
        return _get(f"/drone/{drone_id}/thermal")

    @crewai_tool("step_towards")
    def step_towards_tool(drone_id: str, target_x: int, target_y: int) -> dict:
        """Compute a 1-step move towards a target, avoiding known obstacles."""
        return _get(f"/drone/{drone_id}/step_towards", params={"tx": target_x, "ty": target_y})

    @crewai_tool("thermal_scan_preview")
    def thermal_scan_preview_tool(drone_id: str) -> str:
        """Preview whether the current cell contains a survivor signature."""
        return str(_get(f"/drone/{drone_id}/thermal_scan"))

    @crewai_tool("submit_intent")
    def submit_intent_tool(
        drone_id: str,
        action: str,
        target_x: int,
        target_y: int,
        rationale: str,
        new_status: Optional[str] = None,
    ) -> dict:
        """Submit the drone's final intent decision for this tick."""
        payload = {
            "drone_id": drone_id,
            "action": action,
            "target_x": int(target_x),
            "target_y": int(target_y),
            "rationale": rationale,
            "new_status": new_status,
        }
        return _post("/intent", payload=payload)

    @crewai_tool("get_distance_to_base")
    def get_distance_to_base_tool(drone_id: str) -> dict:
        """Return Manhattan distance to base and whether battery is safe to continue."""
        pos = _get(f"/drone/{drone_id}/pos")
        batt = int(_get(f"/drone/{drone_id}/battery"))
        if "x" not in pos or "y" not in pos:
            return {"error": "no pos"}
        dist = abs(int(pos["x"]) - 9) + abs(int(pos["y"]) - 9)
        return {
            "current_pos": pos,
            "base_pos": {"x": 9, "y": 9},
            "distance": dist,
            "safe_to_continue": batt > dist + 5,
        }

    @crewai_tool("get_mission_data")
    def get_mission_data_tool() -> dict:
        """Return global mission status and survivor counts."""
        return _get("/mission_data")
