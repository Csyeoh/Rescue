from mesa import Agent, Model
from mesa.space import MultiGrid
import database
import sqlite3
import random

class DebrisAgent(Agent):
    """An impassable obstacle representing collapsed infrastructure from an earthquake."""
    def __init__(self, model, custom_id):
        super().__init__(model)
        self.custom_id = custom_id

class DroneAgent(Agent):
    """An agent representing a rescue drone in the swarm."""
    def __init__(self, model, custom_id, initial_battery=100):
        super().__init__(model)
        self.custom_id = custom_id 
        self.battery = initial_battery

    def attempt_move(self, new_x, new_y):
        """Validates the move, drains battery, checks for debris, and syncs to DB."""
        # Rule 1: Battery Check
        if self.battery < 5:
            return {"status": "failed", "reason": "low battery"}
        
        # Rule 2: Bounds Check
        if self.model.grid.out_of_bounds((new_x, new_y)):
            return {"status": "failed", "reason": "out of bounds"}

        # Rule 3: Debris Check (No-Fly Zone)
        cell_contents = self.model.grid.get_cell_list_contents([(new_x, new_y)])
        for agent in cell_contents:
            if isinstance(agent, DebrisAgent):
                return {"status": "failed", "reason": "path blocked by debris"}
                database.log_action(self.custom_id, "Path blocked by debris!")

        # Physically move the agent
        self.model.grid.move_agent(self, (new_x, new_y))
        
        # Rule 4: Base Camp Charging Mechanic
        if new_x == 0 and new_y == 0:
            self.battery = 100  
            status_msg = "success - arrived at base camp, battery recharged to 100%"
            database.log_action(self.custom_id, "Arrived at Base Camp (0,0). Battery recharged to 100%.")
        else:
            self.battery -= 5   
            status_msg = "success"
            database.log_action(self.custom_id, f"Moved to sector ({new_x}, {new_y}). Battery at {self.battery}%.")
        
        # Sync the new physical reality to the database
        database.update_drone_state(self.custom_id, new_x, new_y, self.battery)
        
        return {"status": status_msg, "new_location": (new_x, new_y), "battery": self.battery}

class DisasterZoneModel(Model):
    """The 2D simulation environment."""
    def __init__(self, width=20, height=20):
        super().__init__()
        self.grid = MultiGrid(width, height, torus=False)
        database.init_db()

        # Scatter 15 pieces of debris to simulate the earthquake disaster zone
        self.spawn_debris(15)

    def spawn_debris(self, num_debris):
        """Randomly places debris, ensuring Base Camp (0,0) remains clear."""
        debris_count = 0
        while debris_count < num_debris:
            x = random.randrange(self.grid.width)
            y = random.randrange(self.grid.height)
            
            # Keep Base Camp (0,0) and immediate surroundings clear
            if x <= 1 and y <= 1:
                continue
                
            # Ensure we don't stack debris on top of other debris
            if not any(isinstance(a, DebrisAgent) for a in self.grid.get_cell_list_contents([(x, y)])):
                debris = DebrisAgent(self, f"debris_{debris_count}")
                self.grid.place_agent(debris, (x, y))
                debris_count += 1

    def spawn_drone(self, custom_id, start_x, start_y):
        """Spawns a drone into both the grid and the database."""
        drone = DroneAgent(self, custom_id)
        self.grid.place_agent(drone, (start_x, start_y))
        
        conn = sqlite3.connect(database.DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO drones (drone_id, x, y, battery) VALUES (?, ?, ?, ?)", 
                       (custom_id, start_x, start_y, 100))
        conn.commit()
        conn.close()
        return drone

# ==========================================
# "THE CONTRACT" - MOVE FUNCTION
# ==========================================
sim_world = None

def initialize_world():
    global sim_world
    sim_world = DisasterZoneModel(20, 20)
    return sim_world

def move_to(drone_id: str, x: int, y: int) -> dict:
    global sim_world
    if sim_world is None:
        return {"status": "failed", "reason": "simulation not initialized"}
        
    drone = next((agent for agent in sim_world.agents if getattr(agent, 'custom_id', None) == drone_id), None)
    if not drone:
        return {"status": "failed", "reason": "drone not found in simulation"}
        
    return drone.attempt_move(x, y)


# ==========================================
# TESTING BLOCK
# ==========================================
if __name__ == "__main__":
    print("Initializing 2D Disaster Zone with Earthquake Debris...")
    world = initialize_world()
    
    # Let's forcefully put a piece of debris at (1, 0) to test the collision
    test_debris = DebrisAgent(world, "test_debris")
    world.grid.place_agent(test_debris, (1, 0))
    
    print("Spawning 'drone_beta' at Base Camp (0, 0)...")
    world.spawn_drone("drone_beta", 0, 0)
    
    print("\n=== RUNNING ADVANCED PHYSICS TEST ===")
    
    # Test 1: Hit the debris at (1, 0)
    print(f"Move 1 - Try hitting debris at (1, 0): {move_to('drone_beta', 1, 0)}")
    
    # Test 2: Move around it to (0, 1)
    print(f"Move 2 - Move to clear space (0, 1): {move_to('drone_beta', 0, 1)}")
    
    # Test 3: Return to Base Camp (0, 0) to trigger recharge
    print(f"Move 3 - Return to Base Camp (0, 0): {move_to('drone_beta', 0, 0)}")
    
    print("=====================================")