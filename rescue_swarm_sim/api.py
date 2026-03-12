from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import database
import simulation

# Initialize the API
app = FastAPI(title="Rescue Swarm API")

database.init_db()

# Fix CORS so your Next.js frontend can fetch data without browser errors
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For a hackathon, allowing all origins is perfectly fine
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 1. PYDANTIC MODELS (Validates UI Inputs)
# ==========================================
class SimulationConfig(BaseModel):
    scenario: str = "A dense residential area near a steep hill."
    flood_type: str = "Flash Flood"  # NEW: The flood physics category!
    
    num_drones: int = 2
    drone_battery: int = 100
    num_survivors: int = 5
    obstacle_difficulty: str = "med"  
    sim_difficulty: str = "easy"

# ==========================================
# 2. POST ENDPOINT (Starts the Simulation)
# ==========================================
@app.post("/api/start_mission")
def start_mission(config: SimulationConfig):
    """Receives the UI configuration and boots the dynamic Mesa engine."""
    config_dict = config.dict()
    
    print(f"Booting Swarm Nexus with {config.num_drones} drones on a fixed 20x20 grid...")
    print(f"AI Scenario: {config.scenario}")
    print(f"Difficulty: {config.sim_difficulty} | Obstacles: {config.obstacle_difficulty}")
    
    # Initialize the physics engine with the custom rules
    simulation.initialize_world(config_dict)
    
    return {
        "status": "success", 
        "message": "Environment generated. Awaiting AI Swarm Commands."
    }

# ==========================================
# 3. GET ENDPOINT (Broadcasts the Live World)
# ==========================================
@app.get("/state")
def get_world_state():
    """Returns the live state of the drones, terrain, and survivors as JSON."""
    try:
        conn = sqlite3.connect(database.DB_NAME, timeout=10.0)
        cursor = conn.cursor()
        
        # 1. Fetch live drone data
        cursor.execute("SELECT drone_id, x, y, battery FROM drones")
        drones = [
            {"id": row[0], "x": row[1], "y": row[2], "battery": row[3]} 
            for row in cursor.fetchall()
        ]
        
        # 2. Fetch survivor data
        cursor.execute("SELECT survivor_id, x, y, is_discovered FROM survivors")
        survivors = [
            {"id": row[0], "x": row[1], "y": row[2], "discovered": bool(row[3])} 
            for row in cursor.fetchall()
        ]
        
        # 3. Fetch terrain data
        try:
            cursor.execute("SELECT x, y, altitude, is_obstacle, terrain_type, obstacle_discovered FROM grid")
            terrain = [
                {
                    "x": row[0], "y": row[1], "altitude": row[2], 
                    "is_obstacle": bool(row[3]), "terrain_type": row[4], "obstacle_discovered": bool(row[5])
                }
                for row in cursor.fetchall()
            ]
        except sqlite3.OperationalError:
            terrain = []
            
        # Grid is fixed to 20x20
        grid_w, grid_h = 20, 20
            
        # 4. Fetch the 15 most recent logs
        cursor.execute("SELECT timestamp, drone_id, message FROM logs ORDER BY id DESC LIMIT 15")
        logs = [
            {"time": row[0], "drone": row[1], "message": row[2]} 
            for row in cursor.fetchall()
        ]

        # 5. Fetch live environment data directly from the new SQLite table
        try:
            cursor.execute("SELECT global_water_level, water_speed FROM environment WHERE id=1")
            env_row = cursor.fetchone()
            if env_row:
                env_data = {
                    "global_water_level": env_row[0],
                    "water_speed": env_row[1]
                }
            else:
                env_data = {"global_water_level": 0.0, "water_speed": 0.0}
        except sqlite3.OperationalError:
            env_data = {"global_water_level": 0.0, "water_speed": 0.0}

        conn.close()
        
        return {
            "grid": {"width": grid_w, "height": grid_h},
            "terrain": terrain,
            "drones": drones,
            "survivors": survivors,
            "logs": logs,
            "environment": env_data
        }
    except Exception as e:
        return {"error": str(e)}