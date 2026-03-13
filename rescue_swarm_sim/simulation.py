from mesa import Agent, Model
from mesa.space import MultiGrid
from mesa.time import RandomActivation
import database
import sqlite3
import random
import math 
import time
import threading # NEW: For the live simulation heartbeat
import world_builder

class TerrainAgent(Agent):
    def __init__(self, custom_id, model, altitude=0.0, is_obstacle=False, terrain_type="terrain"):
        super().__init__(custom_id, model)
        self.custom_id = custom_id
        self.altitude = altitude
        self.is_obstacle = is_obstacle
        self.terrain_type = terrain_type 
        self.obstacle_discovered = False 
        self.local_water_level = 0.0

    def step(self):
        # Calculates how deep the water is on THIS specific grid square
        raw_water = self.model.global_water_level - self.altitude
        self.local_water_level = max(0.0, raw_water)

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

        # Grab the flood type from the config
        self.flood_type = config.get("flood_type", "Flash Flood")

        # ==========================================
        # 🧠 AUTO-GENERATE SCENARIO FOR GEMINI
        # ==========================================
        scenario_prompt = config.get("scenario")
        if not scenario_prompt:
            themes = [
                "A dense downtown commercial district.",
                "A quiet suburban neighborhood in a valley.",
                "A mountainous rural village with steep hills.",
                "An industrial warehouse district.",
                "A coastal town hit by a massive tsunami.",
                "A forested camp ground hit by slow, heavy rain."
            ]
            scenario_prompt = random.choice(themes)
            
        print(f"Asking Gemini to design: {scenario_prompt} | Type: {self.flood_type}")
        # Pass the flood_type to the AI!
        blueprint = world_builder.generate_disaster_blueprint(scenario_prompt, num_survivors, self.flood_type)
        
        if not blueprint:
             blueprint = {
                 "initial_water_level": 0.5, "initial_water_speed": 0.2,
                 "hills": [{"x":15, "y":15, "peak_altitude":8.0, "spread":1.5}], 
                 "city_centers": [{"x":5, "y":5}], "survivors": []
             }
             print("AI failed, falling back to default.")

        # NEW: Pull dynamic weather settings from Gemini!
        self.global_water_level = blueprint.get("initial_water_level", 0.5)
        self.water_speed = blueprint.get("initial_water_speed", 0.2)

        database.log_action("SYSTEM", f"SCENARIO INITIALIZED. Starting Water Level: {self.global_water_level:.2f}m")

        hills = blueprint.get("hills", [])
        city_centers = [(c["x"], c["y"]) for c in blueprint.get("city_centers", [])]
        ai_survivors = blueprint.get("survivors", [])

        # Build the grid using the AI blueprint rules
        terrain_id = 0
        for x in range(self.width):
            for y in range(self.height):
                
                # Base Camp is now an indestructible 150m high platform
                if x == 9 and y == 9:
                    altitude = 150.0
                    is_ob = False
                    t_type = "terrain"
                else:
                    altitude = 1.0 
                    for hill in hills:
                        hx, hy = hill.get("x", 10), hill.get("y", 10)
                        h_max = hill.get("peak_altitude", 40.0) # Hills are much taller
                        h_spread = hill.get("spread", 1.5)
                        
                        dist = math.sqrt((x - hx)**2 + (y - hy)**2)
                        hill_height = h_max - (dist * h_spread)
                        if hill_height > altitude:
                            altitude = hill_height
                            
                    altitude += random.uniform(-0.5, 0.5)
                    altitude = max(1.0, altitude) 
                    
                    closest_city = min([math.sqrt((x - cx)**2 + (y - cy)**2) for cx, cy in city_centers]) if city_centers else 10
                    
                    t_type = "terrain"
                    if closest_city < 5.0 and altitude < 20.0:
                        if random.random() < 0.75:
                            t_type = "building"
                            # Skyscrapers in the city! (20m to 80m tall)
                            altitude += random.uniform(20.0, 80.0) 
                    else:
                        if random.random() < 0.05 and altitude < 30.0:
                            t_type = "building"
                            # Suburban/Rural buildings (5m to 20m tall)
                            altitude += random.uniform(5.0, 20.0)

                    is_ob = random.random() < obstacle_prob 

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
        cursor.execute("DELETE FROM grid")
        cursor.execute("DELETE FROM drones")
        cursor.execute("DELETE FROM survivors")
        cursor.execute("DELETE FROM logs")
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
        
        # NEW: The water only physically rises once every 5 seconds
        if self.tick_count % 5 == 0:
            self.global_water_level += self.water_speed
        
        # EVERY 10 SECONDS: Proportional weather shift!
        if self.tick_count % 10 == 0:
            multiplier = random.uniform(0.9, 1.3) 
            self.water_speed = self.water_speed * multiplier
            self.water_speed = min(0.15, self.water_speed) 
            
            database.log_action("SYSTEM", f"WEATHER ALERT: {self.flood_type} intensity shifted. New speed: {self.water_speed:.4f}m/tick")

        self.schedule.step() 
        database.update_environment(self.global_water_level, self.water_speed)
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

def initialize_world(config=None):
    global sim_world, sim_running
    
    sim_world = DisasterZoneModel(config)
    
    # Start the heartbeat thread if it isn't running already
    if not sim_running:
        sim_running = True
        t = threading.Thread(target=_run_sim_loop, daemon=True)
        t.start()
        
    return sim_world