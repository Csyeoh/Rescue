import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from fastmcp import FastMCP
import heapq
import json
import time
import db

mcp = FastMCP("DroneSwarm")

@mcp.tool()
def get_drone_context(drone_id: str) -> dict:
    """Returns local position, battery, thermal memory, and sector status."""
    t0 = time.time()
    conn = db.get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT x, y, battery, status, thermal_memory, assigned_cells FROM drones WHERE id=?", (drone_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"error": "not found"}
    
    x, y, batt, status, t_mem_raw, pts_raw = row
    pts = json.loads(pts_raw) if pts_raw else []
    t_mem = json.loads(t_mem_raw) if t_mem_raw else []
    
    
    conn.close()
    return {
        "id": drone_id, 
        "pos": {"x": x, "y": y}, 
        "battery": batt, 
        "status": status, 
        "thermal_memory": t_mem,
        "assigned_cells": pts
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
    
    msg = f"Revealed {revealed} cells."
    if new_auras: msg += f" Thermal auras detected nearby! Survivors are in adjacent cells."
    return msg

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
            return {"x": start[0], "y": start[1]}
    path = []
    curr = goal
    while curr != start:
        path.append(curr)
        curr = came_from[curr]
    return {"x": path[-1][0], "y": path[-1][1]}

if __name__ == "__main__":
    mcp.run()
