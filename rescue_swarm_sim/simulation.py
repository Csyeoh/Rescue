import math
import json
import sys
import db

from mesa import Agent, Model
from mesa.space import ContinuousSpace
from mesa.time import RandomActivation

def cluster_tiles(tiles):
    """
    Groups adjacent points into contiguous clusters.
    Uses a basic flood-fill algorithm (4-way connectivity).
    tiles: list of (x, y) tuples
    """
    clusters = []
    unvisited = set(tiles)

    while unvisited:
        start_obj = next(iter(unvisited))
        cluster = []
        queue = [start_obj]
        unvisited.remove(start_obj)
        
        while queue:
            curr = queue.pop(0)
            cluster.append(curr)
            
            neighbors = [
                (curr[0] + 1, curr[1]),
                (curr[0] - 1, curr[1]),
                (curr[0], curr[1] + 1),
                (curr[0], curr[1] - 1)
            ]
            
            for n in neighbors:
                if n in unvisited:
                    unvisited.remove(n)
                    queue.append(n)
        clusters.append(cluster)
    return clusters

# ---------------------------------------------------------------------------
# Terrain Agents
# ---------------------------------------------------------------------------

class ObstacleAgent(Agent):
    """Represents an impassable terrain feature (rubble, collapsed structure)."""
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.discovered = False

    def step(self): pass


class BuildingAgent(Agent):
    """Represents a searchable building cell that may contain survivors."""
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.revealed = False
    def step(self): pass



class BuildingCluster:
    """Precomputed logical grouping of BuildingAgents."""
    def __init__(self, unique_id, cx, cy, tiles):
        self.id = unique_id
        self.cx = cx
        self.cy = cy
        self.tiles = tiles # list of (x,y) coordinates
        self.revealed = False


# ---------------------------------------------------------------------------
# Mobile Agents
# ---------------------------------------------------------------------------

class SurvivorAgent(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.found = False

    def step(self): pass


class DroneAgent(Agent):
    def __init__(self, unique_id, model, battery):
        super().__init__(unique_id, model)
        self.battery = battery
        self.status = "IDLE"
        self.assigned_sector = None   # dict: {cx, cy, radius} or None
        self.thermal_memory = []
        self.is_destroyed = False

    def step(self):
        if self.is_destroyed:
            return
        if self.status == "CHARGING":
            self.battery = min(100, self.battery + 2)
        if self.battery <= 0 and self.status != "CHARGING":
            self.status = "GROUNDED"
            self.is_destroyed = True
            self.model.log_action(self.unique_id, "Battery exhausted — drone lost.")

    def move(self, dx: float, dy: float):
        """Move by a delta vector clamped to exactly 1.0 unit magnitude."""
        if self.is_destroyed:
            return
        mag = math.hypot(dx, dy)
        if mag == 0:
            return
        if mag > 1.0:
            dx, dy = dx / mag, dy / mag   # normalise to unit vector

        nx = max(0.0, min(19.99, self.pos[0] + dx))
        ny = max(0.0, min(19.99, self.pos[1] + dy))
        self.model.space.move_agent(self, (nx, ny))
        self.battery -= 2


# ---------------------------------------------------------------------------
# World Model
# ---------------------------------------------------------------------------

class DisasterZoneModel(Model):
    def __init__(self, config=None):
        super().__init__()
        db.init_db()

        self.tick_count = 0
        self.mission_complete = False
        self.mission_failed = False
        self.mission_logs = []
        self.step_logs = []
        self.total_survivors = 0
        self.found_survivors = 0

        # ContinuousSpace: 20×20 units, each unit = 50 m
        self.space = ContinuousSpace(x_max=20.0, y_max=20.0, torus=False)
        self.schedule = RandomActivation(self)

        # Fast lookup maps (int tile → agent)
        self.obstacle_map: dict = {}   # (int_x, int_y) -> ObstacleAgent
        self.building_map: dict = {}   # (int_x, int_y) -> BuildingAgent
        self.building_clusters = []    # List of BuildingCluster

        # ── Load map ────────────────────────────────────────────────────────
        map_data  = config.get("map_data", {})
        obstacles = map_data.get("obstacles", [])
        buildings = map_data.get("buildings", [])
        survivors = map_data.get("survivors", [])

        for c in obstacles:
            ix, iy = int(c["x"]), int(c["y"])
            location = (ix + 0.5, iy + 0.5)
            agent = ObstacleAgent(f"obs_{ix}_{iy}", self)
            self.space.place_agent(agent, location)
            self.obstacle_map[(ix, iy)] = agent

        for b in buildings:
            ix, iy = int(b["x"]), int(b["y"])
            if (ix, iy) not in self.building_map:
                location = (ix + 0.5, iy + 0.5)
                agent = BuildingAgent(f"bld_{ix}_{iy}", self)
                self.space.place_agent(agent, location)
                self.building_map[(ix, iy)] = agent

        # Precompute the building clusters
        clusters = cluster_tiles(list(self.building_map.keys()))
        for i, cluster in enumerate(clusters):
            cx = sum(t[0] for t in cluster) / len(cluster) + 0.5
            cy = sum(t[1] for t in cluster) / len(cluster) + 0.5
            self.building_clusters.append(BuildingCluster(f"cluster_{i}", cx, cy, cluster))

        # ── Place drones at base centre (9.5, 9.5) ──────────────────────────
        for i in range(config.get("num_drones", 5)):
            drone = DroneAgent(f"drone_{i+1}", self, config.get("drone_battery", 100))
            self.space.place_agent(drone, (9.5, 9.5))
            self.schedule.add(drone)

        # ── Place survivors ──────────────────────────────────────────────────
        for s in survivors:
            sx, sy = int(s.get("x", 0)), int(s.get("y", 0))
            if sx == 9 and sy == 9:
                continue
            location = (sx + 0.5, sy + 0.5)
            survivor = SurvivorAgent(f"s_{self.total_survivors}", self)
            self.space.place_agent(survivor, location)
            self.schedule.add(survivor)
            self.total_survivors += 1

        self.sync_to_db()

    # ── Helpers ─────────────────────────────────────────────────────────────

    def log_action(self, d_id, msg):
        self.mission_logs.append({"drone_id": d_id, "message": msg, "tick": self.tick_count})

    def _tile(self, pos) -> tuple:
        """Convert continuous pos → integer tile key."""
        return (int(pos[0]), int(pos[1]))

    # ── DB sync ─────────────────────────────────────────────────────────────

    def sync_to_db(self):
        drone_data = [
            (d.unique_id, d.pos[0], d.pos[1], d.battery, d.status,
             int(d.is_destroyed), json.dumps(d.thermal_memory),
             json.dumps(d.assigned_sector))
            for d in self.schedule.agents if isinstance(d, DroneAgent)
        ]
        obstacle_data = [
            (a.unique_id, a.pos[0], a.pos[1], int(a.discovered))
            for a in self.obstacle_map.values()
        ]
        building_data = [
            (a.unique_id, a.pos[0], a.pos[1], int(a.revealed))
            for a in self.building_map.values()
        ]
        survivor_data = []
        for agent in self.schedule.agents:
            if isinstance(agent, SurvivorAgent):
                survivor_data.append(
                    (agent.unique_id, agent.pos[0], agent.pos[1], int(agent.found))
                )

        building_cluster_data = [
            (bc.id, bc.cx, bc.cy, int(bc.revealed), len(bc.tiles))
            for bc in self.building_clusters
        ]

        db.sync_world_state(
            drone_data, obstacle_data, building_data, building_cluster_data, survivor_data
        )

    # ── Dispatcher-only sync (decoupled) ────────────────────────────────────

    def dispatcher_step(self):
        """
        Lightweight sync that pulls ONLY dispatcher-written fields from the DB
        into the in-memory Mesa agents:
          - drone.status      (IDLE → SEARCHING)
          - drone.assigned_sector  (sector dict or None)
        """
        conn = db.get_db_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id, status, assigned_sector FROM drones")
        for (drone_id, status, sector_json) in cursor.fetchall():
            for agent in self.schedule.agents:
                if isinstance(agent, DroneAgent) and agent.unique_id == drone_id:
                    agent.status = status
                    agent.assigned_sector = json.loads(sector_json) if sector_json else None
                    break
        conn.close()

    # ── Physics step ─────────────────────────────────────────────────────────

    def step(self, batch_intents=None):
        if self.mission_complete or self.mission_failed:
            return
        self.tick_count += 1

        # 1. Sync status / sector from DB (source of truth for agent decisions)
        conn = db.get_db_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id, status, assigned_sector, thermal_memory FROM drones")
        drone_rows = {r[0]: r for r in cursor.fetchall()}
        for agent in self.schedule.agents:
            if isinstance(agent, DroneAgent) and agent.unique_id in drone_rows:
                r = drone_rows[agent.unique_id]
                agent.status = r[1]
                agent.assigned_sector = json.loads(r[2]) if r[2] else None
                agent.thermal_memory  = json.loads(r[3]) if r[3] else []

        # 2. Sync building revealed from DB
        cursor.execute("SELECT id, revealed FROM buildings")
        for bld_id, rev in cursor.fetchall():
            # find building agent by id
            for a in self.building_map.values():
                if a.unique_id == bld_id:
                    a.revealed = bool(rev)
        conn.close()

        # 3. Apply drone intents
        if batch_intents:
            for d_id, intent in batch_intents.items():
                drone = next(
                    (a for a in self.schedule.agents
                     if isinstance(a, DroneAgent) and a.unique_id == d_id),
                    None
                )
                if not drone or drone.is_destroyed:
                    continue

                new_status = intent.get("status", drone.status)
                drone.status = new_status

                self.step_logs.append({
                    "step": self.tick_count,
                    "drone_id": d_id,
                    "pos": drone.pos,
                    "status": drone.status,
                })

                if new_status in ["SEARCHING", "RETURNING"]:
                    dx = float(intent.get("dx", 0.0))
                    dy = float(intent.get("dy", 0.0))

                    if math.hypot(dx, dy) > 0:
                        # Tile-based Collision Check (Robust)
                        nx, ny = drone.pos[0] + dx, drone.pos[1] + dy
                        tx, ty = int(nx), int(ny)
                        # Check maps for any blocking agent in the target integer tile
                        collision_agent = self.obstacle_map.get((tx, ty)) or self.building_map.get((tx, ty))
                        
                        if collision_agent:
                            drone.status = "CRASHED"
                            drone.is_destroyed = True
                            agent_type = "building" if isinstance(collision_agent, BuildingAgent) else "obstacle"
                            self.log_action(d_id, f"FATAL CRASH: Entered {agent_type} tile at ({tx}, {ty})!")
                        else:
                            drone.move(dx, dy)

                    # Reveal area within 1.0-unit radius using ContinuousSpace
                    nearby = self.space.get_neighbors(drone.pos, radius=1.0, include_center=True)
                    
                    revealed_cells = []
                    # Standardized revealed logic: 0.5 unit grid (40x40)
                    # For each drone, update the coverage cells in its vicinity
                    # This is a bit brute-force but for 1.0 radius it's only ~16 checks per drone.
                    cx, cy = drone.pos
                    r = 1.0
                    for ix in range(max(0, int((cx - r) * 2)), min(40, int((cx + r) * 2) + 1)):
                        for iy in range(max(0, int((cy - r) * 2)), min(40, int((cy + r) * 2) + 1)):
                            # Check distance from drone to cell center
                            cell_x = ix * 0.5 + 0.25
                            cell_y = iy * 0.5 + 0.25
                            if math.hypot(cell_x - cx, cell_y - cy) <= r:
                                revealed_cells.append((ix, iy))

                    if revealed_cells:
                        db.sync_coverage(revealed_cells)

                    for obj in nearby:
                        if isinstance(obj, BuildingAgent):
                            obj.revealed = True
                            # Force coverage update for building location
                            db.sync_coverage([(int(obj.pos[0]*2), int(obj.pos[1]*2))])
                        elif isinstance(obj, ObstacleAgent):
                            obj.discovered = True
                            # Force coverage update for obstacle location
                            db.sync_coverage([(int(obj.pos[0]*2), int(obj.pos[1]*2))])
                        elif isinstance(obj, SurvivorAgent) and not obj.found:
                            obj.found = True
                            self.found_survivors += 1
                            self.log_action(d_id, f"Survivor found at {obj.pos}!")

        # 4. Mesa schedule step (battery drain / charge)
        self.schedule.step()

        # Re-evaluate cluster visibility mapping
        for bc in self.building_clusters:
            if not bc.revealed:
                if all(self.building_map[t].revealed for t in bc.tiles):
                    bc.revealed = True

        # 5. Mission completion checks
        any_destroyed = any(
            getattr(a, "is_destroyed", False)
            for a in self.schedule.agents
            if isinstance(a, DroneAgent)
        )
        if any_destroyed:
            self.mission_failed = True
        elif self.total_survivors > 0 and self.found_survivors >= self.total_survivors:
            self.mission_complete = True

        self.sync_to_db()

sim_world = None

def initialize_world(config=None):
    global sim_world
    sim_world = DisasterZoneModel(config)
    return sim_world
