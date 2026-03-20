from fastmcp import FastMCP
import httpx
import json

# Initialize the MCP Server
mcp = FastMCP("RescueSwarm")

API_URL = "http://localhost:8000/api"

@mcp.tool()
async def check_mission_status() -> str:
    """Returns survivor counts and whether the mission objective has been met."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/mission/status")
        data = r.json()
        status = "COMPLETE" if data.get('is_complete') else "ACTIVE"
        return f"Mission {status}: {data.get('found_survivors', 0)}/{data.get('total_survivors', 0)} survivors found."

@mcp.tool()
async def trigger_global_killswitch() -> str:
    """Immediately halts the simulation engine. Use this when mission objectives are met or in emergency aborts."""
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{API_URL}/mission/killswitch")
        return r.json().get("message", "Killswitch triggered.")

@mcp.tool()
async def clear_all_assignments() -> str:
    """Wipes all pending drone waypoints from the database. Use before re-partitioning or RTB."""
    async with httpx.AsyncClient() as client:
        r = await client.delete(f"{API_URL}/waypoints")
        return r.json().get("message", "Assignments cleared.")

@mcp.tool()
async def assign_mission_waypoints(drone_id: str, waypoints: list[dict]) -> str:
    """
    Assigns a list of waypoints to a specific drone.
    Example waypoints: [{"x": 10, "y": 12}, {"x": 11, "y": 12}]
    """
    payload = {"drone_id": drone_id, "waypoints": waypoints}
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{API_URL}/waypoints/assign", json=payload)
        return f"Assigned {r.json().get('count', 0)} waypoints to {drone_id}."

@mcp.tool()
async def get_swarm_assignment_status() -> str:
    """Returns the total number of pending waypoints across all drones."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/waypoints/status")
        return f"Total pending waypoints: {r.json().get('pending_waypoints', 0)}"

@mcp.tool()
async def post_log(agent_id: str, message: str) -> str:
    """Posts a system or agent log message to the terminal UI."""
    payload = {"agent_id": agent_id, "message": message}
    async with httpx.AsyncClient() as client:
        await client.post(f"{API_URL}/logs", json=payload)
        return "Log posted."

@mcp.tool()
async def discover_drones() -> list[str]:
    """Returns a list of all active drone IDs available for command in the simulation."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/drones")
        return r.json()

@mcp.tool()
async def get_battery_status(drone_id: str) -> str:
    """Returns the current battery level (0-100) of a specific drone."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/drone/{drone_id}/battery")
        battery = r.json()
        if battery == -1:
            return f"Error: {drone_id} not found."
        return f"{drone_id} battery is at {battery}%"

@mcp.tool()
async def get_hardware_status(drone_id: str) -> str:
    """Returns the full diagnostic hardware status of a drone including location, battery, flight state, and system health."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/drone/{drone_id}/hardware")
        data = r.json()
        if "error" in data:
            return f"Error: {drone_id} not found."
        
        return f"""[{drone_id} HARDWARE DIAGNOSTIC]
- Location: ({data['location']['x']}, {data['location']['y']})
- Flight State: {data['flight_state']}
- Mission Status: {data['mission_status']}
- Battery: {data['battery']}%
- Core Health: {data['health']}"""

@mcp.tool()
async def move_drone(drone_id: str, x: int, y: int) -> str:
    """
    Moves a rescue drone to specific (x, y) coordinates on the grid.
    Includes Passive Sensors: Scans adjacent grids for obstacles and thermal auras upon arrival.
    """
    payload = {"drone_id": drone_id, "action": "MOVE", "target_x": x, "target_y": y}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(f"{API_URL}/intent", json=payload)
        return str(r.json())

@mcp.tool()
async def thermal_scan(drone_id: str) -> str:
    """
    Performs a high-powered thermal scan at the drone's current location AND 4 adjacent grids.
    Returns a message indicating if a hidden survivor was found.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{API_URL}/drone/{drone_id}/thermal_scan")
        return str(r.json())

@mcp.tool()
async def get_known_map() -> str:
    """
    Returns the known layout of the 20x20 grid, including altitudes and terrain types.
    Use this to analyze the landscape and run clustering algorithms.
    """
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/mission/map")
        data = r.json()
        if isinstance(data, dict) and "error" in data:
            return f"Error: {data['error']}"
        return "GRID DATA (x, y, altitude, type):\n" + json.dumps(data)

if __name__ == "__main__":
    mcp.run_stdio()
