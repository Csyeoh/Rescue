from mesa import Agent, Model
from mesa.space import MultiGrid
from mesa.time import RandomActivation
import database
import sqlite3
import random
import time
import threading
import map_generator
import traceback
import autopilot

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
        self.priority_searching_list = [] # Local state for decentralized logic
        self.status = "IDLE"
        self.step_count = 0

    def step(self):
        """
        Implementation of the fixed step() logic.
        Prioritizes the local 'priority_searching_list' over the DB 'drone_waypoints'.
        Includes Bingo Fuel survival reflex and strictly 1-tile movement.
        """
        # SILENCE THE DRONES: Check if docked at base with no tasks
        conn = database._connect()
        cursor = conn.cursor()
        
        # Get current position from DB
        cursor.execute("SELECT x, y, battery FROM drones WHERE drone_id=?", (self.custom_id,))
        curr = cursor.fetchone()
        if not curr:
            conn.close()
            return
        cx, cy, battery = curr
        
        # DOCKING FIX: Only dock if EXACTLY at 9,9
        if cx == 9 and cy == 9:
            # Check for any pending waypoints in DB
            cursor.execute("SELECT COUNT(*) FROM drone_waypoints WHERE drone_id=? AND is_done=0", (self.custom_id,))
            db_wp_count = cursor.fetchone()[0]
            
            # If at base and no local tasks and (no DB tasks OR only RTB task at 9,9)
            if not self.priority_searching_list:
                is_only_rtb = False
                if db_wp_count == 1:
                    cursor.execute("SELECT x, y FROM drone_waypoints WHERE drone_id=? AND is_done=0", (self.custom_id,))
                    wp = cursor.fetchone()
                    if wp[0] == 9 and wp[1] == 9:
                        is_only_rtb = True
                
                if db_wp_count == 0 or is_only_rtb:
                    self.status = "DOCKED"
                    conn.close()
                    return # Silent return, no logging or movement
        else:
            # Reset DOCKED status if we move away from base (e.g. on new mission)
            if self.status == "DOCKED":
                self.status = "ACTIVE"

        # 0. Get current position and battery from DB first
        self.battery = battery
        start = (cx, cy)
        base_pos = (9, 9)

        target = None
        seq = -1
        is_bingo = False

        # NEW: Global RTB Override
        if getattr(self.model, "mission_complete", False):
            self.priority_searching_list = [] # Clear local BFS targets
            target = base_pos # FORCE target to base
            seq = 0

        # 1. BINGO FUEL CHECK (Survival Reflex)
        # Calculate distance to base using current knowledge
        obstacles = autopilot._read_obstacle_set(conn)
        path_to_base = autopilot._a_star_path(start, base_pos, obstacles - {start, base_pos})
        distance_to_base = len(path_to_base) if path_to_base is not None else (abs(cx - 9) + abs(cy - 9))
        
        # RECALIBRATED: Bingo Fuel at 1% cost + 5% reserve
        if not getattr(self.model, "mission_complete", False) and start != base_pos and (battery <= (distance_to_base * 1) + 5):
            is_bingo = True
            print(f"⚠️ BINGO FUEL: Drone {self.custom_id} triggered RTB reflex. Battery: {battery}%, Dist: {distance_to_base}")
            
            # Survival Action: Clear mission state
            self.priority_searching_list = []
            with database.DB_WRITE_LOCK:
                conn_bingo = database._connect()
                cursor_bingo = conn_bingo.cursor()
                cursor_bingo.execute("DELETE FROM drone_waypoints WHERE drone_id=?", (self.custom_id,))
                cursor_bingo.execute("INSERT INTO logs (drone_id, message) VALUES (?, ?)", 
                                     (self.custom_id, "WARNING: Bingo Fuel reached! RTB for recharge."))
                conn_bingo.commit()
                conn_bingo.close()
            
            target = base_pos
        elif not is_bingo and target is None:
            # 2. Normal Logic: Check local search list first (Decentralized BFS)
            if self.priority_searching_list:
                target = self.priority_searching_list[0] 
                seq = 0 
                # print(f"DEBUG: Drone {self.custom_id} using local BFS target {target}. Remaining: {len(self.priority_searching_list)}")
            else:
                # 3. Fallback to SQLite Waypoints (Centralized Strategy)
                cursor.execute("""
                    SELECT seq, x, y FROM drone_waypoints 
                    WHERE drone_id=? AND is_done=0 
                    ORDER BY seq ASC LIMIT 1
                """, (self.custom_id,))
                wp = cursor.fetchone()
                if wp:
                    seq, tx, ty = wp
                    target = (tx, ty)
        
        if not target:
            conn.close()
            return

        # If already at target, pop and move on
        if start == target:
            # print(f"DEBUG: Drone {self.custom_id} already at {target}. Pop and mark done.")
            if not is_bingo and not getattr(self.model, "mission_complete", False) and self.priority_searching_list:
                self.priority_searching_list.pop(0)
            elif not is_bingo and not getattr(self.model, "mission_complete", False):
                with database.DB_WRITE_LOCK:
                    conn2 = database._connect()
                    conn2.execute("UPDATE drone_waypoints SET is_done=1 WHERE drone_id=? AND seq=?", (self.custom_id, seq))
                    conn2.commit()
                    conn2.close()
            conn.close()
            return

        # 4. Pathfinding using discovered hazards
        # Close connection before potential move logic to avoid lock issues
        conn.close()
        
        # WE MUST PATHFIND BUT ONLY SUBMIT THE VERY FIRST STEP
        path = autopilot._a_star_path(start, target, obstacles)
        
        if path:
            next_step = path[0] # STICTLY 1 STEP
            # print(f"DEBUG: Drone {self.custom_id} heading to {target}. Step: {next_step}")
            
            res = resolve_intent({
                "drone_id": self.custom_id,
                "action": "MOVE",
                "target_x": next_step[0],
                "target_y": next_step[1]
            })
            
            if "Success" in res:
                self.model.grid.move_agent(self, next_step)
                self.step_count += 1
                if not getattr(self.model, "mission_complete", False) and self.step_count % 20 == 0:
                    print(f"[{self.custom_id}] 📡 Sector {next_step} scanned. LIDAR nominal.")
                
                if next_step == target and not is_bingo:
                    if self.priority_searching_list:
                        self.priority_searching_list.pop(0)
                    else:
                        with database.DB_WRITE_LOCK:
                            conn = database._connect()
                            conn.execute("UPDATE drone_waypoints SET is_done=1 WHERE drone_id=? AND seq=?", (self.custom_id, seq))
                            conn.commit()
                            conn.close()
            elif ("Failure: Blocked" in res or "Collision" in res) and not is_bingo:
                # Discard unreachable target to prevent infinite loops
                print(f"DEBUG: Drone {self.custom_id} target {target} BLOCKED. Discarding.")
                if self.priority_searching_list:
                    self.priority_searching_list.pop(0)
                else:
                    with database.DB_WRITE_LOCK:
                        conn = database._connect()
                        conn.execute("UPDATE drone_waypoints SET is_done=1 WHERE drone_id=? AND seq=?", (self.custom_id, seq))
                        conn.commit()
                        conn.close()
        elif not is_bingo:
            # Unreachable path (e.g., completely boxed in by known obstacles)
            print(f"DEBUG: Drone {self.custom_id} NO PATH to {target}. Discarding.")
            if self.priority_searching_list:
                self.priority_searching_list.pop(0)
            else:
                with database.DB_WRITE_LOCK:
                    conn = database._connect()
                    conn.execute("UPDATE drone_waypoints SET is_done=1 WHERE drone_id=? AND seq=?", (self.custom_id, seq))
                    conn.commit()
                    conn.close()

class DisasterZoneModel(Model):
    def __init__(self, config=None):
        super().__init__()
        if config is None: config = {}

        self.width = 20
        self.height = 20
        self.tick_count = 0
        
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
            # Fallback
            scenario_prompt = config.get("scenario", "")
            if not scenario_prompt:
                themes = ["A mixed urban layout with clusters of residential buildings."]
                scenario_prompt = random.choice(themes)
                
            blueprint = map_generator.generate_semantic_blueprint(scenario_prompt, num_survivors)
            cells = map_generator.build_terrain_matrix(blueprint, obstacle_prob, self.width, self.height)
            ai_survivors = [{"x": s.x, "y": s.y} for s in blueprint.survivors] if blueprint else []

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

    def _clear_old_mission_data(self, keep_map=False):
        """
        Modified to preserve discovered obstacles and survivors based on user feedback.
        """
        conn = sqlite3.connect(database.DB_NAME, timeout=10.0)
        cursor = conn.cursor()

        if not keep_map:
            cursor.execute("DELETE FROM question_plane")
            cursor.execute("DELETE FROM answer_plane")
            cursor.execute("DELETE FROM survivors")
        else:
            # If keeping map:
            # 1. Reset ONLY survivor discovery so they can be "found" again.
            # 2. DO NOT reset obstacle discovery - they "remain" on the map.
            cursor.execute("UPDATE survivors SET is_discovered=0")
            # We explicitly do NOT reset is_scanned/obstacle_discovered on answer_plane

        # Reset drones to base rather than deleting them, ensuring agent.py stays in sync
        cursor.execute("UPDATE drones SET x=9, y=9, battery=100, is_active=1")
        cursor.execute("DELETE FROM logs")

        conn.commit()
        conn.close()

        # Reset internal agent states to match DB
        for agent in self.schedule.agents:
            if isinstance(agent, DroneAgent):
                agent.battery = 100
                agent.status = "IDLE"
                agent.priority_searching_list = []
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
            if not (0 <= x < 20 and 0 <= y < 20) or (x, y) in used_coords: continue
            used_coords.add((x, y))
            cursor.execute("INSERT OR IGNORE INTO survivors (survivor_id, x, y, is_discovered) VALUES (?, ?, ?, ?)",
                           (f"survivor_{spawned+1}", x, y, False))
            spawned += 1
        while spawned < fallback_count:
            x, y = random.randint(0, 19), random.randint(0, 19)
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
        """
        Modified step() to allow drones to return to base after mission completion
        and trigger an automatic reset once all are DOCKED.
        """
        conn = database._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*), SUM(is_discovered) FROM survivors")
        row = cursor.fetchone()
        conn.close()

        if row:
            total, found = row[0], (row[1] if row[1] is not None else 0)
            if total > 0 and total == found:
                if not getattr(self, "mission_complete", False):
                    self.mission_complete = True
                    self.reset_counter = 0 # New counter to delay the reset
                    database.log_action("SYSTEM", "🎉 MISSION ACCOMPLISHED! All survivors rescued. Initiating global RTB.")

                # Check if all drones are DOCKED AND at base
                drones = [a for a in self.schedule.agents if isinstance(a, DroneAgent)]
                if drones and all(a.status == "DOCKED" and a.pos == (9, 9) for a in drones):
                    self.reset_counter += 1
                    if self.reset_counter == 1:
                        database.log_action("SYSTEM", "🏁 All drones have returned to (9,9). Preparing final mission report.")
                    
                    if self.reset_counter > 20: # Wait 20 ticks (10 seconds) to ensure everything is synced
                        database.log_action("SYSTEM", "♻️ MISSION COMPLETE. Auto-resetting for next deployment.")
                        print("♻️ All drones DOCKED. Auto-resetting simulation.")
                        self._clear_old_mission_data(keep_map=True)
                        # Clear waypoints and zones explicitly for a full reset
                        with database.DB_WRITE_LOCK:
                            conn_reset = database._connect()
                            conn_reset.execute("DELETE FROM drone_waypoints")
                            conn_reset.execute("DELETE FROM drone_zones")
                            conn_reset.execute("DELETE FROM cell_weights")
                            conn_reset.commit()
                            conn_reset.close()
                        self.mission_complete = False # Ready for next deploy signal
                        return # Skip the rest of this step

        self.tick_count += 1
        self.schedule.step() 
        self.sync_terrain_to_db()


# ==========================================
# ⚙️ INTENT RESOLVER
# ==========================================
def resolve_intent(intent: dict):
    """
    Bridge between agents and hardware.
    Includes Physics Guardrail and Step-and-Scan logic.
    """
    import database
    import sqlite3
    
    drone_id = intent.get("drone_id")
    action = intent.get("action")
    tx, ty = intent.get("target_x"), intent.get("target_y")
    
    if action == "MOVE":
        if not (0 <= tx < 20 and 0 <= ty < 20):
            return "Failure: Coordinates out of bounds."

        with database.DB_WRITE_LOCK:
            conn = database._connect()
            cursor = conn.cursor()

            # 0. STRICT PHYSICS GUARDRAIL (Manhattan Dist > 1 check)
            cursor.execute("SELECT x, y, battery FROM drones WHERE drone_id=?", (drone_id,))
            drone_data = cursor.fetchone()
            if not drone_data:
                conn.close()
                return f"Error: {drone_id} not found."
            
            x, y, battery = drone_data
            if abs(tx - x) + abs(ty - y) > 1:
                # Teleportation detected!
                conn.close()
                return f"Failure: Blocked. Manhattan distance {abs(tx - x) + abs(ty - y)} > 1."

            # 1. Check battery
            if battery < 1:
                conn.close()
                return f"Failure: {drone_id} battery exhausted."

            # Helper to check if mission is active
            cursor.execute("SELECT COUNT(*) FROM survivors WHERE is_discovered=0")
            mission_active = cursor.fetchone()[0] > 0

            # 2. Check for physical obstacles
            cursor.execute("SELECT is_obstacle FROM question_plane WHERE x=? AND y=?", (tx, ty))
            grid_data = cursor.fetchone()
            if grid_data and grid_data[0] == 1:
                # Collision! Map it.
                cursor.execute("UPDATE answer_plane SET obstacle_discovered=1, is_scanned=1 WHERE x=? AND y=?", (tx, ty))
                cursor.execute("INSERT INTO logs (drone_id, message) VALUES (?, ?)", (drone_id, f"CRITICAL: Collision at ({tx}, {ty})!"))
                if mission_active:
                    print(f"[{drone_id}] 🚧 Structural anomaly mapped at ({tx}, {ty}).")
                conn.commit()
                conn.close()
                return "Failure: Blocked."

            # 3. Successful move logic (Charging Pad area abs(diff) <= 1, Drain reduced to 1%)
            is_charging = (abs(tx - 9) <= 1 and abs(ty - 9) <= 1)
            new_battery = 100 if is_charging else battery - 1
            cursor.execute("UPDATE drones SET x=?, y=?, battery=? WHERE drone_id=?", (tx, ty, new_battery, drone_id))
            cursor.execute("UPDATE answer_plane SET is_scanned=1 WHERE x=? AND y=?", (tx, ty))

            # 4. STEP-AND-SCAN: Check the 4 adjacent grids (Up, Down, Left, Right)
            adj = [(tx, ty-1), (tx, ty+1), (tx-1, ty), (tx+1, ty)]
            for ax, ay in adj:
                if 0 <= ax < 20 and 0 <= ay < 20:
                    # Reveal obstacles in adjacent cells
                    cursor.execute("SELECT is_obstacle FROM question_plane WHERE x=? AND y=?", (ax, ay))
                    a_obs = cursor.fetchone()
                    is_a_obs = bool(a_obs[0]) if a_obs else False
                    
                    if is_a_obs:
                        cursor.execute("SELECT obstacle_discovered FROM answer_plane WHERE x=? AND y=?", (ax, ay))
                        already_known = cursor.fetchone()[0]
                        cursor.execute("UPDATE answer_plane SET obstacle_discovered=1, is_scanned=1 WHERE x=? AND y=?", (ax, ay))
                        if mission_active and not already_known:
                            print(f"[{drone_id}] 🚧 Structural anomaly mapped at ({ax}, {ay}).")
                    else:
                        cursor.execute("UPDATE answer_plane SET is_scanned=1 WHERE x=? AND y=?", (ax, ay))
                    
                    # Detect survivors in adjacent cells
                    cursor.execute("SELECT survivor_id FROM survivors WHERE x=? AND y=? AND is_discovered=0", (ax, ay))
                    surv = cursor.fetchone()
                    if surv:
                        cursor.execute("UPDATE survivors SET is_discovered=1 WHERE survivor_id=?", (surv[0],))
                        cursor.execute("INSERT INTO logs (drone_id, message) VALUES (?, ?)", (drone_id, f"Survivor spotted at ({ax}, {ay})!"))
                        if mission_active:
                            print(f"[{drone_id}] 🚨 CRITICAL: High-density heat signature detected at ({ax}, {ay})! Survivor located.")

            conn.commit()
            conn.close()
            return f"Success: Moved to ({tx}, {ty})"
            
    elif action == "THERMAL_SCAN":
        import mcp_server
        return mcp_server.thermal_scan(drone_id)
        
    return f"Error: Unknown action {action}"

# ==========================================
# ⏱️ IMMORTAL BACKGROUND HEARTBEAT THREAD
# ==========================================
sim_world = None
sim_running = False

def _run_sim_loop():
    """Critical Fix 3: Immortal thread with traceback and 0.5s tick."""
    global sim_world, sim_running
    print("🟢 [ENGINE] Physics thread is ALIVE.")
    
    while sim_running:
        try:
            if sim_world:
                sim_world.step()
        except Exception:
            print(f"\n🔥 [FATAL ENGINE CRASH] Simulation halted:")
            traceback.print_exc()
        time.sleep(0.5)

def initialize_world(config=None, start_sim=True):
    global sim_world
    if config is None: config = {}
    if config.get("num_drones", 0) < 1: config["num_drones"] = 5
    sim_world = DisasterZoneModel(config)
    if start_sim: start_sim_thread()
    return sim_world

def start_sim_thread():
    global sim_running
    if not sim_running:
        sim_running = True
        t = threading.Thread(target=_run_sim_loop, daemon=True)
        t.start()
