import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from fastmcp import FastMCP
import json
import time
import io
from swarm_flow.tools.ascii_map import generate_global_map
import db

mcp = FastMCP("DispatcherSwarm")

@mcp.tool()
def get_current_mission_status() -> str:
    """Returns a narrative report of the mission, including a legend, drone summary, and the 20x20 ASCII map."""
    t0 = time.time()
    conn = db.get_db_conn()
    cursor = conn.cursor()
    
    # Generate ASCII Map
    ascii_map = generate_global_map(cursor)
        
    # Get all drones status
    cursor.execute("SELECT id, x, y, battery, status, assigned_cells FROM drones")
    drones = cursor.fetchall()
    conn.close()

    # Build Narrative Report
    report = []
    report.append("### MISSION STATUS REPORT ###")
    report.append("\n**LEGEND:**")
    report.append("- `B`: Unrevealed Building")
    report.append("- `U`: Unrevealed Terrain")
    report.append("- `A`: Assigned cell)")
    report.append("- `.` : Searched/Revealed cell")
    report.append("- `(x,y)`: Drone positions are marked by their IDs in the drone summary below.")

    report.append("\n**DRONE FLEET SUMMARY:**")
    if not drones:
        report.append("No drones currently active in the field.")
    for r in drones:
        d_id, x, y, batt, status, pts_raw = r
        pts = json.loads(pts_raw) if pts_raw else []
        report.append(f"- **{d_id}**: At ({x}, {y}) | Battery: {batt}% | Status: {status}")
        if pts:
            report.append(f"  * Current Assignment: {len(pts)} cells remaining in sector.")
        else:
            report.append("  * Current Assignment: IDLE (Awaiting sector allocation)")

    report.append("\n**GLOBAL DISASTER ZONE MAP (20x20):**")
    report.append("```")
    report.append(ascii_map)
    report.append("```")
    
    print(f"⏱️ [Timing] MCP get_current_mission_status took {time.time()-t0:.4f}s", file=sys.stderr)
    return "\n".join(report)

@mcp.tool()
def allocate_drone_sector(drone_id: str, assigned_cells: list) -> str:
    """Allocates a specific list of cells [[x,y], ...] to a drone."""
    t0 = time.time()
    
    # 1. Parse cells
    pts = []
    for v in assigned_cells:
        if isinstance(v, (list, tuple)) and len(v) >= 2:
            pts.append([int(v[0]), int(v[1])])
        elif isinstance(v, dict):
            pts.append([int(v.get("x", 0)), int(v.get("y", 0))])
            
    if not pts:
        return "Error: Invalid cell list."

    conn = db.get_db_conn()
    cursor = conn.cursor()
    
    # 2. Assign specifically requested cells
    # Only assign if not already assigned or revealed
    assigned_count = 0
    for px, py in pts:
        cursor.execute("""
            UPDATE cells SET assigned_to = ? 
            WHERE x = ? AND y = ? AND assigned_to IS NULL AND revealed = 0
        """, (drone_id, px, py))
        if cursor.rowcount > 0:
            assigned_count += 1
        
    # 3. Update drone's assigned cells and status
    cursor.execute("UPDATE drones SET assigned_cells = ?, status = 'SEARCHING' WHERE id = ?", 
                   (json.dumps(pts), drone_id))
    
    conn.commit()
    conn.close()
    print(f"⏱️ [Timing] MCP allocate_drone_sector took {time.time()-t0:.4f}s", file=sys.stderr)
    return f"Successfully allocated {assigned_count} cells to {drone_id}."


if __name__ == "__main__":
    mcp.run()
