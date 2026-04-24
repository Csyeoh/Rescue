import math
import json
import sys
import random
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
    def __init__(self, unique_id, model, height: float):
        super().__init__(unique_id, model)
        self.discovered = False
        self.height = float(height)

    def step(self): pass


class BuildingAgent(Agent):
    """Represents a searchable building cell that may contain survivors."""
    def __init__(self, unique_id, model, height: float):
        super().__init__(unique_id, model)
        self.revealed = False
        self.height = float(height)
    def step(self): pass



class BuildingCluster:
    """Precomputed logical grouping of BuildingAgents."""
    def __init__(self, unique_id, cx, cy, tiles):
        self.id = unique_id
        self.cx = cx
        self.cy = cy
        self.tiles = tiles # list of (x,y) coordinates
        self.revealed = False
        self.assigned_to = None


# ---------------------------------------------------------------------------
# Mobile Agents
# ---------------------------------------------------------------------------

class SurvivorAgent(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.found = False
        self.found_tick = None

    def step(self): pass


class DroneAgent(Agent):
    def __init__(self, unique_id, model, battery):
        super().__init__(unique_id, model)
        self.battery = battery
        self.status = "IDLE"
        self.z = 1.1
        self.task_queue = []   # replaces assigned_sector
        self.messages_for_commander = []
        self.error_count = 0
        self.thermal_memory = []
        self.is_destroyed = False
        self.destroy_reason = None
        self.destroy_tick = None

    def step(self):
        if self.is_destroyed:
            return
        
        # Base charging logic
        if hasattr(self.model, 'bases'):
            for b in self.model.bases:
                bx, by = b.get("x", 9)+0.5, b.get("y", 9)+0.5
                if math.hypot(bx - self.pos[0], by - self.pos[1]) < 0.5:
                    self.battery = 100
                    if self.status == "RETURNING":
                        self.status = "IDLE"

        if self.battery <= 0:
            if not self.destroy_reason:
                pos = getattr(self, "pos", None)
                if pos:
                    self.destroy_reason = f"BATTERY_EXHAUSTED at {pos[0]:.2f},{pos[1]:.2f}"
                else:
                    self.destroy_reason = "BATTERY_EXHAUSTED"
                self.destroy_tick = getattr(self.model, "tick_count", None)
            self.status = "GROUNDED"
            self.is_destroyed = True
            pos = getattr(self, "pos", None)
            pos_txt = f" at {pos[0]:.2f},{pos[1]:.2f}" if pos else ""
            self.model.log_action(self.unique_id, f"DRONE LOST: battery exhausted{pos_txt}.")

    def move(self, dx: float, dy: float, dz: float = 0.0):
        """Move by a 3D delta vector clamped to exactly 1.0 unit magnitude (Z handled independently)."""
        if self.is_destroyed:
            return
        mag = math.sqrt(dx * dx + dy * dy + dz * dz)
        if mag == 0:
            return
        if mag > 1.0:
            dx, dy, dz = dx / mag, dy / mag, dz / mag   # normalise to unit vector

        nx = max(0.0, min(19.99, self.pos[0] + dx))
        ny = max(0.0, min(19.99, self.pos[1] + dy))
        self.model.space.move_agent(self, (nx, ny))
        self.z = max(0.2, min(6.0, self.z + dz))
        self.battery -= 3 if dz > 0 else 2


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
        self.bases = map_data.get("bases", [{"x": 9, "y": 9}])

        def terrain_height(kind: str, ix: int, iy: int, provided: float | None) -> float:
            if provided is not None:
                try:
                    return float(provided)
                except Exception:
                    pass
            seed = (ix * 73856093) ^ (iy * 19349663) ^ (0xB11D if kind == "building" else 0x0B57)
            rng = random.Random(seed)
            if kind == "building":
                return round(rng.uniform(1.2, 3.8), 2)
            return round(rng.uniform(0.6, 2.6), 2)

        for c in obstacles:
            ix, iy = int(c["x"]), int(c["y"])
            location = (ix + 0.5, iy + 0.5)
            h = terrain_height("obstacle", ix, iy, c.get("height"))
            agent = ObstacleAgent(f"obs_{ix}_{iy}", self, height=h)
            self.space.place_agent(agent, location)
            self.obstacle_map[(ix, iy)] = agent

        for b in buildings:
            ix, iy = int(b["x"]), int(b["y"])
            if (ix, iy) not in self.building_map:
                location = (ix + 0.5, iy + 0.5)
                h = terrain_height("building", ix, iy, b.get("height"))
                agent = BuildingAgent(f"bld_{ix}_{iy}", self, height=h)
                self.space.place_agent(agent, location)
                self.building_map[(ix, iy)] = agent

        # Precompute the building clusters
        clusters = cluster_tiles(list(self.building_map.keys()))
        for i, cluster in enumerate(clusters):
            cx = sum(t[0] for t in cluster) / len(cluster) + 0.5
            cy = sum(t[1] for t in cluster) / len(cluster) + 0.5
            self.building_clusters.append(BuildingCluster(f"cluster_{i}", cx, cy, cluster))

        # ── Place drones at bases ──────────────────────────
        base = {"x": 9, "y": 9}
        for i in range(config.get("num_drones", 5)):
            drone = DroneAgent(f"drone_{i+1}", self, config.get("drone_battery", 100))
            self.space.place_agent(drone, (base["x"] + 0.5, base["y"] + 0.5))
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
            (d.unique_id, d.pos[0], d.pos[1], getattr(d, "z", 1.8), d.battery, d.status,
             int(d.is_destroyed), json.dumps(d.task_queue), 
             json.dumps(d.messages_for_commander), d.error_count, json.dumps(d.thermal_memory))
            for d in self.schedule.agents if isinstance(d, DroneAgent)
        ]
        obstacle_data = [
            (a.unique_id, a.pos[0], a.pos[1], float(getattr(a, "height", 1.2)), int(a.discovered))
            for a in self.obstacle_map.values()
        ]
        building_data = [
            (a.unique_id, a.pos[0], a.pos[1], float(getattr(a, "height", 1.6)), int(a.revealed))
            for a in self.building_map.values()
        ]
        survivor_data = []
        for agent in self.schedule.agents:
            if isinstance(agent, SurvivorAgent):
                survivor_data.append(
                    (agent.unique_id, agent.pos[0], agent.pos[1], int(agent.found), agent.found_tick)
                )

        building_cluster_data = [
            (bc.id, bc.cx, bc.cy, int(bc.revealed), len(bc.tiles), bc.assigned_to)
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
          - drone.task_queue
        """
        conn = db.get_db_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id, status, task_queue FROM drones")
        for (drone_id, status, queue_json) in cursor.fetchall():
            for agent in self.schedule.agents:
                if isinstance(agent, DroneAgent) and agent.unique_id == drone_id:
                    agent.status = status
                    agent.task_queue = json.loads(queue_json) if queue_json else []
                    break
        conn.close()

    # ── Physics step ─────────────────────────────────────────────────────────

    def step(self, batch_intents=None):
        if self.mission_complete or self.mission_failed:
            return
        self.tick_count += 1

        # 1. Sync status / queues from DB (source of truth for agent decisions)
        conn = db.get_db_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id, status, task_queue, messages_for_commander, error_count, thermal_memory FROM drones")
        drone_rows = {r[0]: r for r in cursor.fetchall()}
        for agent in self.schedule.agents:
            if isinstance(agent, DroneAgent) and agent.unique_id in drone_rows:
                r = drone_rows[agent.unique_id]
                agent.status = r[1]
                agent.task_queue = json.loads(r[2]) if r[2] else []
                agent.messages_for_commander = json.loads(r[3]) if r[3] else []
                agent.error_count = r[4]
                agent.thermal_memory = json.loads(r[5]) if r[5] else []

        # 2. Sync building revealed from DB
        cursor.execute("SELECT id, revealed FROM buildings")
        for bld_id, rev in cursor.fetchall():
            # find building agent by id
            for a in self.building_map.values():
                if a.unique_id == bld_id:
                    a.revealed = bool(rev)

        # Sync assigned_to for building_clusters from DB
        cursor.execute("SELECT id, assigned_to FROM building_clusters")
        cluster_assignment = {r[0]: r[1] for r in cursor.fetchall()}
        for bc in self.building_clusters:
            if bc.id in cluster_assignment:
                bc.assigned_to = cluster_assignment[bc.id]

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

                self.step_logs.append({
                    "step": self.tick_count,
                    "drone_id": d_id,
                    "pos": drone.pos,
                    "status": drone.status,
                })

                if drone.status in ["SEARCHING", "RETURNING"]:
                    dx = float(intent.get("dx", 0.0))
                    dy = float(intent.get("dy", 0.0))
                    dz = float(intent.get("dz", 0.0))

                    if math.sqrt(dx * dx + dy * dy + dz * dz) > 0:
                        cruise_z = 1.1
                        clearance = 0.35
                        max_z = 6.0
                        # Tile-based Collision Check (Robust)
                        mag = math.sqrt(dx * dx + dy * dy + dz * dz)
                        if mag > 1.0:
                            dx, dy, dz = dx / mag, dy / mag, dz / mag

                        nx, ny = drone.pos[0] + dx, drone.pos[1] + dy
                        tx, ty = int(nx), int(ny)
                        # Check maps for any blocking agent in the target integer tile
                        collision_agent = self.obstacle_map.get((tx, ty)) or self.building_map.get((tx, ty))
                        
                        if collision_agent:
                            hit_height = float(getattr(collision_agent, "height", 1.2))
                            required_z = hit_height + clearance
                            if required_z > max_z:
                                drone.status = "CRASHED"
                                drone.is_destroyed = True
                                agent_type = "building" if isinstance(collision_agent, BuildingAgent) else "obstacle"
                                if not getattr(drone, "destroy_reason", None):
                                    drone.destroy_reason = f"ALTITUDE_LIMIT_EXCEEDED_OVER_{agent_type.upper()} ({tx},{ty})"
                                    drone.destroy_tick = self.tick_count
                                fx, fy = drone.pos[0], drone.pos[1]
                                self.log_action(
                                    d_id,
                                    f"DRONE LOST: cannot clear {agent_type} tile ({tx},{ty}) height={hit_height:.2f} with max_z={max_z:.2f}."
                                )
                            else:
                                current_z = float(getattr(drone, "z", cruise_z))
                                if current_z < required_z:
                                    drone.move(0.0, 0.0, required_z - current_z)
                                else:
                                    drone.move(dx, dy, dz)
                        else:
                            current_z = float(getattr(drone, "z", cruise_z))
                            if abs(dz) < 1e-6 and current_z > cruise_z + clearance:
                                dz = -min(0.5, current_z - cruise_z)
                            drone.move(dx, dy, dz)

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
                        db.increment_physical_visits(revealed_cells)

                    for obj in nearby:
                        if isinstance(obj, BuildingAgent):
                            obj.revealed = True
                            # Force coverage update for building location
                            db.increment_physical_visits([(int(obj.pos[0]*2), int(obj.pos[1]*2))])
                        elif isinstance(obj, ObstacleAgent):
                            obj.discovered = True
                            # Force coverage update for obstacle location
                            db.increment_physical_visits([(int(obj.pos[0]*2), int(obj.pos[1]*2))])
                        elif isinstance(obj, SurvivorAgent) and not obj.found:
                            obj.found = True
                            obj.found_tick = self.tick_count
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
        if any_destroyed and not self.mission_failed and not self.mission_complete:
            destroyed_drones = [
                a for a in self.schedule.agents
                if isinstance(a, DroneAgent) and getattr(a, "is_destroyed", False)
            ]
            lines = [
                f"MISSION FAILED (tick {self.tick_count}): drone lost. progress={self.found_survivors}/{self.total_survivors}"
            ]
            for d in destroyed_drones:
                pos = getattr(d, "pos", None)
                pos_txt = f"{pos[0]:.2f},{pos[1]:.2f}" if pos else "unknown"
                reason = getattr(d, "destroy_reason", None) or d.status
                dtick = getattr(d, "destroy_tick", None)
                dtick_txt = str(dtick) if dtick is not None else "unknown"
                battery = getattr(d, "battery", None)
                batt_txt = str(int(battery)) if isinstance(battery, (int, float)) else "unknown"

                last_evt = next((l for l in reversed(self.mission_logs) if l.get("drone_id") == d.unique_id), None)
                last_msg = last_evt.get("message") if isinstance(last_evt, dict) else None
                last_tick = last_evt.get("tick") if isinstance(last_evt, dict) else None

                if last_msg is not None and last_tick is not None:
                    lines.append(
                        f"- {d.unique_id}: status={d.status} battery={batt_txt} pos={pos_txt} destroy_tick={dtick_txt} reason={reason}\n  last_event(tick {last_tick}): {last_msg}"
                    )
                else:
                    lines.append(
                        f"- {d.unique_id}: status={d.status} battery={batt_txt} pos={pos_txt} destroy_tick={dtick_txt} reason={reason}"
                    )

            details = "\n".join(lines) if lines else f"MISSION FAILED (tick {self.tick_count}): unknown drone loss"
            self.mission_failed = True
            self.log_action("SYSTEM", details)
        elif self.total_survivors > 0 and self.found_survivors >= self.total_survivors and not self.mission_complete and not self.mission_failed:
            self.mission_complete = True
            self.log_action("SYSTEM", f"MISSION COMPLETE (tick {self.tick_count}): rescued {self.found_survivors}/{self.total_survivors} survivors.")

        self.sync_to_db()

        # --- NEW: 6. Log Telemetry for Post-Mission Report ---
        import time
        total_battery_capacity = 0
        current_battery = 0
        
        for a in self.schedule.agents:
            if isinstance(a, DroneAgent):
                # Assuming starting battery is 100
                total_battery_capacity += getattr(a, 'max_battery', 100) 
                current_battery += a.battery
                
        # Net battery used (charging will reduce this net amount, 
        # but it gives us a good proxy for overall energy expenditure)
        total_battery_consumed = total_battery_capacity - current_battery
        
        db.log_telemetry(self.tick_count, time.time(), total_battery_consumed)

sim_world = None

def initialize_world(config=None):
    global sim_world
    sim_world = DisasterZoneModel(config)
    return sim_world
