import json
import sqlite3
from typing import Any, Dict

import database
import mcp_server

try:
    from crewai.tools import tool as crewai_tool
except Exception:  # pragma: no cover
    crewai_tool = None

# We no longer need A* or full grids. The AI purely works on high-level zones.

def get_terrain_map() -> str:
    """Returns the known map (altitude, terrain type) and water level without obstacles."""
    return mcp_server.get_known_map()

def get_drone_status() -> Dict[str, Any]:
    """Returns the active drones, their batteries, and their CURRENT zone assignments."""
    conn = database._connect()
    cursor = conn.cursor()

    cursor.execute("SELECT drone_id, x, y, battery FROM drones WHERE is_active=1")
    drones_rows = cursor.fetchall()

    cursor.execute("SELECT drone_id, x_min, x_max, y_min, y_max, is_complete FROM drone_zones")
    zones = {row[0]: {"x_min": row[1], "x_max": row[2], "y_min": row[3], "y_max": row[4], "is_complete": bool(row[5])} for row in cursor.fetchall()}

    drones = []
    for (d_id, x, y, bat) in drones_rows:
        drone_data = {
            "id": d_id,
            "x": x,
            "y": y,
            "battery": bat,
            "zone_assignment": zones.get(d_id, "UNASSIGNED")
        }
        drones.append(drone_data)

    conn.close()
    return {"drones": drones}

def get_idle_drones() -> list[str]:
    """Returns a list of drone IDs that have no remaining unvisited waypoints."""
    conn = database._connect()
    cursor = conn.cursor()
    cursor.execute("SELECT drone_id FROM drones WHERE is_active=1")
    all_drones = [r[0] for r in cursor.fetchall()]
    
    idle = []
    for d in all_drones:
        cursor.execute("SELECT COUNT(*) FROM drone_waypoints WHERE drone_id=? AND is_done=0", (d,))
        count = cursor.fetchone()[0]
        if count == 0:
            idle.append(d)
    conn.close()
    return idle

def assign_waypoints(drone_id: str, waypoints: list[tuple[int, int]]) -> str:
    """Assigns an ordered list of (x,y) waypoints to a drone."""

    def _do_write():
        with database.DB_WRITE_LOCK:
            conn = database._connect()
            cursor = conn.cursor()

            cursor.execute("SELECT drone_id FROM drones WHERE drone_id=?", (drone_id,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return f"Error: Drone {drone_id} does not exist."

            # Erase old uncompleted waypoints for this drone
            cursor.execute("DELETE FROM drone_waypoints WHERE drone_id=?", (drone_id,))

            # Insert new sequential list
            records = [(drone_id, seq, x, y, 0) for seq, (x, y) in enumerate(waypoints)]
            cursor.executemany('''
                INSERT INTO drone_waypoints (drone_id, seq, x, y, is_done)
                VALUES (?, ?, ?, ?, ?)
            ''', records)

            # Update UI bounding box for the new territory
            if waypoints:
                x_min = min(x for x, y in waypoints)
                x_max = max(x for x, y in waypoints)
                y_min = min(y for x, y in waypoints)
                y_max = max(y for x, y in waypoints)
                
                cursor.execute('''
                    INSERT OR REPLACE INTO drone_zones (drone_id, x_min, x_max, y_min, y_max, is_complete)
                    VALUES (?, ?, ?, ?, ?, 0)
                ''', (drone_id, x_min, x_max, y_min, y_max))

            # Log inline
            cursor.execute("INSERT INTO logs (drone_id, message) VALUES (?, ?)",
                           (drone_id, f"COMMAND: Received {len(waypoints)} new waypoints."))

            conn.commit()
            conn.close()
            return f"Success: {drone_id} assigned {len(waypoints)} waypoints."

    try:
        return database._with_retry(_do_write)
    except Exception as e:
        return f"Error writing waypoints for {drone_id}: {e}"

get_terrain_map_tool = None
get_drone_status_tool = None
assign_waypoints_tool = None

if crewai_tool:
    @crewai_tool("get_terrain_map")
    def get_terrain_map_tool() -> str:
        """Read the global water level and known map altitudes (excluding hidden obstacles and survivors)."""
        return get_terrain_map()

    @crewai_tool("get_drone_status")
    def get_drone_status_tool() -> str:
        """Get live coordinates, batteries, and current zone assignments of all active drones."""
        return json.dumps(get_drone_status())

    @crewai_tool("log_mission_reasoning")
    def log_mission_reasoning_tool(logic: str) -> str:
        """Use this to write your Chain-of-Thought reasoning to the official mission logs database."""
        # Simple inline log writer for the Strategy Agent
        def _do_write():
            with database.DB_WRITE_LOCK:
                conn = database._connect()
                cursor = conn.cursor()
                cursor.execute("INSERT INTO logs (drone_id, message) VALUES (?, ?)", ("SYSTEM", f"STRATEGY: {logic}"))
                conn.commit()
                conn.close()
            return "SUCCESS"
        database._with_retry(_do_write)
        return "Reasoning Logged."
