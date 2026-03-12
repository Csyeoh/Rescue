from fastmcp import FastMCP
import sqlite3
import time
import database

# Initialize the MCP Server
mcp = FastMCP("RescueSwarm")

@mcp.tool()
def discover_drones() -> list[str]:
    """Returns a list of all active drone IDs available for command in the simulation."""
    conn = sqlite3.connect(database.DB_NAME, timeout=10.0)
    cursor = conn.cursor()
    cursor.execute("SELECT drone_id FROM drones")
    drones = [row[0] for row in cursor.fetchall()]
    conn.close()
    return drones

@mcp.tool()
def get_battery_status(drone_id: str) -> str:
    """Returns the current battery level (0-100) of a specific drone."""
    conn = sqlite3.connect(database.DB_NAME, timeout=10.0)
    cursor = conn.cursor()
    cursor.execute("SELECT battery FROM drones WHERE drone_id=?", (drone_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return f"{drone_id} battery is at {result[0]}%"
    return f"Error: {drone_id} not found."

@mcp.tool()
def get_hardware_status(drone_id: str) -> str:
    """Returns the full diagnostic hardware status of a drone including location, battery, flight state, and system health."""
    conn = sqlite3.connect(database.DB_NAME, timeout=10.0)
    cursor = conn.cursor()
    cursor.execute("SELECT x, y, battery, is_active, health_status FROM drones WHERE drone_id=?", (drone_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        x, y, bat, is_active, health = result
        state = "CHARGING AT BASE" if (x == 9 and y == 9) else "IN FLIGHT"
        activity = "ACTIVE (SEARCHING)" if is_active == 1 else "IDLE"
        
        return f"""[{drone_id} HARDWARE DIAGNOSTIC]
- Location: ({x}, {y})
- Flight State: {state}
- Mission Status: {activity}
- Battery: {bat}%
- Core Health: {health}"""
    
    return f"Error: {drone_id} not found."

@mcp.tool()
def move_drone(drone_id: str, x: int, y: int) -> str:
    """
    Moves a rescue drone to specific (x, y) coordinates on the grid.
    Automatically drains battery by 2% per move, or recharges to 100% if moved to Base Camp (9,9).
    If a survivor is in an adjacent grid (Up, Down, Left, Right), it will trigger a Thermal Aura sensor alert.
    """
    if not (0 <= x < 20 and 0 <= y < 20):
        return "Failure: Coordinates out of bounds. Grid is strictly 0 to 19."

    conn = sqlite3.connect(database.DB_NAME, timeout=10.0)
    cursor = conn.cursor()

    # 1. Check current battery
    cursor.execute("SELECT battery FROM drones WHERE drone_id=?", (drone_id,))
    drone_data = cursor.fetchone()
    
    if not drone_data:
        conn.close()
        return f"Error: {drone_id} not found."

    battery = drone_data[0]
    if battery < 2:
        conn.close()
        return f"Failure: {drone_id} battery exhausted. Drone is grounded."

    # 2. Check for physical obstacles
    try:
        cursor.execute("SELECT is_obstacle FROM grid WHERE x=? AND y=?", (x, y))
        grid_data = cursor.fetchone()
        
        if grid_data and grid_data[0] == 1:
            cursor.execute("UPDATE grid SET obstacle_discovered=1 WHERE x=? AND y=?", (x, y))
            database.log_action(drone_id, f"CRITICAL: Flight path to ({x}, {y}) blocked by physical obstacle!")
            conn.commit()
            conn.close()
            return f"Failure: Movement to ({x}, {y}) blocked by an obstacle. Route around it."
    except sqlite3.OperationalError:
        pass 

    # 3. Process the successful move
    new_battery = 100 if (x == 9 and y == 9) else battery - 2
    cursor.execute("UPDATE drones SET x=?, y=?, battery=? WHERE drone_id=?", (x, y, new_battery, drone_id))

    # 4. SENSOR CHECK: Is there a Thermal Aura nearby?
    # We check all undiscovered survivors to see if they are exactly 1 tile away (Manhattan distance of 1)
    cursor.execute("SELECT x, y FROM survivors WHERE is_discovered=0")
    undiscovered = cursor.fetchall()
    
    aura_detected = False
    for sx, sy in undiscovered:
        if abs(sx - x) + abs(sy - y) == 1:
            aura_detected = True
            break

    # 5. Log the action to the UI console
    log_msg = "Returned to Base Camp. Recharging to 100%." if (x == 9 and y == 9) else f"Moved to sector ({x}, {y})."
    
    # We don't log the aura to the UI (to preserve the fog of war for the humans),
    # but the AI will see it in the return message below!
    database.log_action(drone_id, log_msg)

    conn.commit()
    conn.close()
    
    # 6. Simulate the physical flight time! 
    # The AI is forced to wait 1.5 seconds before it receives the sensor feedback.
    time.sleep(1.5)
    
    # 7. Return the sensor data to the AI Brain
    response_msg = f"Success: {drone_id} moved to ({x}, {y}). Battery now at {new_battery}%."
    if aura_detected:
        response_msg += " [SENSOR ALERT: Faint thermal aura detected in an adjacent sector (Up, Down, Left, or Right)! Perform thermal scans immediately.]"
        
    return response_msg

@mcp.tool()
def thermal_scan(drone_id: str) -> str:
    """
    Performs a high-powered thermal scan at the drone's EXACT current (x, y) location.
    Returns a message indicating if a hidden survivor was found on this specific grid square.
    """
    conn = sqlite3.connect(database.DB_NAME, timeout=10.0)
    cursor = conn.cursor()
    
    cursor.execute("SELECT x, y FROM drones WHERE drone_id=?", (drone_id,))
    drone_loc = cursor.fetchone()
    
    if not drone_loc:
        conn.close()
        return f"Error: {drone_id} not found."
    
    dx, dy = drone_loc
    
    cursor.execute("SELECT survivor_id, is_discovered FROM survivors WHERE x=? AND y=?", (dx, dy))
    survivor = cursor.fetchone()
    
    if survivor:
        survivor_id, is_discovered = survivor
        if not is_discovered:
            cursor.execute("UPDATE survivors SET is_discovered=1 WHERE survivor_id=?", (survivor_id,))
            database.log_action(drone_id, f"URGENT: Thermal match! Discovered {survivor_id} at ({dx}, {dy})!")
            conn.commit()
            conn.close()
            return f"SUCCESS: Thermal signature detected! {survivor_id} found and logged."
        else:
            conn.close()
            return "Thermal signature detected, but survivor is already marked as rescued."
    
    conn.close()
    return "Scan complete. No thermal signatures detected at this exact location."

@mcp.tool()
def get_known_map() -> str:
    """
    Returns the known layout of the 20x20 grid, including altitudes and terrain types.
    Use this to analyze the landscape, calculate flood risks, and run clustering algorithms.
    NOTE: This does NOT reveal hidden obstacles or survivors.
    """
    conn = sqlite3.connect(database.DB_NAME, timeout=10.0)
    cursor = conn.cursor()
    
    # We only pull x, y, altitude, and terrain_type. We hide the obstacle data!
    cursor.execute("SELECT x, y, altitude, terrain_type FROM grid")
    grid_data = cursor.fetchall()
    
    # Also fetch the current global water level so the AI knows what is currently flooded
    cursor.execute("SELECT global_water_level FROM environment WHERE id=1")
    env_data = cursor.fetchone()
    water_level = env_data[0] if env_data else 0.0
    
    conn.close()
    
    if not grid_data:
        return "Error: Map data not initialized yet."

    # Format the data cleanly for the AI to read
    map_details = f"CURRENT GLOBAL WATER LEVEL: {water_level:.2f}m\n"
    map_details += "GRID DATA (x, y, altitude, type):\n"
    
    # To save AI token context limits, we can just pass the raw list
    map_list = [{"x": row[0], "y": row[1], "alt": round(row[2], 1), "type": row[3]} for row in grid_data]
    
    import json
    map_details += json.dumps(map_list)
    
    return map_details

if __name__ == "__main__":
    mcp.run_stdio()