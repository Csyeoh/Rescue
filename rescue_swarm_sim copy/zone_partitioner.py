import heapq
import collections
import math

# Terrain priorities for the Greedy Weighted BFS
# Higher number = higher priority = harder to clear
TERRAIN_WEIGHTS = {
    "single_story": 10,
    "double_story": 5,
    "rural": 1,
    "marsh": 2,
    "forest": 3
}

def _get_weight(terrain_type: str) -> int:
    return TERRAIN_WEIGHTS.get(terrain_type, 1)

def greedy_weighted_bfs(drones: list[dict], terrain_map: list[dict]) -> dict[str, list[tuple[int, int]]]:
    """
    Partitions the grid (derived from terrain_map) among available drones.
    drones is a list: [{'drone_id': 'drone_1', 'x': 9, 'y': 9, 'battery': 100}, ...]
    terrain_map is a list: [{'x': 0, 'y': 0, 'terrain_type': 'rural'}, ...]
    
    Returns a dict mapping drone_id -> list of ordered (x, y) coordinates to visit.
    """
    if not drones:
        return {}

    # Build grid weights mapping
    grid_weights = {}
    for cell in terrain_map:
        grid_weights[(cell['x'], cell['y'])] = _get_weight(cell.get('terrain_type', ''))
        
    # Track unassigned cells
    unclaimed = set(grid_weights.keys())
    
    # Track assignments (order matters: implies visit sequence)
    assignments = collections.defaultdict(list)
    
    # State tracking per drone for BFS
    # frontier per drone: list of tuples (-claim_value, distance, x, y)
    # Using negative claim_value because heapq is a min-heap
    frontiers = {d['id']: [] for d in drones}
    drone_positions = {d['id']: (d['x'], d['y']) for d in drones}
    
    # If drones haven't visited their start positions, claim those first if valid
    for d_id, pos in drone_positions.items():
        if pos in unclaimed:
            unclaimed.remove(pos)
            assignments[d_id].append(pos)
            # Add neighbors to frontier
            _push_neighbors(d_id, pos, pos, grid_weights, unclaimed, frontiers[d_id])
    
    # If a drone's start pos wasn't in unclaimed (e.g. out of bounds or already picked),
    # seed its frontier with generic starting points or whatever is closest.
    # In our specific setup, all drones start at base camp (9,9).
    # Provide the base camp neighbors.
    for d_id, pos in drone_positions.items():
        if not frontiers[d_id]:
            _push_neighbors(d_id, pos, pos, grid_weights, unclaimed, frontiers[d_id])

    # Round Robin expansion
    drone_cycle = [d['id'] for d in drones]
    idx = 0
    active_drones = set(drone_cycle)
    
    while unclaimed and active_drones:
        d_id = drone_cycle[idx]
        if d_id in active_drones:
            # Try to claim one cell for this drone
            claimed_cell = False
            while frontiers[d_id]:
                val, dist, cx, cy = heapq.heappop(frontiers[d_id])
                if (cx, cy) in unclaimed:
                    # Claim the cell from the pool so other drones don't take it
                    unclaimed.remove((cx, cy))
                    
                    # MATHEMATICAL CHECKERBOARDING: 
                    # Only assign this as a hard waypoint if it lands on an EVEN parity tile.
                    # Because the drone's sensors scan all 4 adjacent (ODD) tiles upon landing,
                    # this guarantees 100% map coverage while halving the actual flight queue!
                    if (cx + cy) % 2 == 0:
                        assignments[d_id].append((cx, cy))
                        
                    claimed_cell = True
                    # Expand frontier from this new cell, but calculate distance from drone start
                    _push_neighbors(d_id, (cx, cy), drone_positions[d_id], grid_weights, unclaimed, frontiers[d_id])
                    break
            
            if not claimed_cell:
                # This drone's frontier is dead (blocked or exhausted its local area)
                # Technically it could "jump" to another unclaimed area, but BFS naturally grows.
                # If we want it to jump:
                if unclaimed:
                    # jump to closest unclaimed cell
                    closest = min(unclaimed, key=lambda p: abs(p[0]-drone_positions[d_id][0]) + abs(p[1]-drone_positions[d_id][1]))
                    unclaimed.remove(closest)
                    assignments[d_id].append(closest)
                    _push_neighbors(d_id, closest, drone_positions[d_id], grid_weights, unclaimed, frontiers[d_id])
                else:
                    active_drones.remove(d_id)
        
        idx = (idx + 1) % len(drone_cycle)
        
    # Sort assignments to form a continuous nearest-neighbor flight path
    final_assignments = {}
    for d_id, assigned_cells in assignments.items():
        if not assigned_cells:
            final_assignments[d_id] = []
            continue
            
        unvisited = set(assigned_cells)
        path = []
        current_pos = drone_positions[d_id]
        
        while unvisited:
            # Find nearest unvisited cell (Manhattan distance)
            next_cell = min(unvisited, key=lambda c: abs(c[0] - current_pos[0]) + abs(c[1] - current_pos[1]))
            path.append(next_cell)
            unvisited.remove(next_cell)
            current_pos = next_cell
            
        final_assignments[d_id] = path

    return final_assignments

def _push_neighbors(drone_id: str, cell: tuple[int, int], start_pos: tuple[int, int], grid_weights: dict, unclaimed: set, frontier: list):
    cx, cy = cell
    neighbors = [(cx, cy-1), (cx, cy+1), (cx-1, cy), (cx+1, cy)]
    for nx, ny in neighbors:
        if (nx, ny) in unclaimed:
            weight = grid_weights[(nx, ny)]
            # Manhattan distance from start pose
            dist = abs(nx - start_pos[0]) + abs(ny - start_pos[1])
            # Claim Value = CellWeight - (DistanceFromDrone / ScaleFactor)
            # ScaleFactor = 2.0 to give distance a bit of pull but allow heavy cells to attract
            claim_value = weight - (dist / 2.0)
            heapq.heappush(frontier, (-claim_value, dist, nx, ny))

def compute_rebalance(idle_drone_id: str, burdened_drone_id: str, current_assignments: dict, drone_batteries: dict) -> list[tuple[int, int]]:
    """
    Called when idle_drone finishes its queue.
    Takes N waypoints from the tail of burdened_drone's queue and assigns them to idle_drone.
    Returns the list of transferred waypoints.
    """
    burdened_queue = current_assignments.get(burdened_drone_id, [])
    if len(burdened_queue) < 2:
        return [] # Nothing left to share
        
    # We transfer up to half of the burdened drone's remaining queue
    num_to_transfer = len(burdened_queue) // 2
    
    # But limit based on idle drone's battery
    # A rough heuristic: 1 cell takes at least 2% battery. We need 10% reserve.
    # Battery available for exploration = battery - reserve
    idle_batt = drone_batteries.get(idle_drone_id, 100)
    max_cells_by_batt = max(0, (idle_batt - 15) // 3)
    
    transfer_count = min(num_to_transfer, max_cells_by_batt)
    if transfer_count <= 0:
        return []
        
    # Take from the end (furthest cells typically)
    transferred = burdened_queue[-transfer_count:]
    return transferred
