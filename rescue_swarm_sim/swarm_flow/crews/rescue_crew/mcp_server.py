from fastmcp import FastMCP
from typing import Optional
import argparse
import os
import requests

# Initialize the MCP Server (Perception Layer only)
mcp = FastMCP("RescueSwarm")

BASE_URL = os.getenv("RESCUE_API_MCP_BASE_URL", "http://127.0.0.1:8000/api/mcp")

@mcp.tool()
def check_battery(drone_id: str) -> int:
    """Returns the current battery level (0-100) for a drone."""
    try:
        r = requests.get(f"{BASE_URL}/drone/{drone_id}/battery")
        return r.json() if r.status_code == 200 else -1
    except: return -1

@mcp.tool()
def get_status(drone_id: str) -> str:
    """Returns the current status (SEARCHING, RETURNING, etc.)."""
    try:
        r = requests.get(f"{BASE_URL}/drone/{drone_id}/status")
        return r.json() if r.status_code == 200 else "Error: sim offline"
    except: return "Error: sim offline"

@mcp.tool()
def get_current_pos(drone_id: str) -> dict:
    """Returns the current (x, y) location of a given drone."""
    try:
        r = requests.get(f"{BASE_URL}/drone/{drone_id}/pos")
        return r.json() if r.status_code == 200 else {"error": "no sim"}
    except: return {"error": "no sim"}

@mcp.tool()
def get_next_waypoint(drone_id: str) -> dict:
    """Returns the next undiscovered (x, y) target for this drone."""
    try:
        r = requests.get(f"{BASE_URL}/drone/{drone_id}/waypoints")
        if r.status_code == 200:
            wps = r.json()
            if wps:
                return {"has_waypoint": True, "x": wps[0][0], "y": wps[0][1], "remaining_count": len(wps)}
        return {"has_waypoint": False, "remaining_count": 0}
    except: return {"error": "no sim"}

@mcp.tool()
def get_thermal_memory(drone_id: str) -> list:
    """Returns the list of detected thermal coordinates."""
    try:
        r = requests.get(f"{BASE_URL}/drone/{drone_id}/thermal")
        return r.json() if r.status_code == 200 else []
    except: return []

@mcp.tool()
def scan_adjacent(drone_id: str) -> dict:
    """Scan the 4 adjacent cells around the drone and return obstacle/thermal/survivor signals."""
    try:
        r = requests.get(f"{BASE_URL}/drone/{drone_id}/scan_adjacent")
        return r.json() if r.status_code == 200 else {"error": "API error"}
    except:
        return {"error": "no sim"}

@mcp.tool()
def step_towards(drone_id: str, target_x: int, target_y: int) -> dict:
    """Computes the optimal 1-step move (nx, ny) towards a target, avoiding obstacles."""
    try:
        r = requests.get(f"{BASE_URL}/drone/{drone_id}/step_towards", params={"tx": target_x, "ty": target_y})
        return r.json() if r.status_code == 200 else {"error": "API error"}
    except: return {"error": "no sim"}

@mcp.tool()
def thermal_scan_preview(drone_id: str) -> str:
    """Quick preview of current cell for heat signatures (does not rescue)."""
    try:
        r = requests.get(f"{BASE_URL}/drone/{drone_id}/thermal_scan")
        return r.json() if r.status_code == 200 else "Error"
    except: return "Error"

@mcp.tool()
def submit_intent(
    drone_id: str,
    action: str,
    target_x: Optional[int] = None,
    target_y: Optional[int] = None,
    rationale: Optional[str] = None,
    new_status: Optional[str] = None,
) -> str:
    """Submit a drone intent to the backend to be applied to the simulation.

    Note: action must be one of MOVE / THERMAL_SCAN / RETURN_TO_BASE / CONTINUE_CHARGING / IDLE.
    Values like SEARCHING/CHARGING/RETURNING are statuses and belong in new_status, not action.
    """
    try:
        allowed_actions = {"MOVE", "THERMAL_SCAN", "RETURN_TO_BASE", "CONTINUE_CHARGING", "IDLE"}
        allowed_statuses = {"SEARCHING", "CHARGING", "RETURNING", "IDLE"}

        action_norm = (action or "").strip().upper()
        action_aliases = {
            "SCAN": "THERMAL_SCAN",
            "THERMAL": "THERMAL_SCAN",
            "THERMALSCAN": "THERMAL_SCAN",
            "RETURN": "RETURN_TO_BASE",
            "CHARGE": "CONTINUE_CHARGING",
        }
        action_norm = action_aliases.get(action_norm, action_norm)

        if action_norm in allowed_statuses and action_norm not in allowed_actions:
            if new_status is None:
                new_status = action_norm
            if action_norm == "SEARCHING":
                action_norm = "MOVE"
            elif action_norm == "RETURNING":
                action_norm = "RETURN_TO_BASE"
            elif action_norm == "CHARGING":
                action_norm = "CONTINUE_CHARGING"
            else:
                action_norm = "IDLE"
            if rationale is None:
                rationale = ""
            rationale = (rationale + " | " if rationale else "") + "Coerced status-like action into new_status."

        if action_norm not in allowed_actions:
            if rationale is None:
                rationale = ""
            rationale = (rationale + " | " if rationale else "") + f"Unknown action '{action_norm}', defaulting to IDLE."
            action_norm = "IDLE"

        pos_r = requests.get(f"{BASE_URL}/drone/{drone_id}/pos")
        pos = pos_r.json() if pos_r.status_code == 200 else {"x": 9, "y": 9}
        cx, cy = int(pos.get("x", 9)), int(pos.get("y", 9))

        if action_norm == "MOVE" and target_x is not None and target_y is not None:
            if int(target_x) == cx and int(target_y) == cy:
                action_norm = "IDLE"
                if rationale is None:
                    rationale = ""
                rationale = (rationale + " | " if rationale else "") + "MOVE target equals current position; converted to IDLE."
            if abs(cx - int(target_x)) + abs(cy - int(target_y)) != 1:
                step_r = requests.get(
                    f"{BASE_URL}/drone/{drone_id}/step_towards",
                    params={"tx": int(target_x), "ty": int(target_y)}
                )
                step = step_r.json() if step_r.status_code == 200 else {"x": cx, "y": cy}
                target_x, target_y = int(step.get("x", cx)), int(step.get("y", cy))
                if rationale is None:
                    rationale = ""
                rationale = (rationale + " | " if rationale else "") + f"Coerced MOVE target to 1-step ({target_x},{target_y})."

        if target_x is None or target_y is None:
            if action_norm == "MOVE":
                wp_r = requests.get(f"{BASE_URL}/drone/{drone_id}/waypoints")
                wps = wp_r.json() if wp_r.status_code == 200 else []
                if wps:
                    tx, ty = int(wps[0][0]), int(wps[0][1])
                else:
                    tx, ty = (0, 0) if (cx, cy) == (9, 9) else (9, 9)

                step_r = requests.get(f"{BASE_URL}/drone/{drone_id}/step_towards", params={"tx": tx, "ty": ty})
                step = step_r.json() if step_r.status_code == 200 else {"x": cx, "y": cy}
                target_x, target_y = int(step.get("x", cx)), int(step.get("y", cy))
                if rationale is None:
                    rationale = f"Auto-filled MOVE target via step_towards to ({target_x},{target_y})"
            else:
                target_x, target_y = cx, cy
                if rationale is None:
                    rationale = "Auto-filled target to current position"
        if rationale is None:
            rationale = "No rationale provided"
    except Exception:
        if target_x is None:
            target_x = 9
        if target_y is None:
            target_y = 9
        if rationale is None:
            rationale = "Auto-filled intent fields after error"

    payload = {
        "drone_id": drone_id,
        "action": action_norm,
        "target_x": target_x,
        "target_y": target_y,
        "rationale": rationale,
        "new_status": new_status
    }
    try:
        r = requests.post(f"{BASE_URL}/intent", json=payload)
        if r.status_code == 200:
            return r.text[:300]
        return f"Error: {r.status_code}"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def get_distance_to_base(drone_id: str) -> dict:
    """Returns distance to (9,9) and safety status."""
    try:
        pos_r = requests.get(f"{BASE_URL}/drone/{drone_id}/pos")
        batt_r = requests.get(f"{BASE_URL}/drone/{drone_id}/battery")
        if pos_r.status_code != 200 or batt_r.status_code != 200:
            return {"error": "sim offline"}
        pos = pos_r.json()
        batt = batt_r.json()
        if "x" not in pos: return {"error": "no pos"}
        dist = abs(pos["x"] - 9) + abs(pos["y"] - 9)
        return {
            "current_pos": pos,
            "base_pos": {"x": 9, "y": 9},
            "distance": dist,
            "safe_to_continue": batt > dist + 5
        }
    except: return {"error": "calculation error"}

@mcp.tool()
def get_mission_data() -> dict:
    """Returns global mission status and survivor counts."""
    try:
        r = requests.get(f"{BASE_URL}/mission_data")
        return r.json() if r.status_code == 200 else {"mission_status": "error"}
    except: return {"mission_status": "error"}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", default=os.getenv("MCP_TRANSPORT", "stdio"))
    parser.add_argument("--host", default=os.getenv("MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MCP_PORT", "9001")))
    args = parser.parse_args()
    mcp.run(transport=args.transport, host=args.host, port=args.port)
