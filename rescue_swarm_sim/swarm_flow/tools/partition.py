import heapq
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
import simulation
import ai_tools


def get_active_drone_count() -> int:
    """Directly queries the Mesa environment for the number of active DroneAgents."""
    world = simulation.sim_world
    if not world: return 0
    
    from simulation import DroneAgent
    count = 0
    for agent in world.schedule.agents:
        if isinstance(agent, DroneAgent):
            count += 1
    return count


def get_current_map_state() -> dict:
    """
    Assembles the complete world state directly from the Mesa environment and the DB.
    Used for WebSocket broadcasts – no dependency on api.py.
    """
    world = simulation.sim_world
    if not world: return {"error": "Simulation not initialized."}

    from simulation import TerrainAgent, DroneAgent
    
    terrain = []
    survivors = []
    
    # We use SQLite for survivors and terrain discovery status to ensure consistency
    import database
    import sqlite3
    conn = database._connect()
    cursor = conn.cursor()
    cursor.execute("SELECT survivor_id, x, y, is_discovered FROM survivors")
    surv_rows = cursor.fetchall()
    survivors = [{"id": r[0], "x": r[1], "y": r[2], "discovered": bool(r[3])} for r in surv_rows]
    
    cursor.execute("SELECT x, y, obstacle_discovered, is_scanned FROM answer_plane")
    answer_data = {(r[0], r[1]): {"obs": bool(r[2]), "scanned": bool(r[3])} for r in cursor.fetchall()}
    conn.close()

    for contents, (x, y) in world.grid.coord_iter():
        for obj in contents:
            if isinstance(obj, TerrainAgent):
                ans = answer_data.get((x, y), {"obs": False, "scanned": False})
                terrain.append({
                    "x": x, "y": y,
                    "altitude": obj.altitude,
                    "is_obstacle": obj.is_obstacle,
                    "terrain_type": obj.terrain_type,
                    "obstacle_discovered": ans["obs"],
                    "discovered": ans["scanned"],
                    "assigned_drone": getattr(obj, "assigned_drone", None),
                })

    # Drones are dynamic — collect from schedule
    drones = []
    for agent in world.schedule.agents:
        if isinstance(agent, DroneAgent):
            drones.append({
                "id": agent.unique_id,
                "x": agent.pos[0] if agent.pos else 9,
                "y": agent.pos[1] if agent.pos else 9,
                "battery": agent.battery,
                "status": getattr(agent, "status", "IDLE"),
            })

    return {
        "grid": {"width": world.width, "height": world.height},
        "terrain": terrain,
        "drones": drones,
        "survivors": survivors,
    }


def partition_grid_greedy_bfs(num_drones: int, base_pos_x: int, base_pos_y: int) -> dict:
    """
    Runs a Multi-Source Greedy BFS on the Mesa grid to assign sectors.
    Returns the partitions dictionary mapping drone_id to list of (x, y) coordinates.
    Syncs to both Mesa Agents and SQLite Database.
    """
    world = simulation.sim_world
    if not world: return {}

    from simulation import TerrainAgent
    grid_data = {}
    terrain_agents = {}
    
    for contents, (x, y) in world.grid.coord_iter():
        for obj in contents:
            if isinstance(obj, TerrainAgent):
                pos = (x, y)
                grid_data[pos] = {
                    'altitude': getattr(obj, 'altitude', 0.0),
                    'terrain_type': getattr(obj, 'terrain_type', 'terrain'),
                }
                terrain_agents[pos] = obj
                break

    def calculate_weight(cell):
        altitude = float(cell.get('altitude', 0))
        w_altitude = 0.4 * altitude
        ttype = cell.get('terrain_type', 'terrain')
        if ttype == 'single_story': t_val = 1.0 
        elif ttype == 'multiple_story': t_val = 2.0
        else: t_val = 5.0 
        w_terrain = 0.3 * t_val
        return w_altitude + w_terrain

    base_pos = (base_pos_x, base_pos_y)
    claimed = {base_pos}
    partitions = {f"drone_{i+1}": [] for i in range(num_drones)}
    pqs = {f"drone_{i+1}": [] for i in range(num_drones)}
    
    import math
    for i in range(num_drones):
        drone_id = f"drone_{i+1}"
        angle = (2 * math.pi * i) / num_drones
        radius = 6.0
        sx = max(0, min(19, int(base_pos_x + radius * math.cos(angle))))
        sy = max(0, min(19, int(base_pos_y + radius * math.sin(angle))))
        seed = (sx, sy)
        if seed in claimed:
            for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
                candidate = (sx + dx, sy + dy)
                if 0 <= candidate[0] < 20 and 0 <= candidate[1] < 20 and candidate not in claimed:
                    seed = candidate
                    break
        if seed not in claimed:
            claimed.add(seed)
            partitions[drone_id].append(seed)
            if seed in terrain_agents: setattr(terrain_agents[seed], 'assigned_drone', drone_id)
            for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]:
                nx, ny = seed[0] + dx, seed[1] + dy
                if 0 <= nx < 20 and 0 <= ny < 20 and (nx, ny) not in claimed:
                    if (nx, ny) in grid_data:
                        w = calculate_weight(grid_data[(nx, ny)])
                        heapq.heappush(pqs[drone_id], (w, (nx, ny)))

    drone_cycle = [f"drone_{i+1}" for i in range(num_drones)]
    while len(claimed) < 400:
        progress = False
        for d_id in drone_cycle:
            pq = pqs[d_id]
            valid_cell = None
            while pq:
                w, (cx, cy) = heapq.heappop(pq)
                if (cx, cy) not in claimed:
                    valid_cell = (cx, cy)
                    break
            if valid_cell:
                progress = True
                claimed.add(valid_cell)
                partitions[d_id].append(valid_cell)
                if valid_cell in terrain_agents: setattr(terrain_agents[valid_cell], 'assigned_drone', d_id)
                cx, cy = valid_cell
                for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]:
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < 20 and 0 <= ny < 20 and (nx, ny) not in claimed:
                        if (nx, ny) in grid_data:
                            nw = calculate_weight(grid_data[(nx, ny)])
                            heapq.heappush(pq, (nw, (nx, ny)))
        if not progress and len(claimed) < 400:
            unclaimed = [p for p in grid_data.keys() if p not in claimed]
            if unclaimed:
                smallest_drone = min(partitions.keys(), key=lambda k: len(partitions[k]))
                valid_cell = unclaimed[0]
                claimed.add(valid_cell)
                partitions[smallest_drone].append(valid_cell)
                if valid_cell in terrain_agents: setattr(terrain_agents[valid_cell], 'assigned_drone', smallest_drone)
                nw = calculate_weight(grid_data[valid_cell])
                heapq.heappush(pqs[smallest_drone], (nw, valid_cell))

    # --- FIX 2: Write to DB and Populate mesa priority_searching_list ---
    from simulation import DroneAgent
    drones_in_sim = {a.unique_id: a for a in world.schedule.agents if isinstance(a, DroneAgent)}
    
    for d_id, path in partitions.items():
        # 1. Sync to Mesa Agent
        if d_id in drones_in_sim:
            # Sort by weight (Lowest first) to create the priority path
            sorted_path = sorted(path, key=lambda p: calculate_weight(grid_data.get(p, {})))
            drones_in_sim[d_id].priority_searching_list = sorted_path
            drones_in_sim[d_id].status = "SEARCHING"
        
        # 2. Sync to SQLite DB (via ai_tools)
        ai_tools.assign_waypoints(d_id, path)

    # --- FIX 3: Write Visual Grid and Summary to partition_result.txt ---
    try:
        res_path = os.path.join(os.path.dirname(__file__), "..", "partition_result.txt")
        with open(res_path, "w", encoding="utf-8") as f:
            f.write("=== SWARM PARTITION VISUAL GRID (20x20) ===\n")
            for y in range(20):
                row_str = ""
                for x in range(20):
                    agent = terrain_agents.get((x, y))
                    d_assigned = getattr(agent, 'assigned_drone', None)
                    if d_assigned:
                        # Show the drone number (e.g., '1' for drone_1)
                        row_str += d_assigned.split("_")[1] + " "
                    else:
                        row_str += ". "
                f.write(row_str + "\n")
            
            f.write("\n=== PARTITION SUMMARY ===\n")
            for d_id, path in partitions.items():
                f.write(f"{d_id}: {len(path)} sectors assigned.\n")
            f.write(f"Total sectors claimed: {len(claimed)}/400\n")
    except Exception as e:
        print(f"Error writing partition_result.txt: {e}")

    try:
        import websocket_manager
        updated_state = get_current_map_state()
        if "error" not in updated_state:
            websocket_manager.send_to_ui("partitioning_complete", updated_state)
    except Exception as e:
        print(f"Broadcast complete error: {e}")
    
    return partitions
