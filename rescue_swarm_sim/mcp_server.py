from fastmcp import FastMCP
import sqlite3
import simulation
import database

# 1. Initialize the physical world before the AI connects
print("Initializing World State for MCP...")
world = simulation.initialize_world()

# Spawn two drones at Base Camp (0,0) for the AI to command
world.spawn_drone("drone_alpha", 0, 0)
world.spawn_drone("drone_beta", 0, 0)

# 2. Initialize the MCP Server
mcp = FastMCP("RescueSwarm")

@mcp.tool()
def discover_drones() -> list[str]:
    """Returns a list of all active drone IDs available for command in the simulation."""
    conn = sqlite3.connect(database.DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT drone_id FROM drones")
    drones = [row[0] for row in cursor.fetchall()]
    conn.close()
    return drones

@mcp.tool()
def get_battery_status(drone_id: str) -> str:
    """Returns the current battery level (0-100) of a specific drone."""
    conn = sqlite3.connect(database.DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT battery FROM drones WHERE drone_id=?", (drone_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return f"{drone_id} battery is at {result[0]}%"
    return f"Error: {drone_id} not found."

@mcp.tool()
def move_drone(drone_id: str, x: int, y: int) -> str:
    """
    Moves a rescue drone to specific (x, y) coordinates on the grid.
    Returns success status, battery levels, or failure reasons (e.g., path blocked by debris).
    """
    # This calls your brilliant physics engine directly!
    result = simulation.move_to(drone_id, x, y)
    return str(result)

@mcp.tool()
def thermal_scan(drone_id: str) -> str:
    """
    Performs a thermal scan at the drone's current (x, y) location.
    Returns a message indicating if a hidden survivor was found.
    """
    conn = sqlite3.connect(database.DB_NAME)
    cursor = conn.cursor()
    
    # Check where the drone currently is
    cursor.execute("SELECT x, y FROM drones WHERE drone_id=?", (drone_id,))
    drone_loc = cursor.fetchone()
    
    if not drone_loc:
        conn.close()
        return f"Error: {drone_id} not found."
    
    dx, dy = drone_loc
    
    # Check if a survivor shares those exact coordinates
    cursor.execute("SELECT survivor_id, is_discovered FROM survivors WHERE x=? AND y=?", (dx, dy))
    survivor = cursor.fetchone()
    
    if survivor:
        survivor_id, is_discovered = survivor
        if not is_discovered:
            # Mark as found and log the massive success
            cursor.execute("UPDATE survivors SET is_discovered=1 WHERE survivor_id=?", (survivor_id,))
            database.log_action(drone_id, f"URGENT: Discovered {survivor_id} at ({dx}, {dy})!")
            conn.commit()
            conn.close()
            return f"SUCCESS: Thermal signature detected! {survivor_id} found and logged."
        else:
            conn.close()
            return "Thermal signature detected, but survivor is already marked as discovered."
    
    conn.close()
    return "Scan complete. No thermal signatures detected at this location."

if __name__ == "__main__":
    # Runs the server using standard input/output, which is exactly how AI agents talk to MCP
    mcp.run_stdio()