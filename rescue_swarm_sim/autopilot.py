import sqlite3
import time
import heapq
from typing import Tuple, List, Optional, Set
import database
import mcp_server

GRID_WIDTH = 20
GRID_HEIGHT = 20
BASE_CAMP = (9, 9)

def _read_obstacle_set(conn: sqlite3.Connection) -> Set[Tuple[int, int]]:
    cursor = conn.cursor()
    cursor.execute("SELECT x, y FROM answer_plane WHERE obstacle_discovered=1")
    return {(int(x), int(y)) for x, y in cursor.fetchall()}

def _heuristic(ax: int, ay: int, bx: int, by: int) -> int:
    return abs(ax - bx) + abs(ay - by)

def _a_star_path(start: Tuple[int, int], target: Tuple[int, int], obstacles: Set[Tuple[int, int]]) -> Optional[List[Tuple[int, int]]]:
    if start == target:
        return []

    # If the target itself is an obstacle, we can't reach it
    if target in obstacles:
        return None

    open_heap = []
    heapq.heappush(open_heap, (_heuristic(*start, *target), 0, start))
    came_from = {}
    g_score = {start: 0}
    visited = set()

    # Fetch the scanned memory map to build the Fog of War penalty!
    conn = database._connect()
    c = conn.cursor()
    c.execute("SELECT x, y FROM answer_plane WHERE is_scanned=1")
    scanned_tiles = {(row[0], row[1]) for row in c.fetchall()}
    conn.close()

    while open_heap:
        _, current_g, current = heapq.heappop(open_heap)
        
        if current in visited:
            continue
        visited.add(current)
        
        if current == target:
            path = []
            node = current
            while node != start:
                path.append(node)
                node = came_from[node]
            path.reverse()
            return path
            
        cx, cy = current
        neighbors = [(cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)]
        
        for nx, ny in neighbors:
            if not (0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT):
                continue
            if (nx, ny) in obstacles:
                continue
                
            # EXPLORATION URGE: Add a heavy +5 cost penalty if the tile has ALREADY been scanned!
            # This causes the A* algorithm to prioritize flying through unknown "Fog of War" 
            # instead of backtracking through cleared territory.
            movement_cost = 6 if (nx, ny) in scanned_tiles else 1
            tentative_g = current_g + movement_cost
            
            if (nx, ny) not in g_score or tentative_g < g_score[(nx, ny)]:
                came_from[(nx, ny)] = current
                g_score[(nx, ny)] = tentative_g
                f = tentative_g + _heuristic(nx, ny, *target)
                heapq.heappush(open_heap, (f, tentative_g, (nx, ny)))
                
    return None

def autopilot_tick():
    """Advances all drones exactly 1 move towards their assigned goals or base camp."""
    conn = database._connect()
    cursor = conn.cursor()
    
    # Get drones
    cursor.execute("SELECT drone_id, x, y, battery FROM drones WHERE is_active=1")
    drones = cursor.fetchall()
    
    # Get known obstacles
    static_obstacles = _read_obstacle_set(conn)
    dynamic_obstacles = set(static_obstacles)
    for _d_id, dx, dy, _bat in drones:
        dynamic_obstacles.add((dx, dy))

    conn.close()

    for d_id, dx, dy, bat in drones:
        # 1. Evaluate Return to Base logic (Bingo Fuel)
        curr_pos = (dx, dy)
        path_to_base_static = _a_star_path(curr_pos, BASE_CAMP, static_obstacles - {curr_pos, BASE_CAMP})
        
        distance_to_base = len(path_to_base_static) if path_to_base_static else _heuristic(*curr_pos, *BASE_CAMP)
        battery_req_for_return = distance_to_base * 2
        
        # Are we dangerously low? (Reserve must be >= 10%)
        if curr_pos != BASE_CAMP and (bat - battery_req_for_return <= 12):
            path_to_base_dynamic = _a_star_path(curr_pos, BASE_CAMP, dynamic_obstacles - {curr_pos, BASE_CAMP})
            if path_to_base_dynamic:
                next_step = path_to_base_dynamic[0]
                _execute_and_scan(d_id, next_step[0], next_step[1])
            else:
                database.log_action(d_id, "CRITICAL: Path to base is blocked and battery is low!")
            continue

        # 2. Fetch the NEXT uncompleted waypoint for this drone
        conn = database._connect()
        c = conn.cursor()
        c.execute("SELECT seq, x, y FROM drone_waypoints WHERE drone_id=? AND is_done=0 ORDER BY seq ASC LIMIT 1", (d_id,))
        wp = c.fetchone()
        
        if not wp:
            conn.close()
            continue # Idle, waiting for SwarmCommanderFlow
            
        seq, target_x, target_y = wp
        target = (target_x, target_y)
        
        if curr_pos == target:
            # Reached waypoint natively (or spawned on it), mark as done
            conn.close()
            with database.DB_WRITE_LOCK:
                conn2 = database._connect()
                conn2.cursor().execute("UPDATE drone_waypoints SET is_done=1 WHERE drone_id=? AND seq=?", (d_id, seq))
                conn2.commit()
                conn2.close()
            continue
            
        conn.close()
        
        # 2.5 Dynamic Fog of War Skip
        # Check if the waypoint has ALREADY been scanned by any drone
        c = database._connect().cursor()
        c.execute("SELECT is_scanned FROM answer_plane WHERE x=? AND y=?", (target_x, target_y))
        scan_state = c.fetchone()
        
        if scan_state and scan_state[0] == 1:
            # Waypoint was already cleared! Skip it to save time!
            with database.DB_WRITE_LOCK:
                conn = database._connect()
                conn.cursor().execute("UPDATE drone_waypoints SET is_done=1 WHERE drone_id=? AND seq=?", (d_id, seq))
                conn.commit()
                conn.close()
            continue
            
        if target in static_obstacles:
            # Target is a known physical obstacle, skip it!
            with database.DB_WRITE_LOCK:
                conn = database._connect()
                conn.cursor().execute("UPDATE drone_waypoints SET is_done=1 WHERE drone_id=? AND seq=?", (d_id, seq))
                conn.cursor().execute("INSERT INTO logs (drone_id, message) VALUES (?, ?)", (d_id, f"WARNING: Waypoint ({target[0]},{target[1]}) is an obstacle. Skipping."))
                conn.commit()
                conn.close()
            continue
            
        # 3. Pathfind to waypoint
        path = _a_star_path(curr_pos, target, dynamic_obstacles - {curr_pos, target})
        if path:
            next_step = path[0]
            success = _execute_and_scan(d_id, next_step[0], next_step[1])
            if success and next_step == target:
                # We reached the waypoint target this exact tick, mark it done
                with database.DB_WRITE_LOCK:
                    conn = database._connect()
                    conn.cursor().execute("UPDATE drone_waypoints SET is_done=1 WHERE drone_id=? AND seq=?", (d_id, seq))
                    conn.commit()
                    conn.close()
        else:
            # Unreachable due to physical boundaries, skip waypoint
            with database.DB_WRITE_LOCK:
                conn = database._connect()
                conn.cursor().execute("UPDATE drone_waypoints SET is_done=1 WHERE drone_id=? AND seq=?", (d_id, seq))
                conn.cursor().execute("INSERT INTO logs (drone_id, message) VALUES (?, ?)", (d_id, f"WARNING: Waypoint ({target[0]},{target[1]}) is unreachable. Skipping."))
                conn.commit()
                conn.close()

def _execute_and_scan(drone_id: str, nx: int, ny: int) -> bool:
    msg = mcp_server.move_drone(drone_id, nx, ny)
    if "Failure" in msg:
        return False
        
    # If successful move, did we sense an aura?
    if "SENSOR ALERT" in msg:
        scan_msg = mcp_server.thermal_scan(drone_id)
        if "SUCCESS" in scan_msg:
             # Add a delay for dramatic effect
             time.sleep(1.0)
    
    return True
