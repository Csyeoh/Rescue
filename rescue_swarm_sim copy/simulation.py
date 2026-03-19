from mesa import Agent, Model
from mesa.space import MultiGrid
from mesa.time import RandomActivation
import database
import sqlite3
import random
import time
import threading
import map_generator

class TerrainAgent(Agent):
    def __init__(self, custom_id, model, altitude=0.0, is_obstacle=False, terrain_type="terrain"):
        super().__init__(custom_id, model)
        self.custom_id = custom_id
        self.altitude = altitude
        self.is_obstacle = is_obstacle
        self.terrain_type = terrain_type 
        self.obstacle_discovered = False 

    def step(self):
        pass

class DroneAgent(Agent):
    def __init__(self, custom_id, model, initial_battery=100):
        super().__init__(custom_id, model)
        self.custom_id = custom_id 
        self.battery = initial_battery

    def attempt_move(self, new_x, new_y):
        # We leave this alone, MCP handles the movement logic directly in the DB now!
        pass

class DisasterZoneModel(Model):
    def __init__(self, config=None):
        super().__init__()
        if config is None: config = {}

        self.width = 20
        self.height = 20
        self.tick_count = 0 # NEW: Tracker for the 10-second weather changes
        
        obstacle_diff = config.get("obstacle_difficulty", "med")
        self.sim_diff = config.get("sim_difficulty", "easy")
        num_survivors = config.get("num_survivors", 5)
        num_drones = config.get("num_drones", 2)
        start_battery = config.get("drone_battery", 100)

        self.grid = MultiGrid(self.width, self.height, torus=False)
        self.schedule = RandomActivation(self)
        self._clear_old_mission_data()

        if obstacle_diff == "high": obstacle_prob = 0.25
        elif obstacle_diff == "low": obstacle_prob = 0.05
        else: obstacle_prob = 0.15

        map_data = config.get("map_data")
        if map_data:
            cells = map_data.get("cells", [])
            blueprint_dict = map_data.get("blueprint", {})
            ai_survivors = blueprint_dict.get("survivors", [])
        else:
            # Fallback to generating on the fly
            scenario_prompt = config.get("scenario", "")
            if not scenario_prompt:
                themes = [
                    "A dense downtown commercial district.",
                    "A tight-knit suburban neighborhood clustered in a valley.",
                    "An industrial warehouse district with large number of buildings grouped together.",
                    "A coastal urban center with dense housing",
                    "A mixed urban layout with clusters of residential buildings."
                ]
                scenario_prompt = random.choice(themes)
                
            blueprint = map_generator.generate_semantic_blueprint(scenario_prompt, num_survivors)
            cells = map_generator.build_terrain_matrix(blueprint, obstacle_prob, self.width, self.height)
            ai_survivors = [{"x": s.x, "y": s.y} for s in blueprint.survivors] if blueprint else []

        # Build the grid using the cells
        terrain_id = 0
        
        for cell_data in cells:
            x, y = cell_data["x"], cell_data["y"]
            altitude = cell_data["altitude"]
            is_ob = cell_data["is_obstacle"]
            t_type = cell_data["terrain_type"]

            cell = TerrainAgent(f"terrain_{terrain_id}", self, altitude, is_ob, t_type)
            self.grid.place_agent(cell, (x, y))
            self.schedule.add(cell)
            terrain_id += 1

        for i in range(num_drones):
            self.spawn_drone(f"drone_{i+1}", 9, 9, start_battery)

        self.spawn_ai_survivors(ai_survivors, num_survivors)
        self.sync_terrain_to_db()

    def _clear_old_mission_data(self):
        conn = sqlite3.connect(database.DB_NAME, timeout=10.0)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM question_plane")
        cursor.execute("DELETE FROM answer_plane")
        cursor.execute("DELETE FROM drones")
        cursor.execute("DELETE FROM survivors")
        cursor.execute("DELETE FROM logs")
        cursor.execute("DELETE FROM drone_zones")
        cursor.execute("DELETE FROM drone_waypoints")
        cursor.execute("DELETE FROM cell_weights")
        conn.commit()
        conn.close()

    def spawn_drone(self, custom_id, start_x, start_y, battery):
        drone = DroneAgent(custom_id, self, battery)
        self.grid.place_agent(drone, (start_x, start_y))
        self.schedule.add(drone)
        
        conn = sqlite3.connect(database.DB_NAME, timeout=10.0)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO drones (drone_id, x, y, battery, is_active, health_status) VALUES (?, ?, ?, ?, 1, 'OPTIMAL')", 
                       (custom_id, start_x, start_y, battery))
        conn.commit()
        conn.close()

    def spawn_ai_survivors(self, ai_survivors, fallback_count):
        conn = sqlite3.connect(database.DB_NAME, timeout=10.0)
        cursor = conn.cursor()
        
        spawned = 0
        used_coords = set([(9, 9)]) 
        
        for s in ai_survivors:
            x, y = s.get("x", 0), s.get("y", 0)
            
            if not (0 <= x < 20 and 0 <= y < 20) or (x, y) in used_coords:
                continue
                
            used_coords.add((x, y))
            cursor.execute("INSERT OR IGNORE INTO survivors (survivor_id, x, y, is_discovered) VALUES (?, ?, ?, ?)",
                           (f"survivor_{spawned+1}", x, y, False))
            spawned += 1
            
        while spawned < fallback_count:
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            if (x, y) not in used_coords:
                used_coords.add((x, y))
                cursor.execute("INSERT OR IGNORE INTO survivors (survivor_id, x, y, is_discovered) VALUES (?, ?, ?, ?)",
                               (f"survivor_{spawned+1}", x, y, False))
                spawned += 1
            
        conn.commit()
        conn.close()

    def sync_terrain_to_db(self):
        terrain_data = []
        for agent in self.schedule.agents:
            if isinstance(agent, TerrainAgent):
                terrain_data.append((
                    agent.pos[0], agent.pos[1], agent.altitude, 
                    agent.is_obstacle, agent.terrain_type, agent.obstacle_discovered 
                ))
        database.sync_terrain(terrain_data)

    def step(self):
        """Advances the physics simulation by 1 tick (1 second)."""
        
        # 1. CHECK WIN CONDITION
        conn = sqlite3.connect(database.DB_NAME, timeout=10.0)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*), SUM(is_discovered) FROM survivors")
        row = cursor.fetchone()
        conn.close()

        if row:
            total_survivors = row[0]
            found_survivors = row[1] if row[1] is not None else 0
            
            # If everyone is found, freeze the simulation!
            if total_survivors > 0 and total_survivors == found_survivors:
                # We only want to log this once!
                if not getattr(self, "mission_complete", False):
                    self.mission_complete = True
                    database.log_action("SYSTEM", "🎉 MISSION ACCOMPLISHED! All survivors rescued. Physics engine frozen.")
                return # Abort the rest of the step! No more water rising!

        # 2. NORMAL PHYSICS TICK (Only runs if mission is NOT complete)
        self.tick_count += 1
        self.schedule.step() 
        self.sync_terrain_to_db()

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