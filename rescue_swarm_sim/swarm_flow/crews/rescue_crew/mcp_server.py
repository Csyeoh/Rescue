from fastmcp import FastMCP
import sys
import os
import heapq
import sqlite3
import json

DB_PATH = "live_state.db"

def get_db_conn():
    if not os.path.exists(DB_PATH):
        # Create a temporary empty DB if it doesn't exist yet to prevent crash
        conn = sqlite3.connect(DB_PATH)
        conn.close()
    return sqlite3.connect(DB_PATH, timeout=10)

mcp = FastMCP("RescueSwarm")

@mcp.tool()
def get_drone_context(drone_id: str) -> dict:
    """Returns battery, position, status, and search list for a drone."""
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT x, y, battery, status, is_destroyed, thermal_memory, priority_list FROM drones WHERE id=?", (drone_id,))
    row = cursor.fetchone()
    conn.close()
    if not row: return {"error": "not found"}
    return {
        "id": drone_id, "pos": {"x": row[0], "y": row[1]}, "battery": row[2], 
        "status": row[3], "is_destroyed": bool(row[4]),
        "thermal_memory": json.loads(row[5]), "priority_list": json.loads(row[6])
    }

@mcp.tool()
def thermal_scan(drone_id: str) -> str:
    """Reveals adjacent cells, detects auras, and updates lists in DB."""
    conn = get_db_conn()
    cursor = conn.cursor()
    # Get current pos
    cursor.execute("SELECT x, y, thermal_memory FROM drones WHERE id=?", (drone_id,))
    d_row = cursor.fetchone()
    if not d_row: return "Error: drone not found"
    cx, cy, t_mem_raw = d_row
    t_mem = json.loads(t_mem_raw)
    
    # Reveal and Check Auras
    adj = [(cx, cy), (cx, cy-1), (cx, cy+1), (cx-1, cy), (cx+1, cy)]
    revealed = 0
    new_auras = []
    for ax, ay in adj:
        if 0 <= ax < 20 and 0 <= ay < 20:
            cursor.execute("UPDATE cells SET obstacle_discovered = 1 WHERE x=? AND y=? AND is_obstacle=1", (ax, ay))
            cursor.execute("SELECT thermal_aura FROM cells WHERE x=? AND y=?", (ax, ay))
            c_row = cursor.fetchone()
            if c_row and c_row[0] == 1:
                pos = [ax, ay]
                if pos not in t_mem:
                    t_mem.append(pos)
                    new_auras.append(f"({ax},{ay})")
            
            # Clean global lists (simulated by updating all drone rows)
            cursor.execute("SELECT id, priority_list FROM drones")
            all_drones = cursor.fetchall()
            for did, p_list_raw in all_drones: 
                p_list = json.loads(p_list_raw)
                if [ax, ay] in p_list:
                    p_list.remove([ax, ay])
                    cursor.execute("UPDATE drones SET priority_list=? WHERE id=?", (json.dumps(p_list), did))
            revealed += 1

    cursor.execute("UPDATE drones SET thermal_memory=? WHERE id=?", (json.dumps(t_mem), drone_id))
    conn.commit()
    conn.close()
    msg = f"Revealed {revealed} cells."
    if new_auras: msg += f" Thermal auras at {', '.join(new_auras)}."
    return msg

@mcp.tool()
def get_claimable_pool() -> list:
    """Returns list of drones with available waypoints."""
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, priority_list, status FROM drones WHERE status IN ('RETURNING', 'CHARGING', 'IDLE')")
    rows = cursor.fetchall()
    conn.close()
    pool = []
    for r in rows:
        p_list = json.loads(r[1])
        if p_list:
            pool.append({"drone_id": r[0], "count": len(p_list), "status": r[2], "target_x": p_list[0][0], "target_y": p_list[0][1]})
    return pool

@mcp.tool()
def claim_waypoints(requesting_drone_id: str, target_drone_id: str, count: int) -> str:
    """Transfers waypoints between drones in DB."""
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT priority_list FROM drones WHERE id=?", (requesting_drone_id,))
    req_list = json.loads(cursor.fetchone()[0])
    cursor.execute("SELECT priority_list FROM drones WHERE id=?", (target_drone_id,))
    tar_list = json.loads(cursor.fetchone()[0])
    
    to_transfer = tar_list[-count:]
    new_tar = tar_list[:-count]
    req_list.extend(to_transfer)
    
    cursor.execute("UPDATE drones SET priority_list=? WHERE id=?", (json.dumps(req_list), requesting_drone_id))
    cursor.execute("UPDATE drones SET priority_list=? WHERE id=?", (json.dumps(new_tar), target_drone_id))
    conn.commit()
    conn.close()
    return f"Claimed {len(to_transfer)} waypoints."

@mcp.tool()
def check_task_viability(drone_id: str, target_x: int, target_y: int) -> dict:
    """Calculates A* distance to target and back to base."""
    conn = get_db_conn()
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
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT x, y FROM drones WHERE id=?", (drone_id,))
    start = cursor.fetchone()
    cursor.execute("SELECT x, y FROM cells WHERE is_obstacle=1 AND obstacle_discovered=1")
    obs = set(cursor.fetchall())
    conn.close()
    
    goal = (target_x, target_y)
    if start == goal: return {"x": start[0], "y": start[1]}
    
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
    
    if goal not in came_from: return {"x": start[0], "y": start[1]}
    path = []
    curr = goal
    while curr != start:
        path.append(curr)
        curr = came_from[curr]
    return {"x": path[-1][0], "y": path[-1][1]}

if __name__ == "__main__":
    mcp.run()
