from mesa import Agent, Model
from mesa.space import MultiGrid
from mesa.time import RandomActivation
import time
import threading

class CellAgent(Agent):
    """A static agent representing the terrain/building properties of a cell."""
    def __init__(self, unique_id, model, altitude, b_height, is_ob, t_type, is_termal_aura = False):
        super().__init__(unique_id, model)
        # self.pos is set by the grid.place_agent call
        self.altitude = altitude
        self.building_height = b_height
        self.is_obstacle = is_ob
        self.terrain_type = t_type
        self.obstacle_discovered = False
        self.assigned_drone = None
        self.thermal_aura = is_termal_aura

class SurvivorAgent(Agent):
    """A static agent representing a survivor to be found."""
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        # self.pos is set by the grid.place_agent call
        self.found = False

class DroneAgent(Agent):
    """A dynamic agent that moves and consumes battery."""
    def __init__(self, unique_id, model, battery):
        super().__init__(unique_id, model)
        self.battery = battery
        self.status = "SEARCHING" # IDLE, SEARCHING, RETURNING, CHARGING
        self.priority_searching_list = []
        self.thermal_memory = []
        # Intent & history tracking (populated each tick by the flow)
        self.pending_move: tuple | None = None   # (x, y) requested by LLM this tick
        self.move_history: list = []             # [(tick, from_x, from_y, to_x, to_y), ...]
        self.last_action: str = ""               # Last resolved action string
        self.last_rationale: str = ""            # Last LLM rationale

    def _apply_move(self, new_position):
        """Internal: physically moves the drone and drains battery. Called by resolve_intent only."""
        self.model.grid.move_agent(self, new_position)
        self.battery -= 1  # 1% per move rule


class DisasterZoneModel(Model):
    def __init__(self, config=None):
        super().__init__()

        self.width = 20
        self.height = 20
        self.tick_count = 0
        num_drones = config.get("num_drones", 2)
        start_battery = config.get("drone_battery", 100)

        self.grid = MultiGrid(self.width, self.height, torus=False)
        self.schedule = RandomActivation(self)
        self.mission_logs = []
        self.global_discovered_cells = set() # Global memory
        self._clear_old_mission_data()
        
        self.total_survivors = 0
        self.found_survivors = 0


        map_data = config.get("map_data")
        if map_data:
            cells = map_data.get("cells", [])
            blueprint_dict = map_data.get("blueprint", {})
            survivors = blueprint_dict.get("survivors", [])
        else:
            print("ERROR: No map data provided. The simulator cannot start without a valid map.")
            return

        # Build the grid using the cells
        terrain_id = 0
        
        for cell_data in cells:
            x, y = cell_data["x"], cell_data["y"]
            altitude = cell_data["altitude"]
            building_height = cell_data.get("building_height", 0.0)
            is_ob = cell_data["is_obstacle"]
            t_type = cell_data["terrain_type"]

            cell = CellAgent(f"terrain_{terrain_id}", self, altitude, building_height, is_ob, t_type)
            self.grid.place_agent(cell, (x, y))
            terrain_id += 1

        for i in range(num_drones):
            self.spawn_drone(f"drone_{i+1}", 9, 9, start_battery)

        self.spawn_survivors(survivors)
        # self.sync_to_db()

    def log_action(self, drone_id: str, message: str):
        self.mission_logs.append({"drone_id": drone_id, "message": message, "tick": self.tick_count})
        print(f"[SIM TICK {self.tick_count}] {drone_id}: {message}")

    def _clear_old_mission_data(self):
        # Deprecated logic since DB is removed.
        pass

    def spawn_drone(self, custom_id, start_x, start_y, battery):
        drone = DroneAgent(custom_id, self, battery)
        self.grid.place_agent(drone, (start_x, start_y))
        self.schedule.add(drone)

    def spawn_survivors(self, survivors):
        spawned = 0        
        for s in survivors:
            x, y = s.get("x", 0), s.get("y", 0)
            # Create SurvivorAgent and place on grid
            survivor = SurvivorAgent(f"survivor_{spawned+1}", self)
            self.grid.place_agent(survivor, (x, y))
            for dx, dy in [(1,0), (0, 1), (-1, 0), (0, -1)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.grid.width and 0 <= ny < self.grid.height:
                    for obj in self.grid.get_cell_list_contents([(nx, ny)]):
                        if isinstance(obj, CellAgent):
                            obj.thermal_aura = True
            spawned += 1
            
        self.total_survivors = spawned

    def sync_to_db(self):
        """Deprecated."""
        pass

    def step(self):
        """Advances the physics simulation by 1 tick (1 second)."""    
        found = 0
        from simulation import SurvivorAgent
        for contents, (x, y) in self.grid.coord_iter():
            for obj in contents:
                if isinstance(obj, SurvivorAgent) and obj.found:
                    found += 1
                    
        self.found_survivors = found

        # If everyone is found, freeze the simulation!
        if self.total_survivors > 0 and self.total_survivors == self.found_survivors:
            # We only want to log this once!
            if not getattr(self, "mission_complete", False):
                self.mission_complete = True
                self.log_action("SYSTEM", "🎉 MISSION ACCOMPLISHED! All survivors rescued. Physics engine frozen.")
            return 
        # 2. NORMAL PHYSICS TICK (Only runs if mission is NOT complete)
        self.tick_count += 1
        self.schedule.step()

# ==========================================
# 🎯 INTENT RESOLVER
# ==========================================

def resolve_intent(world: "DisasterZoneModel", intent: dict) -> dict:
    """
    Atomically applies one DroneIntent dict to the Mesa environment.

    Returns a map_update dict with only the cells that changed this tick,
    plus the drone's new position and battery — ready for WS broadcast.
    """
    from simulation import DroneAgent, CellAgent, SurvivorAgent

    result = {
        "drone_id": intent.get("drone_id"),
        "action": intent.get("action", "IDLE"),
        "from": None,
        "to": None,
        "battery": None,
        "new_status": intent.get("new_status"),
        "map_updates": [],
        "events": [],
    }

    if not world:
        result["events"].append("ERROR: no simulation world")
        return result

    drone = None
    for agent in world.schedule.agents:
        if isinstance(agent, DroneAgent) and agent.unique_id == intent.get("drone_id"):
            drone = agent
            break

    if not drone:
        result["events"].append(f"ERROR: drone {intent.get('drone_id')} not found")
        return result

    action = intent.get("action", "IDLE")
    drone.last_action = action
    drone.last_rationale = intent.get("rationale", "")

    # Apply status change if requested
    new_status = intent.get("new_status")
    if new_status and new_status in ("SEARCHING", "CHARGING", "RETURNING", "IDLE"):
        drone.status = new_status

    # Clear any pending move regardless
    drone.pending_move = None

    if action == "MOVE":
        tx, ty = intent.get("target_x"), intent.get("target_y")
        if tx is None or ty is None:
            result["events"].append("ERROR: MOVE action missing target_x/target_y")
            return result

        if not (0 <= tx < world.width and 0 <= ty < world.height):
            result["events"].append(f"ERROR: target ({tx},{ty}) out of bounds")
            return result

        if drone.battery < 2:
            result["events"].append(f"GROUNDED: {drone.unique_id} battery too low")
            return result

        # Check obstacle
        for obj in world.grid.get_cell_list_contents([(tx, ty)]):
            if isinstance(obj, CellAgent) and getattr(obj, "is_obstacle", False):
                obj.obstacle_discovered = True
                result["map_updates"].append({"x": tx, "y": ty, "obstacle_discovered": True})
                result["events"].append(f"BLOCKED: ({tx},{ty}) is an obstacle")
                return result

        from_pos = drone.pos
        result["from"] = {"x": from_pos[0], "y": from_pos[1]} if from_pos else None

        drone._apply_move((tx, ty))
        drone.move_history.append((world.tick_count, from_pos[0] if from_pos else 9, from_pos[1] if from_pos else 9, tx, ty))

        result["to"] = {"x": tx, "y": ty}
        result["battery"] = drone.battery

        # Base camp auto-recharge
        if tx == 9 and ty == 9:
            drone.battery = 100
            drone.status = "CHARGING"
            result["battery"] = drone.battery
            result["new_status"] = "CHARGING"
            result["events"].append("Returned to base. Recharging to 100%.")

        # Passive sensors — only report NEW discoveries
        adjacent = [(tx, ty-1), (tx, ty+1), (tx-1, ty), (tx+1, ty)]
        for ax, ay in adjacent:
            if 0 <= ax < world.width and 0 <= ay < world.height:
                contents = world.grid.get_cell_list_contents([(ax, ay)])
                for obj in contents:
                    if isinstance(obj, CellAgent) and obj.is_obstacle and not obj.obstacle_discovered:
                        obj.obstacle_discovered = True
                        result["map_updates"].append({"x": ax, "y": ay, "obstacle_discovered": True})
                    if getattr(obj, "thermal_aura", False):
                        sv_at = world.grid.get_cell_list_contents([(ax, ay)])
                        already_found = any(isinstance(s, SurvivorAgent) and s.found for s in sv_at)
                        if not already_found and (ax, ay) not in drone.thermal_memory:
                            drone.thermal_memory.append((ax, ay))
                            result["events"].append(f"THERMAL ALERT at ({ax},{ay}) added to memory")

        world.log_action(drone.unique_id, f"Moved from {from_pos} to ({tx},{ty}). Battery: {drone.battery}%")
        
        # Auto-discover current cell on arrival to keep search logic efficient
        world.global_discovered_cells.add((tx, ty))
        result["map_updates"].append({"x": tx, "y": ty, "discovered": True})

    elif action == "THERMAL_SCAN":
        if not drone.pos:
            result["events"].append("ERROR: drone has no position")
            return result
        dx, dy = drone.pos
        contents = world.grid.get_cell_list_contents([(dx, dy)])
        for obj in contents:
            if isinstance(obj, SurvivorAgent) and not obj.found:
                obj.found = True
                world.found_survivors += 1
                result["events"].append(f"SURVIVOR FOUND: {obj.unique_id} at ({dx},{dy})")
                result["map_updates"].append({"x": dx, "y": dy, "survivor_found": True, "survivor_id": obj.unique_id})
                world.log_action(drone.unique_id, f"Thermal scan MATCH: {obj.unique_id} rescued at ({dx},{dy})!")
                if world.total_survivors > 0 and world.found_survivors == world.total_survivors:
                    if not getattr(world, "mission_complete", False):
                        world.mission_complete = True
                        world.log_action("SYSTEM", "🎉 MISSION ACCOMPLISHED! All survivors rescued.")
                break
        else:
            result["events"].append(f"Scan complete at ({dx},{dy}): no survivor found")
        # Mark discovered
        world.global_discovered_cells.add((dx, dy))
        result["map_updates"].append({"x": dx, "y": dy, "discovered": True})

    elif action == "CONTINUE_CHARGING":
        result["events"].append(f"{drone.unique_id} continues charging at base.")

    elif action == "RETURN_TO_BASE":
        drone.status = "RETURNING"
        result["new_status"] = "RETURNING"
        result["events"].append(f"{drone.unique_id} set to RETURNING — will navigate base next tick.")

    elif action == "IDLE":
        result["events"].append(f"{drone.unique_id} is IDLE this tick.")

    return result


# ==========================================
# ⏱️ BACKGROUND HEARTBEAT THREAD
# ==========================================
sim_world = None
sim_running = False

def _run_sim_loop():
    """Continuously triggers the physics engine 1 time per second."""
    global sim_world, sim_running
    while sim_running:
        if sim_world:
            sim_world.step()
        time.sleep(1.0) # Tick every 1 second

def initialize_world(config=None, start_sim=True):
    global sim_world
    
    sim_world = DisasterZoneModel(config)
    
    # Start the heartbeat thread if requested
    if start_sim:
        start_sim_thread()
        
    return sim_world

def start_sim_thread():
    global sim_running
    if not sim_running:
        sim_running = True
        t = threading.Thread(target=_run_sim_loop, daemon=True)
        t.start()