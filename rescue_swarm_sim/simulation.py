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

    def move(self, new_position):
        # This will be called by your Flow/MCP Tool logic
        self.model.grid.move_agent(self, new_position)
        self.battery -= 1 # 1% per move rule


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