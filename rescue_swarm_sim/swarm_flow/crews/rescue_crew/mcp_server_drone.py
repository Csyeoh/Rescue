from fastmcp import FastMCP
import sys
import os
import heapq
import json
import time
import io


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
import db

mcp = FastMCP("DroneSwarm")

@mcp.tool()
def get_drone_context(drone_id: str) -> dict:
    """Returns battery, position, status, assigned sector, and thermal memory for a drone."""
    t0 = time.time()
    conn = db.get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT x, y, battery, status, is_destroyed, thermal_memory, assigned_sector FROM drones WHERE id=?", (drone_id,))
    row = cursor.fetchone()
    conn.close()
    print(f"⏱️ [Timing] MCP get_drone_context took {time.time()-t0:.4f}s", file=sys.stderr)
    if not row: return {"error": "not found"}
    t_mem = json.loads(row[5]) if row[5] else []
    a_sec = json.loads(row[6]) if row[6] else None
    return {
        "id": drone_id, "pos": {"x": row[0], "y": row[1]}, "battery": row[2], 
        "status": row[3], "is_destroyed": bool(row[4]),
        "thermal_memory": t_mem if t_mem is not None else [], 
        "assigned_sector": a_sec
    }

@mcp.tool()
def thermal_scan(drone_id: str) -> str:
    """Reveals adjacent cells, detects auras, and updates lists in DB."""
    t0 = time.time()
    conn = db.get_db_conn()
    cursor = conn.cursor()
    # Get current pos
    cursor.execute("SELECT x, y, thermal_memory FROM drones WHERE id=?", (drone_id,))
    d_row = cursor.fetchone()
    if not d_row: return "Error: drone not found"
    cx, cy, t_mem_raw = d_row
    t_mem_data = json.loads(t_mem_raw) if t_mem_raw else []
    t_mem = t_mem_data if t_mem_data is not None else []
    
    # Reveal and Check Auras
    adj = [(cx, cy), (cx, cy-1), (cx, cy+1), (cx-1, cy), (cx+1, cy)]
    revealed = 0
    new_auras = []
    for ax, ay in adj:
        if 0 <= ax < 20 and 0 <= ay < 20:
            # Mark as revealed and discovered (if obstacle)
            cursor.execute("UPDATE cells SET revealed = 1, obstacle_discovered = CASE WHEN is_obstacle = 1 THEN 1 ELSE obstacle_discovered END WHERE x=? AND y=?", (ax, ay))
            
            cursor.execute("SELECT thermal_aura FROM cells WHERE x=? AND y=?", (ax, ay))
            c_row = cursor.fetchone()
            if c_row and c_row[0] == 1:
                pos = [ax, ay]
                if pos not in t_mem:
                    t_mem.append(pos)
                    new_auras.append(f"({ax},{ay})")
            revealed += 1

    # WIPE OUT THERMAL MEMORY if aura is gone (meaning survivor was found)
    updated_t_mem = []
    for tx, ty in t_mem:
        cursor.execute("SELECT thermal_aura FROM cells WHERE x=? AND y=?", (tx, ty))
        aura_row = cursor.fetchone()
        if aura_row and aura_row[0] == 1:
            updated_t_mem.append([tx, ty])
    
    cursor.execute("UPDATE drones SET thermal_memory=? WHERE id=?", (json.dumps(updated_t_mem), drone_id))
    conn.commit()
    conn.close()
    
    print(f"⏱️ [Timing] MCP thermal_scan took {time.time()-t0:.4f}s", file=sys.stderr)
    msg = f"Revealed {revealed} cells."
    if new_auras: msg += f" Thermal auras detected nearby! Survivors are in adjacent cells."
    return msg

@mcp.tool()
def get_next_sector_step(drone_id: str) -> dict:
    """Returns the closest unrevealed coordinate from the drone's assigned cell list."""
    t0 = time.time()
    
    # Initialize basic log state
    log_state = {
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "drone_id": drone_id,
        "action": "evaluating",
        "position": None,
        "assigned_cells_count": 0,
        "unrevealed_in_sector_count": 0
    }
    
    def write_log(result_obj):
        log_state["result"] = result_obj
        try:
            with open("get_next_sector_step.txt", "a") as f:
                f.write(json.dumps(log_state) + "\n")
        except Exception as e:
            print(f"Error writing to log: {e}", file=sys.stderr)
        return result_obj

    conn = db.get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT x, y, assigned_sector FROM drones WHERE id=?", (drone_id,))
    row = cursor.fetchone()
    if not row or not row[2]:
        conn.close()
        return write_log({"error": "no sector assigned"})
    
    cx, cy = row[0], row[1]
    sector_raw = json.loads(row[2]) if row[2] else []
    assigned_cells = sector_raw if sector_raw is not None else []
    
    log_state["position"] = [cx, cy]
    log_state["assigned_cells_count"] = len(assigned_cells)
    
    # Filter for cells that are still unrevealed
    unrevealed_in_sector = []
    for cell in assigned_cells:
        try:
            if isinstance(cell, dict):
                tx, ty = int(cell["x"]), int(cell["y"])
            else:
                tx, ty = int(cell[0]), int(cell[1])
        except (ValueError, IndexError, TypeError):
            continue
            
        cursor.execute("SELECT revealed FROM cells WHERE x=? AND y=?", (tx, ty))
        c_row = cursor.fetchone()
        if c_row and c_row[0] == 0:
            unrevealed_in_sector.append((tx, ty))
            
    conn.close()
    
    log_state["unrevealed_in_sector_count"] = len(unrevealed_in_sector)
    
    if not unrevealed_in_sector:
        # No more work in this assignment.
        conn = db.get_db_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE drones SET assigned_sector=NULL WHERE id=?", (drone_id,))
        conn.commit()
        conn.close()
        print(f"⏱️ [Timing] MCP get_next_sector_step took {time.time()-t0:.4f}s", file=sys.stderr)
        return write_log({"status": "sector_complete"})
        
    # Find the closest unrevealed cell in the set
    closest = min(unrevealed_in_sector, key=lambda c: abs(c[0] - cx) + abs(c[1] - cy))
    print(f"⏱️ [Timing] MCP get_next_sector_step took {time.time()-t0:.4f}s", file=sys.stderr)
    return write_log({"x": closest[0], "y": closest[1]})

@mcp.tool()
def check_task_viability(drone_id: str, target_x: int, target_y: int) -> dict:
    """Calculates A* distance to target and back to base."""
    t0 = time.time()
    conn = db.get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT x, y, battery FROM drones WHERE id=?", (drone_id,))
    d_row = cursor.fetchone()
    if not d_row: return {"error": "not found"}
    start = (d_row[0], d_row[1])
    battery = d_row[2]
    
    cursor.execute("SELECT x, y FROM cells WHERE is_obstacle=1 AND obstacle_discovered=1")
    obs = set(cursor.fetchall())
    conn.close()

    def get_dist(a, b):
        frontier = [(0, a)]
        came_from = {a: None}; cost = {a: 0}
        while frontier:
            current = heapq.heappop(frontier)[1]
            if current == b: break
            for dx, dy in [(0,1),(0,-1),(1,0),(-1,0)]:
                nxt = (current[0]+dx, current[1]+dy)
                if 0<=nxt[0]<20 and 0<=nxt[1]<20 and nxt not in obs:
                    new_c = cost[current] + 1
                    if nxt not in cost or new_c < cost[nxt]:
                        cost[nxt] = new_c
                        priority = new_c + abs(b[0]-nxt[0]) + abs(b[1]-nxt[1])
                        heapq.heappush(frontier, (priority, nxt))
                        came_from[nxt] = current
        return cost.get(b, abs(a[0]-b[0]) + abs(a[1]-b[1])) # Fallback to Manhattan if blocked/unknown

    d1 = get_dist(start, (target_x, target_y))
    d2 = get_dist((target_x, target_y), (9, 9))
    required = (d1 + d2) * 2 + 10
    print(f"⏱️ [Timing] MCP check_task_viability took {time.time()-t0:.4f}s", file=sys.stderr)
    return {"viable": battery >= required, "required": required, "current": battery}

@mcp.tool()
def get_navigation_step(drone_id: str, target_x: int, target_y: int) -> dict:
    """Calculates one A* step towards target avoiding known obstacles."""
    t0 = time.time()
    conn = db.get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT x, y FROM drones WHERE id=?", (drone_id,))
    start = cursor.fetchone()
    cursor.execute("SELECT x, y FROM cells WHERE is_obstacle=1 AND obstacle_discovered=1")
    obs = set(cursor.fetchall())
    conn.close()
    
    goal = (target_x, target_y)
    if start == goal: 
        print(f"⏱️ [Timing] MCP get_navigation_step took {time.time()-t0:.4f}s", file=sys.stderr)
        return {"x": start[0], "y": start[1]}
    
    frontier = [(0, start)]
    came_from = {start: None}; cost = {start: 0}
    while frontier:
        current = heapq.heappop(frontier)[1]
        if current == goal: break
        for dx, dy in [(0,1),(0,-1),(1,0),(-1,0)]:
            nxt = (current[0]+dx, current[1]+dy)
            if 0<=nxt[0]<20 and 0<=nxt[1]<20 and nxt not in obs:
                new_c = cost[current] + 1
                if nxt not in cost or new_c < cost[nxt]:
                    cost[nxt] = new_c
                    heapq.heappush(frontier, (new_c + abs(goal[0]-nxt[0]) + abs(goal[1]-nxt[1]), nxt))
                    came_from[nxt] = current
    
    if goal not in came_from: 
        print(f"⏱️ [Timing] MCP get_navigation_step took {time.time()-t0:.4f}s", file=sys.stderr)
        return {"x": start[0], "y": start[1]}
    path = []
    curr = goal
    while curr != start:
        path.append(curr)
        curr = came_from[curr]
    print(f"⏱️ [Timing] MCP get_navigation_step took {time.time()-t0:.4f}s", file=sys.stderr)
    return {"x": path[-1][0], "y": path[-1][1]}

if __name__ == "__main__":
    mcp.run()
