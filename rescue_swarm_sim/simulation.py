from mesa import Agent, Model
from mesa.space import MultiGrid
from mesa.time import RandomActivation
import json
import sys
import db

DB_PATH = "live_state.db"

class CellAgent(Agent):
    def __init__(self, unique_id, model, is_ob, t_type, is_thermal_aura = False):
        super().__init__(unique_id, model)
        self.is_obstacle = is_ob
        self.terrain_type = t_type
        self.obstacle_discovered = False
        self.thermal_aura = is_thermal_aura
        self.revealed = False
        self.assigned_to = None

class SurvivorAgent(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.found = False

class DroneAgent(Agent):
    def __init__(self, unique_id, model, battery):
        super().__init__(unique_id, model)
        self.battery = battery
        self.status = "IDLE"
        self.assigned_cells = None
        self.thermal_memory = []
        self.is_destroyed = False

    def step(self):
        if self.is_destroyed: return
        if self.status == "CHARGING":
            self.battery = min(100, self.battery + 2)
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
        db.init_db()
        self.width = 20
        self.height = 20
        self.tick_count = 0
        self.mission_complete = False
        self.mission_failed = False
        self.global_discovered_cells = set()
        self.mission_logs = []
        self.step_logs = []
        self.total_survivors = 0
        self.found_survivors = 0
        
        self.grid = MultiGrid(self.width, self.height, torus=False)
        self.schedule = RandomActivation(self)

        map_data = config.get("map_data", {})
        cells = map_data.get("cells", [])
        survivors = map_data.get("blueprint", {}).get("survivors", [])

        for c in cells:
            cell = CellAgent(f"c_{c['x']}_{c['y']}", self, c['is_obstacle'], c['terrain_type'])
            if c['x'] == 9 and c['y'] == 9: cell.revealed = True
            self.grid.place_agent(cell, (c['x'], c['y']))

        for i in range(config.get("num_drones", 3)):
            drone = DroneAgent(f"drone_{i+1}", self, config.get("drone_battery", 100))
            self.grid.place_agent(drone, (9, 9))
            self.schedule.add(drone)

        for s in survivors:
            x, y = s.get("x", 0), s.get("y", 0)
            if x == 9 and y == 9: continue # FAIL-SAFE: No survivors at the base
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
        import time
        t0 = time.time()
        
        drone_data = []
        for a in self.schedule.agents:
            if isinstance(a, DroneAgent):
                drone_data.append((a.unique_id, a.pos[0], a.pos[1], a.battery, a.status, int(a.is_destroyed), json.dumps(a.thermal_memory), json.dumps(a.assigned_cells)))
                
        cell_data = []
        survivor_data = []
        for contents, (x, y) in self.grid.coord_iter():
            for obj in contents:
                if isinstance(obj, CellAgent):
                    cell_data.append((x, y, int(obj.is_obstacle), int(obj.obstacle_discovered), obj.terrain_type, int(obj.thermal_aura), int(obj.revealed), obj.assigned_to))
                elif isinstance(obj, SurvivorAgent):
                    survivor_data.append((obj.unique_id, x, y, int(obj.found)))
                    
        mission_data = (self.tick_count, int(self.mission_complete), int(self.mission_failed), self.total_survivors, self.found_survivors)
        
        db.sync_world_state(drone_data, cell_data, survivor_data, mission_data)
        
        t1 = time.time()

    def log_action(self, d_id, msg):
        print(f"Logging action - Drone: {d_id}, Msg: {msg}, Tick: {self.tick_count}")
        self.mission_logs.append({"drone_id": d_id, "message": msg, "tick": self.tick_count})

    def update_thermal_auras(self):
        """Recalculates thermal auras based on unfound survivors."""
        # Reset all cells
        for contents, (x, y) in self.grid.coord_iter():
            for obj in contents:
                if isinstance(obj, CellAgent): obj.thermal_aura = False
        
        # Re-apply auras for unfound survivors
        for contents, (x, y) in self.grid.coord_iter():
            for obj in contents:
                if isinstance(obj, SurvivorAgent) and not obj.found:
                    for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                        nx, ny = x+dx, y+dy
                        if 0 <= nx < 20 and 0 <= ny < 20:
                            for c_obj in self.grid.get_cell_list_contents([(nx, ny)]):
                                if isinstance(c_obj, CellAgent): c_obj.thermal_aura = True

    def step(self, batch_intents=None):
        if self.mission_complete or self.mission_failed: return
        self.tick_count += 1
        
        # 1. Synchronize in-memory state from DB (Source of Truth for Agent/Dispatcher actions)
        conn = db.get_db_conn()
        cursor = conn.cursor()
        
        # Update Drones (including status which was missing before)
        cursor.execute("SELECT id, status, assigned_cells, thermal_memory FROM drones")
        drone_rows = {r[0]: r for r in cursor.fetchall()}
        for a in self.schedule.agents:
            if isinstance(a, DroneAgent) and a.unique_id in drone_rows:
                r = drone_rows[a.unique_id]
                a.status = r[1]
                a.assigned_cells = json.loads(r[2]) if r[2] else None
                a.thermal_memory = json.loads(r[3]) if r[3] else []
        
        # Update Cells (crucial for preserving revealed status and assignments)
        cursor.execute("SELECT x, y, revealed, assigned_to, obstacle_discovered FROM cells")
        for cx, cy, rev, asgn, obs_disc in cursor.fetchall():
            for obj in self.grid.get_cell_list_contents([(cx, cy)]):
                if isinstance(obj, CellAgent):
                    obj.revealed = bool(rev)
                    obj.assigned_to = asgn
                    obj.obstacle_discovered = bool(obs_disc)
        conn.close()

        if batch_intents:
            for d_id, intent in batch_intents.items():
                drone = next((a for a in self.schedule.agents if a.unique_id == d_id), None)
                if not drone or drone.is_destroyed: continue
                drone.status = intent.get("status", drone.status)
                
                action = intent.get("action")
                tx, ty = intent.get("x", drone.pos[0]), intent.get("y", drone.pos[1])

                self.step_logs.append({
                    "step": self.tick_count,
                    "drone_id": d_id,
                    "coordinate": drone.pos,
                    "status": drone.status,
                    "assigned_cells": drone.assigned_cells,
                    "target_cell": (tx, ty)
                })

                if action == "search":
                    crash = any(isinstance(o, CellAgent) and o.is_obstacle for o in self.grid.get_cell_list_contents([(tx, ty)]))
                    if crash:
                        drone.status = "CRASHED"; drone.is_destroyed = True
                        self.log_action(d_id, "Fatal crash!")
                    else:
                        drone.move((tx, ty))

                # Reveal current and adjacent cells for MOVE or SCAN
                if action in ["search", "scan"]:
                    adj = [(tx, ty), (tx+1, ty), (tx-1, ty), (tx, ty+1), (tx, ty-1)]
                    for ax, ay in adj:
                        if 0 <= ax < 20 and 0 <= ay < 20:
                            survivor_found_nearby = False
                            for o in self.grid.get_cell_list_contents([(ax, ay)]):
                                if isinstance(o, CellAgent): 
                                    o.revealed = True
                                    o.assigned_to = None # Clear assignment when revealed
                                    if o.is_obstacle: o.obstacle_discovered = True
                                if isinstance(o, SurvivorAgent) and not o.found:
                                    o.found = True; self.found_survivors += 1
                                    self.log_action(d_id, f"Survivor found at ({ax}, {ay})!")
                                    survivor_found_nearby = True
                            if survivor_found_nearby:
                                self.update_thermal_auras()

        self.schedule.step()
        
        destroyed = next((d for d in self.schedule.agents if getattr(d, "is_destroyed", False)), None)
        if destroyed: 
            self.mission_failed = True
            print("Mission Failed: Drone Destroyed!")
        elif self.total_survivors > 0 and self.found_survivors >= self.total_survivors: 
            self.mission_complete = True
            print("Mission Complete: All Survivors Found!")
        
        self.sync_to_db()

        if self.mission_complete or self.mission_failed:
            print("Generating log files")
            self.generate_log_file()

    def generate_log_file(self):
        try:
            with open("log_file.txt", "w") as f:
                f.write("Mission Log\n")
                f.write("="*50 + "\n")
                for log in self.step_logs:
                    f.write(f"Step: {log['step']} | Drone: {log['drone_id']} | Coord: {log['coordinate']} | Status: {log['status']} | Sector: {log['assigned_cells']} | Target: {log['target_cell']}\n")
        except Exception as e:
            print(f"Failed to write log file: {e}")

sim_world = None
def initialize_world(config=None):
    global sim_world
    sim_world = DisasterZoneModel(config)
    return sim_world
