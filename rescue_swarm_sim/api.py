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
from typing import Optional, Dict, Any

class SimulationConfig(BaseModel):
    scenario: str = ""
    num_drones: int = 2
    drone_battery: int = 100
    num_survivors: int = 5
    obstacle_difficulty: str = "med"  
    sim_difficulty: str = "easy"
    map_data: Optional[Dict[str, Any]] = None

# ==========================================
# 2. POST ENDPOINT (Starts the Simulation)
# ==========================================
@app.post("/api/generate_map")
def generate_map(config: SimulationConfig):
    """Generates the map and returns it to the client for preview."""
    import random
    import map_generator
    
    scenario_prompt = config.scenario
    if not scenario_prompt:
        themes = [
            "A dense downtown commercial district.",
            "A tight-knit suburban neighborhood clustered in a valley.",
            "An industrial warehouse district with large number of buildings grouped together.",
            "A coastal urban center with dense housing",
            "A mixed urban layout with clusters of residential buildings."
        ]
        scenario_prompt = random.choice(themes)

    print(f"Generating Map Config: {scenario_prompt}")
    blueprint = map_generator.generate_semantic_blueprint(scenario_prompt, config.num_survivors)
    
    if blueprint is None:
        return {"status": "error", "message": "Failed to generate AI map."}

    obstacle_diff = config.obstacle_difficulty
    if obstacle_diff == "high": obstacle_prob = 0.25
    elif obstacle_diff == "low": obstacle_prob = 0.05
    else: obstacle_prob = 0.15

    cells = map_generator.build_terrain_matrix(blueprint, obstacle_prob, 20, 20)
    
    map_data = {
        "blueprint": blueprint.model_dump() if hasattr(blueprint, 'model_dump') else blueprint.dict(),
        "cells": cells,
        "scenario": scenario_prompt
    }
    return {"status": "success", "message": "Map generated.", "map_data": map_data}

@app.post("/api/start_mission")
def start_mission(config: SimulationConfig):
    """Receives the deploy signal and boots up the background engine."""
    simulation.initialize_world(config.dict(), start_sim=True)
        
    return {
        "status": "success", 
        "message": "Simulation Running."
    }

# ==========================================
# 3. GET ENDPOINT (Broadcasts the Live World)
# ==========================================

# we are going to use websocket / webhook
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
            # We join the question_plane (Ground Truth) with the answer_plane (Known AI Map)
            # The UI needs the ground truth `is_obstacle` so it can track the hidden layout.
            # But it also needs `obstacle_discovered` to render the UI 'fog of war'.
            cursor.execute('''
                SELECT q.x, q.y, q.altitude, q.is_obstacle, q.terrain_type, a.obstacle_discovered 
                FROM question_plane q
                JOIN answer_plane a ON q.x = a.x AND q.y = a.y
            ''')
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
            
        # 4. Fetch logs (limit 50 recent)
        cursor.execute("SELECT timestamp, drone_id, message FROM logs ORDER BY id DESC LIMIT 50")
        logs = [{"time": row[0], "drone": row[1], "message": row[2]} for row in cursor.fetchall()]

        conn.close()
        
        return {
            "grid": {"width": grid_w, "height": grid_h},
            "terrain": terrain,
            "drones": drones,
            "survivors": survivors,
            "logs": logs
        }
    except Exception as e:
        return {"error": str(e)}