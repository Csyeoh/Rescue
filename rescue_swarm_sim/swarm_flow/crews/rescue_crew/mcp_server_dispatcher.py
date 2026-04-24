import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from fastmcp import FastMCP
import json
import db

mcp = FastMCP("DispatcherSwarm")

@mcp.tool()
def get_quadrant_status() -> dict:
    """
    Returns buildings divided into 4 geographic quadrants (Q1: NE, Q2: NW, Q3: SW, Q4: SE).
    Each building shows whether its cluster is 'revealed' (fully searched) or not.
    """
    conn = db.get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, cx, cy, revealed, tile_count, assigned_to FROM building_clusters")
    
    quadrants = {"Q1_NE": [], "Q2_NW": [], "Q3_SW": [], "Q4_SE": []}
    
    for b_id, cx, cy, revealed, tile_count, assigned_to in cursor.fetchall():
        entry = {
            "id": b_id, "pos": [round(cx, 2), round(cy, 2)], 
            "fully_revealed": bool(revealed), "tile_count": tile_count,
            "assigned_to": assigned_to
        }
        if cx >= 10 and cy >= 10: quadrants["Q1_NE"].append(entry)
        elif cx < 10 and cy >= 10: quadrants["Q2_NW"].append(entry)
        elif cx < 10 and cy < 10: quadrants["Q3_SW"].append(entry)
        else: quadrants["Q4_SE"].append(entry)
        
    conn.close()
    return quadrants

@mcp.tool()
def get_fleet_status() -> dict:
    """
    Returns real-time data on the drone fleet including their task_queue,
    error counts, and any messages/reports they have sent to the Commander.
    """
    conn = db.get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, x, y, battery, status, task_queue, messages_for_commander FROM drones WHERE is_destroyed=0")
    
    drones = []
    for row in cursor.fetchall():
        d_id, x, y, batt, status, queue_raw, msgs_raw = row
        drones.append({
            "id": d_id,
            "pos": [round(x, 2), round(y, 2)],
            "battery": batt,
            "status": status,
            "task_queue": json.loads(queue_raw) if queue_raw else [],
            "reports_from_drone": json.loads(msgs_raw) if msgs_raw else []
        })
    conn.close()
    return {"drone_fleet": drones}

@mcp.tool()
def check_building_coverage(cluster_id: str) -> dict:
    """
    Checks exactly which 0.5x0.5 internal tiles of a building cluster have NOT been covered yet.
    Returns the missing coordinates.
    """
    conn = db.get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT cx, cy FROM building_clusters WHERE id=?", (cluster_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"error": "Cluster not found"}
        
    # We check the coverage table for any unrevealed cells near this cluster cx,cy
    cx, cy = row[0], row[1]
    
    # We define building cluster coverage simply as a 1.5 unit box around its center
    missing_tiles = []
    total_tiles = 0
    
    for ix in range(int((cx-1.5)*2), int((cx+1.5)*2)+1):
        for iy in range(int((cy-1.5)*2), int((cy+1.5)*2)+1):
            if 0 <= ix < 40 and 0 <= iy < 40:
                total_tiles += 1
                cursor.execute("SELECT revealed FROM coverage WHERE x_idx=? AND y_idx=?", (ix, iy))
                c_row = cursor.fetchone()
                if not c_row or c_row[0] == 0:
                    missing_tiles.append({"x": ix*0.5+0.25, "y": iy*0.5+0.25})
                    
    conn.close()
    coverage_pct = 100 * (1.0 - len(missing_tiles)/max(1, total_tiles))
    return {
        "cluster_id": cluster_id,
        "coverage_percentage": round(coverage_pct, 1),
        "missing_coverage_spots": missing_tiles,
        "summary": f"Coverage {round(coverage_pct,1)}%. {len(missing_tiles)} spots missed."
    }

@mcp.tool()
def assign_drone_task(drone_id: str, task: str, status: str) -> dict:
    """
    Assign a single narrative task to a drone and immediately set its status.
    Allowed status: 'SEARCHING' or 'RETURNING'.
    A drone can only have one uncompleted task at a time.
    """
    if status not in ['SEARCHING', 'RETURNING']:
        return {"error": "Invalid status. Must be SEARCHING or RETURNING."}

    conn = db.get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT task_queue FROM drones WHERE id=?", (drone_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"error": "Drone not found"}
        
    tasks = json.loads(row[0]) if row[0] else []
    
    if tasks and any(t.get("status") == "pending" for t in tasks):
        conn.close()
        return {"error": f"Drone {drone_id} already has a pending task. You must evaluate and call set_task_complete before assigning a new one."}
        
    # Overwrite task queue with this single new active task
    new_task = [{"task": task, "status": "pending", "feedback": []}]
    cursor.execute("UPDATE drones SET task_queue=?, status=? WHERE id=?", (json.dumps(new_task), status, drone_id))
    conn.commit()
    conn.close()
    return {"summary": f"Assigned new task to {drone_id} and set status to {status}."}

@mcp.tool()
def set_task_complete(drone_id: str) -> dict:
    """
    Marks the drone's current pending task as completed.
    This frees up the drone to receive a new task.
    """
    conn = db.get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT task_queue FROM drones WHERE id=?", (drone_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"error": "Drone not found"}
        
    tasks = json.loads(row[0]) if row[0] else []
    found = False
    for t in tasks:
        if t.get("status") == "pending":
            t["status"] = "completed"
            found = True
            break
            
    cursor.execute("UPDATE drones SET task_queue=?, messages_for_commander='[]', status='IDLE' WHERE id=?", (json.dumps(tasks), drone_id))
    conn.commit()
    conn.close()
    
    if found:
        return {"summary": f"Current task for {drone_id} marked complete. Drone is now IDLE."}
    return {"summary": f"Drone {drone_id} had no pending task, but status set to IDLE."}

@mcp.tool()
def give_feedback(drone_id: str, feedback: str) -> dict:
    """
    Appends a feedback message to the drone's current active task.
    The drone will read this to correct its actions.
    """
    conn = db.get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT task_queue FROM drones WHERE id=?", (drone_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"error": "Drone not found, you might give the wrong drone id, please check."}
        
    tasks = json.loads(row[0]) if row[0] else []
    found = False
    for t in tasks:
        if t.get("status") == "pending":
            t.setdefault("feedback", []).append(feedback)
            found = True
            break
            
    if not found:
        conn.close()
        return {"error": f"Drone {drone_id} has no pending task to give feedback on."}
        
    cursor.execute("UPDATE drones SET task_queue=? WHERE id=?", (json.dumps(tasks), drone_id))
    conn.commit()
    conn.close()
    return {"summary": f"Feedback sent to {drone_id}."}

@mcp.tool()
def set_cluster_assignment(cluster_id: str, drone_id: str) -> dict:
    """
    Updates the database to track which drone is assigned to a specific building cluster.
    Pass an empty string for drone_id to unassign a cluster.
    """
    did = None if not drone_id else drone_id
    conn = db.get_db_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE building_clusters SET assigned_to=? WHERE id=?", (did, cluster_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    if affected == 0: return {"error": "Cluster not found"}
    return {"summary": f"Cluster {cluster_id} assigned_to set to {did}."}


if __name__ == "__main__":
    mcp.run()
