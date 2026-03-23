from mesa import Agent, Model
from mesa.space import MultiGrid
from mesa.time import RandomActivation
import sqlite3
import json
import os

DB_PATH = "live_state.db"

def init_db():
    if os.path.exists(DB_PATH):
        try: os.remove(DB_PATH)
        except: pass
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE drones (id TEXT PRIMARY KEY, x INTEGER, y INTEGER, battery INTEGER, status TEXT, is_destroyed INTEGER, thermal_memory TEXT, priority_list TEXT)")
    cursor.execute("CREATE TABLE cells (x INTEGER, y INTEGER, altitude REAL, building_height REAL, is_obstacle INTEGER, obstacle_discovered INTEGER, terrain_type TEXT, thermal_aura INTEGER, PRIMARY KEY(x,y))")
    cursor.execute("CREATE TABLE survivors (id TEXT PRIMARY KEY, x INTEGER, y INTEGER, found INTEGER)")
    cursor.execute("CREATE TABLE mission_state (id INTEGER PRIMARY KEY, tick_count INTEGER, complete INTEGER, failed INTEGER, total_survivors INTEGER, found_survivors INTEGER)")
    cursor.execute("INSERT INTO mission_state (id, tick_count, complete, failed, total_survivors, found_survivors) VALUES (1, 0, 0, 0, 0, 0)")
    conn.commit()
    conn.close()

class CellAgent(Agent):
    def __init__(self, unique_id, model, altitude, b_height, is_ob, t_type, is_thermal_aura = False):
        super().__init__(unique_id, model)
        self.altitude = altitude
        self.building_height = b_height
        self.is_obstacle = is_ob
        self.terrain_type = t_type
        self.obstacle_discovered = False
        self.thermal_aura = is_thermal_aura

class SurvivorAgent(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.found = False

class DroneAgent(Agent):
    def __init__(self, unique_id, model, battery):
        super().__init__(unique_id, model)
        self.battery = battery
        self.status = "SEARCHING"
        self.priority_searching_list = []
        self.thermal_memory = []
        self.is_destroyed = False

    def step(self):
        if self.is_destroyed: return
        if self.status == "CHARGING":
            self.battery = min(100, self.battery + 2)
            if self.pos != (9, 9): self.model.grid.move_agent(self, (9, 9))
        if self.battery <= 0 and self.status != "CHARGING":
            self.status = "GROUNDED"
            self.is_destroyed = True
            self.model.log_action(self.unique_id, "Battery exhausted.")

    def move(self, new_position):
        if self.is_destroyed: return
        self.model.grid.move_agent(self, new_position)
        self.battery -= 2

class DisasterZoneModel(Model):
    def __init__(self, config=None):
        super().__init__()
        init_db()
        self.width = 20
        self.height = 20
        self.tick_count = 0
        self.mission_complete = False
        self.mission_failed = False
        self.global_discovered_cells = set()
        self.mission_logs = []
        self.total_survivors = 0
        self.found_survivors = 0
        
        self.grid = MultiGrid(self.width, self.height, torus=False)
        self.schedule = RandomActivation(self)

        map_data = config.get("map_data", {})
        cells = map_data.get("cells", [])
        survivors = map_data.get("blueprint", {}).get("survivors", [])

        for c in cells:
            cell = CellAgent(f"c_{c['x']}_{c['y']}", self, c['altitude'], c.get('building_height', 0), c['is_obstacle'], c['terrain_type'])
            self.grid.place_agent(cell, (c['x'], c['y']))

        for i in range(config.get("num_drones", 3)):
            drone = DroneAgent(f"drone_{i+1}", self, config.get("drone_battery", 100))
            self.grid.place_agent(drone, (9, 9))
            self.schedule.add(drone)

        for s in survivors:
            x, y = s.get("x", 0), s.get("y", 0)
            survivor = SurvivorAgent(f"s_{self.total_survivors}", self)
            self.grid.place_agent(survivor, (x, y))
            self.total_survivors += 1
            for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                nx, ny = x+dx, y+dy
                if 0 <= nx < 20 and 0 <= ny < 20:
                    for obj in self.grid.get_cell_list_contents([(nx, ny)]):
                        if isinstance(obj, CellAgent): obj.thermal_aura = True
        
        self.sync_to_db()

    def sync_to_db(self):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # Sync Drones
        for a in self.schedule.agents:
            if isinstance(a, DroneAgent):
                cursor.execute("INSERT OR REPLACE INTO drones VALUES (?,?,?,?,?,?,?,?)", 
                    (a.unique_id, a.pos[0], a.pos[1], a.battery, a.status, int(a.is_destroyed), json.dumps(a.thermal_memory), json.dumps(a.priority_searching_list)))
        # Sync Cells (Selective update for discovery)
        for contents, (x, y) in self.grid.coord_iter():
            for obj in contents:
                if isinstance(obj, CellAgent):
                    cursor.execute("INSERT OR REPLACE INTO cells VALUES (?,?,?,?,?,?,?,?)",
                        (x, y, obj.altitude, obj.building_height, int(obj.is_obstacle), int(obj.obstacle_discovered), obj.terrain_type, int(obj.thermal_aura)))
        # Sync Survivors
        for contents, (x, y) in self.grid.coord_iter():
            for obj in contents:
                if isinstance(obj, SurvivorAgent):
                    cursor.execute("INSERT OR REPLACE INTO survivors VALUES (?,?,?,?)", (obj.unique_id, x, y, int(obj.found)))
        # Sync Mission State
        cursor.execute("UPDATE mission_state SET tick_count=?, complete=?, failed=?, total_survivors=?, found_survivors=? WHERE id=1",
            (self.tick_count, int(self.mission_complete), int(self.mission_failed), self.total_survivors, self.found_survivors))
        conn.commit()
        conn.close()

    def log_action(self, d_id, msg):
        self.mission_logs.append({"drone_id": d_id, "message": msg, "tick": self.tick_count})

    def step(self, batch_intents=None):
        if self.mission_complete or self.mission_failed: return
        self.tick_count += 1
        
        # Apply intents from database (The MCP tools write back to lists, we must read them)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        for a in self.schedule.agents:
            if isinstance(a, DroneAgent):
                cursor.execute("SELECT priority_list, thermal_memory FROM drones WHERE id=?", (a.unique_id,))
                row = cursor.fetchone()
                if row:
                    a.priority_searching_list = json.loads(row[0])
                    a.thermal_memory = json.loads(row[1])
        conn.close()

        if batch_intents:
            for d_id, intent in batch_intents.items():
                drone = next((a for a in self.schedule.agents if a.unique_id == d_id), None)
                if not drone or drone.is_destroyed: continue
                drone.status = intent.get("status", drone.status)
                if intent.get("action") == "move":
                    tx, ty = intent.get("x"), intent.get("y")
                    crash = any(isinstance(o, CellAgent) and o.is_obstacle for o in self.grid.get_cell_list_contents([(tx, ty)]))
                    if crash:
                        drone.status = "CRASHED"; drone.is_destroyed = True
                        self.log_action(d_id, "Fatal crash!")
                    else:
                        drone.move((tx, ty))
                        for o in self.grid.get_cell_list_contents([(tx, ty)]):
                            if isinstance(o, SurvivorAgent) and not o.found:
                                o.found = True; self.found_survivors += 1
                                self.log_action(d_id, "Survivor found!")

        self.schedule.step()
        
        destroyed = next((d for d in self.schedule.agents if getattr(d, "is_destroyed", False)), None)
        if destroyed: self.mission_failed = True
        if self.total_survivors > 0 and self.found_survivors >= self.total_survivors: self.mission_complete = True
        
        self.sync_to_db()

sim_world = None
def initialize_world(config=None):
    global sim_world
    sim_world = DisasterZoneModel(config)
    return sim_world
