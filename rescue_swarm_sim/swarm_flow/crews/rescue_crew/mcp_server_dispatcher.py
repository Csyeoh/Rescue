from fastmcp import FastMCP
import sys
import os
import json
import time
import io

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
import db

mcp = FastMCP("DispatcherSwarm")

@mcp.tool()
def get_global_mission_state() -> dict:
    """Returns a compact summary of unrevealed cells and all drone statuses."""
    t0 = time.time()
    conn = db.get_db_conn()
    cursor = conn.cursor()
    
    # Get all unrevealed cells
    cursor.execute("SELECT x, y, terrain_type, assigned_to FROM cells WHERE revealed = 0")
    unrevealed = []
    for r in cursor.fetchall():
        unrevealed.append({"pos": [r[0], r[1]], "type": r[2], "assigned_to": r[3]})
        
    # Get all drones
    cursor.execute("SELECT id, x, y, battery, status, assigned_sector FROM drones")
    drones = []
    for r in cursor.fetchall():
        sector_raw = json.loads(r[5]) if r[5] else []
        sector = sector_raw if sector_raw is not None else []
        drones.append({
            "id": r[0], "pos": {"x": r[1], "y": r[2]}, "battery": r[3], 
            "status": r[4], "assigned_cells_count": len(sector)
        })
        
    conn.close()
    print(f"⏱️ [Timing] MCP get_global_mission_state took {time.time()-t0:.4f}s", file=sys.stderr)
    return {"unrevealed_cells": unrevealed, "drones": drones}

@mcp.tool()
def allocate_drone_sector(drone_id: str, coordinates: list) -> str:
    """Allocates a specific list of [x,y] coordinates to a drone and marks them as assigned."""
    t0 = time.time()
    
    clean_coords = []
    for c in coordinates:
        try:
            if isinstance(c, dict):
                clean_coords.append([int(c["x"]), int(c["y"])])
            elif isinstance(c, (list, tuple)) and len(c) >= 2:
                clean_coords.append([int(c[0]), int(c[1])])
        except (ValueError, TypeError):
            pass

    conn = db.get_db_conn()
    cursor = conn.cursor()
    
    # 1. Update the cells table
    for x, y in clean_coords:
        cursor.execute("UPDATE cells SET assigned_to = ? WHERE x = ? AND y = ?", (drone_id, x, y))
        
    # 2. Update the drones table
    cursor.execute("UPDATE drones SET assigned_sector = ?, status = 'SEARCHING' WHERE id = ?", (json.dumps(clean_coords), drone_id))
    
    conn.commit()
    conn.close()
    print(f"⏱️ [Timing] MCP allocate_drone_sector took {time.time()-t0:.4f}s", file=sys.stderr)
    return f"Successfully allocated {len(clean_coords)} cells to {drone_id}."

if __name__ == "__main__":
    mcp.run()
