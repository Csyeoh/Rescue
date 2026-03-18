from fastmcp import FastMCP
from typing import Optional
import time
import json
import sys
import os
import requests

# Initialize the MCP Server (Perception Layer only)
mcp = FastMCP("RescueSwarm")

BASE_URL = "http://127.0.0.1:8000/api/mcp"

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
def submit_intent(drone_id: str, action: str, target_x: int, target_y: int, rationale: str, new_status: Optional[str] = None) -> str:
    """
    REQUIRED FINAL STEP: Submit your final decision for this tick.
    Valid actions: MOVE, THERMAL_SCAN, RETURN_TO_BASE, CONTINUE_CHARGING, IDLE.
    Valid statuses: SEARCHING, CHARGING, RETURNING, IDLE.
    """
    payload = {
        "drone_id": drone_id,
        "action": action,
        "target_x": target_x,
        "target_y": target_y,
        "rationale": rationale,
        "new_status": new_status
    }
    # This just returns success to the agent; the Flow captures tool calls via thinking_logger
    return f"Intent for {drone_id} submitted: {action} to ({target_x}, {target_y})"

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
    mcp.run()
