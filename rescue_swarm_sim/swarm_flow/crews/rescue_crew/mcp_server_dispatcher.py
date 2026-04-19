import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from fastmcp import FastMCP
import json
import db

mcp = FastMCP("DispatcherSwarm")

@mcp.tool()
def get_current_mission_status() -> dict:
    """
    Returns a structured JSON report of the mission.
    Includes drone fleet, building registry, obstacle registry, and survivor status.
    The dispatcher should use this to reason about uncleared zones and assign sectors.
    Each position is in continuous-space units (1 unit = 50 m). The space is 20×20 units.
    """
    conn = db.get_db_conn()
    cursor = conn.cursor()

    # Survivors - for both list and aggregated mission stats
    cursor.execute("SELECT id, x, y, found FROM survivors")
    survivors_rows = cursor.fetchall()
    
    total_survivors = len(survivors_rows)
    found_survivors = sum(1 for r in survivors_rows if r[3])

    # Mission state (dynamically aggregated)
    mission = {
        "complete": total_survivors > 0 and found_survivors >= total_survivors,
        "total_survivors": total_survivors,
        "found_survivors": found_survivors
    }

    # Drones
    cursor.execute("SELECT id, x, y, battery, status FROM drones WHERE is_destroyed=0")
    drones = []
    for row in cursor.fetchall():
        d_id, x, y, batt, status = row
        drones.append({
            "id": d_id,
            "pos": [round(x, 2), round(y, 2)],
            "battery": batt,
            "status": status,
        })

    # Buildings — directly read from precomputed clusters
    cursor.execute("SELECT id, cx, cy, revealed, tile_count FROM building_clusters")
    buildings = []
    unsearched = []
    
    for row in cursor.fetchall():
        b_id, cx, cy, revealed, tile_count = row
        entry = {
            "id": b_id, 
            "pos": [round(cx, 2), round(cy, 2)], 
            "revealed": bool(revealed), 
            "tile_count": tile_count
        }
        buildings.append(entry)
        
        if not revealed:
            unsearched.append([round(cx, 2), round(cy, 2)])

    conn.close()

    return {
        "mission state": mission,
        "drones status": drones,
        "buildings": buildings,
        "unsearched buildings": unsearched
    }


@mcp.tool()
def allocate_drone_sector(drone_id: str, center_x: float, center_y: float, radius: float) -> str:
    """
    Assigns a circular search sector to a drone for scanning open terrain.
    The sector is defined by a centre point (center_x, center_y) and a radius in continuous-space units.
    """
    if not (0 <= center_x <= 20 and 0 <= center_y <= 20):
        return "Error: center coordinates must be within the 20×20 space."
    if radius <= 0 or radius > 15:
        return "Error: radius must be between 0.1 and 15.0 units."

    sector = {"cx": round(center_x, 2), "cy": round(center_y, 2), "radius": round(radius, 2)}

    conn = db.get_db_conn()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE drones SET assigned_sector=?, status='SEARCHING' WHERE id=?",
        (json.dumps(sector), drone_id)
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()

    if affected == 0:
        return f"Error: drone '{drone_id}' not found."
    return (
        f"Sector allocated to {drone_id}: centre ({center_x}, {center_y}), "
        f"radius {radius} units. Status set to SEARCHING."
    )

if __name__ == "__main__":
    mcp.run()
