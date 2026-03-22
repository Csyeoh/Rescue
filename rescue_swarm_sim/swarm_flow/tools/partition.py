import heapq
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
import simulation


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

    from simulation import CellAgent, DroneAgent, SurvivorAgent
    
    terrain = []
    survivors = []
    for contents, (x, y) in world.grid.coord_iter():
        for obj in contents:
            if isinstance(obj, CellAgent):
                terrain.append({
                    "x": x, "y": y,
                    "altitude": obj.altitude,
                    "building_height": obj.building_height,
                    "is_obstacle": obj.is_obstacle,
                    "terrain_type": obj.terrain_type,
                    "obstacle_discovered": obj.obstacle_discovered,
                    "assigned_drone": getattr(obj, "assigned_drone", None),
                })
            elif isinstance(obj, SurvivorAgent):
                survivors.append({"id": obj.unique_id, "x": x, "y": y, "discovered": obj.found})

    # Drones are dynamic — collect from schedule
    drones = []
    for agent in world.schedule.agents:
        if isinstance(agent, DroneAgent):
            drones.append({
                "id": agent.unique_id,
                "x": agent.pos[0] if agent.pos else 9,
                "y": agent.pos[1] if agent.pos else 9,
                "battery": agent.battery,
                "status": agent.status,
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
    """
    world = simulation.sim_world
    if not world: return {}


    from simulation import CellAgent
    grid_data = {}
    cell_agents = {}
    
    # We now fetch CellAgents iterating the grid instead of the schedule
    for contents, (x, y) in world.grid.coord_iter():
        for obj in contents:
            if isinstance(obj, CellAgent):
                pos = (x, y)
                grid_data[pos] = {
                    'altitude': getattr(obj, 'altitude', 0.0),
                    'terrain_type': getattr(obj, 'terrain_type', 'terrain'),
                    'building_height': getattr(obj, 'building_height', 0.0)
                }
                cell_agents[pos] = obj
                break # Only one CellAgent per cell expected

    # Weighting Logic (Lower score = Higher Priority for Greedy)
    def calculate_weight(cell):
        # We want to MINIMIZE this score to be 'Greedy' for best cells
        # Formula: 0.4*Altitude + 0.3*TerrainType + 0.3*BuildingHeight
        
        # Altitude (Weight 0.4)
        altitude = float(cell.get('altitude', 0))
        w_altitude = 0.4 * altitude
        
        # Terrain type (Weight 0.3)
        # Prioritize search areas (residential/complex) over empty terrain.
        # Lower value = Higher Priority.
        ttype = cell.get('terrain_type', 'terrain')
        if ttype == 'single_story':
            t_val = 1.0 # High priority
        elif ttype == 'multi_story':
            t_val = 2.0 # Medium priority (complex)
        else:
            t_val = 5.0 # Low priority (empty ground)
        w_terrain = 0.3 * t_val
            
        # Building height (Weight 0.3)
        b_height = float(cell.get('building_height', 0))
        w_height = 0.3 * b_height
            
        return w_altitude + w_terrain + w_height

    #  Multi-Source BFS Setup
    base_pos = (base_pos_x, base_pos_y)
    
    claimed = {base_pos}
    partitions = {f"drone_{i+1}": [] for i in range(num_drones)}
    
    # Priority Queues per drone: list of (weight, (x, y))
    pqs = {f"drone_{i+1}": [] for i in range(num_drones)}
    
    # --- STARVATION FIX: Spread Seeds ---
    # Instead of just base neighbors, we give each drone a different "sector seed"
    import math
    print(f"DEBUG: Partitioning for {num_drones} drones. Spreading seeds...")
    for i in range(num_drones):
        drone_id = f"drone_{i+1}"
        # Calculate a point roughly 6 units away in a unique direction
        angle = (2 * math.pi * i) / num_drones
        radius = 6.0
        sx = int(base_pos_x + radius * math.cos(angle))
        sy = int(base_pos_y + radius * math.sin(angle))
        
        # Clamp to grid (0-19)
        sx = max(0, min(19, sx))
        sy = max(0, min(19, sy))
        
        # Determine unique seed
        seed = (sx, sy)
        if seed in claimed:
            # Shift seed slightly if collision
            for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
                candidate = (sx + dx, sy + dy)
                if 0 <= candidate[0] < 20 and 0 <= candidate[1] < 20 and candidate not in claimed:
                    seed = candidate
                    break
        
        if seed not in claimed:
            claimed.add(seed)
            partitions[drone_id].append(seed)
            if seed in cell_agents:
                setattr(cell_agents[seed], 'assigned_drone', drone_id)
            
            # Initial neighbors for this drone's PQ
            for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]:
                nx, ny = seed[0] + dx, seed[1] + dy
                if 0 <= nx < 20 and 0 <= ny < 20 and (nx, ny) not in claimed:
                    if (nx, ny) in grid_data:
                        w = calculate_weight(grid_data[(nx, ny)])
                        heapq.heappush(pqs[drone_id], (w, (nx, ny)))
        else:
            print(f"WARNING: Could not find unique seed for {drone_id}")
                
    # 4. Greedy Expansion Loop with Round Robin
    drone_cycle = [f"drone_{i+1}" for i in range(num_drones)]
    while len(claimed) < 400: # For 20x20 grid
        progress = False
        for d_id in drone_cycle:
            pq = pqs[d_id]
            # Find a valid cell to claim
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
                
                # Assign to Mesa agent directly
                if valid_cell in cell_agents:
                    setattr(cell_agents[valid_cell], 'assigned_drone', d_id)
                
                # Add neighbors to this drone's queue
                cx, cy = valid_cell
                for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]:
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < 20 and 0 <= ny < 20 and (nx, ny) not in claimed:
                        if (nx, ny) in grid_data:
                            nw = calculate_weight(grid_data[(nx, ny)])
                            heapq.heappush(pq, (nw, (nx, ny)))
                            
        # If no standard progress was made but cells remain (disconnected components),
        # force jump to random unclaimed cell
        if not progress and len(claimed) < 400:
            unclaimed = [p for p in grid_data.keys() if p not in claimed]
            if unclaimed:
                # Give to the drone with the smallest partition to normalize
                smallest_drone = min(partitions.keys(), key=lambda k: len(partitions[k]))
                valid_cell = unclaimed[0]
                claimed.add(valid_cell)
                partitions[smallest_drone].append(valid_cell)
                if valid_cell in cell_agents:
                    setattr(cell_agents[valid_cell], 'assigned_drone', smallest_drone)
                nw = calculate_weight(grid_data[valid_cell])
                heapq.heappush(pqs[smallest_drone], (nw, valid_cell))

    
    # Broadcast to UI: Partitioning Complete
    try:
        import websocket_manager
        updated_state = get_current_map_state()
        if "error" not in updated_state:
            websocket_manager.send_to_ui("partitioning_complete", updated_state)
    except Exception as e:
        print(f"Broadcast complete error: {e}")
        
    # INJECT DIRECTLY INTO MESA STATE
    if world:
        from simulation import DroneAgent
        for agent in world.schedule.agents:
            if isinstance(agent, DroneAgent):
                raw_list = partitions.get(agent.unique_id, [])
                # Re-sort by weight (Lowest Weight == Highest Priority)
                sorted_list = sorted(raw_list, key=lambda pos: calculate_weight(grid_data.get(pos, {})))
                agent.priority_searching_list = sorted_list
    
    return partitions


def compute_rebalance(idle_drone_id: str, burdened_drone_id: str, current_assignments: dict, drone_batteries: dict) -> list[tuple[int, int]]:
    """
    Algorithm to offload searching tasks from a burdened drone to an idle one.
    Takes the furthest 1/3 of the burdened drone's queue and validates against idle drone's battery.
    """
    burdened_queue = current_assignments.get(burdened_drone_id, [])
    if len(burdened_queue) < 4:
        return [] # Not enough work to justify a hand-off
        
    # Transfer roughly 30% of the remaining queue
    num_to_transfer = len(burdened_queue) // 3
    
    # Check idle drone's range (Battery - 15% safety reserve)
    # Each cell cost is roughly 2% battery + 1% for scanning
    idle_batt = drone_batteries.get(idle_drone_id, 100)
    max_cells_by_batt = max(0, (idle_batt - 15) // 3)
    
    transfer_count = min(num_to_transfer, max_cells_by_batt)
    if transfer_count <= 0:
        return []
        
    # Take from the end of the queue (the furthest points)
    transferred = burdened_queue[-transfer_count:]
    return transferred
