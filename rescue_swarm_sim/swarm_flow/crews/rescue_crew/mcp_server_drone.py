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
def view_surrounding(drone_id: str) -> dict:
    """Reveals adjacent 1-cell radius and identifies exact components (N, S, E, W, CURRENT)."""
    conn = db.get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT x, y FROM drones WHERE id=?", (drone_id,))
    d_row = cursor.fetchone()
    if not d_row: return {"error": "drone not found"}
    cx, cy = d_row
    
    surrounding = {}
    offsets = {"CURRENT": (0,0), "N": (0,-1), "S": (0,1), "W": (-1,0), "E": (1,0)}
    
    cursor.execute("SELECT x, y FROM survivors WHERE found=0")
    survivors_locs = {(row[0], row[1]) for row in cursor.fetchall()}
    
    for direction, (dx, dy) in offsets.items():
        ax, ay = cx + dx, cy + dy
        if 0 <= ax < 20 and 0 <= ay < 20:
            cursor.execute("UPDATE cells SET revealed = 1, obstacle_discovered = CASE WHEN is_obstacle = 1 THEN 1 ELSE obstacle_discovered END WHERE x=? AND y=?", (ax, ay))
            
            cursor.execute("SELECT is_obstacle, terrain_type FROM cells WHERE x=? AND y=?", (ax, ay))
            c_row = cursor.fetchone()
            if c_row:
                is_ob, t_type = c_row
                if (ax, ay) in survivors_locs:
                    surrounding[direction] = "SURVIVOR"
                elif is_ob:
                    surrounding[direction] = "OBSTACLE"
                elif t_type == "building":
                    surrounding[direction] = "BUILDING"
                else:
                    surrounding[direction] = "EMPTY"
        else:
            surrounding[direction] = "OUT_OF_BOUNDS"
            
    conn.commit()
    conn.close()
    return surrounding

def bresenham_line(x0, y0, x1, y1):
    points = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    x, y = x0, y0
    sx = -1 if x0 > x1 else 1
    sy = -1 if y0 > y1 else 1
    if dx > dy:
        err = dx / 2.0
        while x != x1:
            points.append((x, y))
            err -= dy
            if err < 0:
                y += sy
                err += dx
            x += sx
    else:
        err = dy / 2.0
        while y != y1:
            points.append((x, y))
            err -= dx
            if err < 0:
                x += sx
                err += dy
            y += sy
    points.append((x, y))
    return points

import random

@mcp.tool()
def thermal_scan(drone_id: str, direction: str) -> dict:
    """Senses heat traces in a specific direction ('N', 'S', 'E', 'W') using a fan sensor. Obstacles block heat. Returns noisy signal %."""
    conn = db.get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT x, y FROM drones WHERE id=?", (drone_id,))
    d_row = cursor.fetchone()
    if not d_row: return {"error": "drone not found"}
    cx, cy = d_row
    
    cursor.execute("SELECT x, y FROM cells WHERE is_obstacle=1")
    obstacles = {(r[0], r[1]) for r in cursor.fetchall()}
    
    cursor.execute("SELECT x, y FROM survivors WHERE found=0")
    survivors = {(r[0], r[1]) for r in cursor.fetchall()}
    
    direction = direction.upper()
    valid_dirs = ["N", "S", "E", "W"]
    if direction not in valid_dirs:
        conn.close()
        return {"error": "Invalid direction. Use N, S, E, or W."}
        
    MAX_DEPTH = 5
    highest_true_score = 0
    scanned_cells = []
    
    for d in range(1, MAX_DEPTH + 1):
        for w in range(-d, d + 1):
            if direction == "N": ax, ay = cx + w, cy - d
            elif direction == "S": ax, ay = cx + w, cy + d
            elif direction == "E": ax, ay = cx + d, cy + w
            elif direction == "W": ax, ay = cx - d, cy + w
            
            if not (0 <= ax < 20 and 0 <= ay < 20):
                continue
                
            # Line of sight check
            line = bresenham_line(cx, cy, ax, ay)
            occluded = False
            for lx, ly in line[1:]: # Skip the drone's own cell
                if (lx, ly) in obstacles:
                    occluded = True
                    break
                    
            if occluded:
                continue
                
            scanned_cells.append({"x": ax, "y": ay})
                
            if (ax, ay) in survivors:
                score = max(0, 100 - (d * 15))
                if score > highest_true_score:
                    highest_true_score = score
                    
    # Inject atmospheric/sensor noise +/- 12%
    noise = random.randint(-12, 12)
    final_score = max(0, min(100, highest_true_score + noise))
    
    if scanned_cells:
        import time
        cursor.execute("INSERT INTO thermal_scans (cells_json, timestamp) VALUES (?, ?)", (json.dumps(scanned_cells), time.time()))
        conn.commit()

    conn.close()
    return {"direction": direction, "signal_strength": f"{final_score}%"}

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
