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

    result = {
        "mission state": mission,
        "drones status": drones,
        "buildings": buildings,
        "unsearched buildings": unsearched,
        "summary": f"Mission: {found_survivors}/{total_survivors} survivors found, {len(drones)} drones active, {len(unsearched)} buildings unsearched."
    }
    return result


@mcp.tool()
def evaluate_sector_overlap(center_x: float, center_y: float, radius: float) -> dict:
    """
    Evaluates whether a candidate circular search sector overlaps significantly (>10%) 
    with any existing sectors assigned to actively searching drones.
    You MUST use this tool before blindly calling allocate_drone_sector.
    """
    if not (0 <= center_x <= 20 and 0 <= center_y <= 20):
        return {"summary": "Error: center coordinates must be within the 20×20 space.", "error": True}
    if radius <= 0 or radius > 15:
        return {"summary": "Error: radius must be between 0.1 and 15.0 units.", "error": True}

    import math
    conn = db.get_db_conn()
    cursor = conn.cursor()
    # Only check drones that are searching and have an assigned sector
    cursor.execute("SELECT id, assigned_sector FROM drones WHERE status='SEARCHING' AND assigned_sector IS NOT NULL")
    
    overlaps = []
    area_candidate = math.pi * radius**2

    for d_id, sector_raw in cursor.fetchall():
        try:
            sector = json.loads(sector_raw)
            cx2, cy2, r2 = float(sector['cx']), float(sector['cy']), float(sector['radius'])
        except Exception:
            continue
            
        d = math.hypot(cx2 - center_x, cy2 - center_y)
        overlap_pct = 0.0
        
        if d >= radius + r2:
            overlap_pct = 0.0
        elif d <= abs(radius - r2):
            area_smaller = math.pi * min(radius, r2)**2
            overlap_pct = (area_smaller / area_candidate) * 100.0
        else:
            # Trigonometric lens intersection area
            part1 = (radius**2) * math.acos((d**2 + radius**2 - r2**2) / (2 * d * radius))
            part2 = (r2**2) * math.acos((d**2 + r2**2 - radius**2) / (2 * d * r2))
            # Protect against floating point precision issues inside sqrt
            val = (-d + radius + r2) * (d + radius - r2) * (d - radius + r2) * (d + radius + r2)
            part3 = 0.5 * math.sqrt(max(0, val))
            
            intersection_area = part1 + part2 - part3
            overlap_pct = (intersection_area / area_candidate) * 100.0
            
        if overlap_pct > 10.0:
            overlaps.append(f"{d_id} ({overlap_pct:.1f}%)")
            
    conn.close()

    if overlaps:
        return {
            "summary": f"Warning: Major overlap detected with {', '.join(overlaps)}. Please adjust coordinates.",
            "overlapping_drones": overlaps,
            "is_clear": False
        }
        
    return {
        "summary": f"No major overlap detected for ({center_x}, {center_y}) r={radius}. Sector is clear to assign.",
        "is_clear": True
    }



@mcp.tool()
def allocate_drone_sector(drone_id: str, center_x: float, center_y: float, radius: float) -> dict:
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
        return {"summary": f"Error: drone '{drone_id}' not found.", "error": True}
    return {
        "summary": f"Sector assigned to {drone_id} at ({center_x}, {center_y}) radius of {radius}. Status set to SEARCHING.",
    }

if __name__ == "__main__":
    mcp.run()
