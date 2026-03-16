from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from pydantic import BaseModel
import simulation
import websocket_manager

# Initialize the API
app = FastAPI(title="Rescue Swarm API")

@app.on_event("startup")
async def startup_event():
    # Capture the main event loop so background threads can use it
    websocket_manager.manager.loop = asyncio.get_running_loop()

# CORS Policy 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For a hackathon, allowing all origins is perfectly fine
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from typing import Optional, Dict, Any

class SimulationConfig(BaseModel):
    scenario: str = ""
    num_drones: int = 3
    drone_battery: int = 100
    num_survivors: int = 5
    obstacle_difficulty: str = "med"  
    map_data: Optional[Dict[str, Any]] = None

# Endpoint for Generate Map
@app.post("/api/generate_map")
def generate_map(config: SimulationConfig):
    """Generates the map and returns it to the client for preview."""
    import random
    import map_generator
    
    themes_map = {
        "downtown": "A dense downtown commercial district.",
        "suburban": "A tight-knit suburban neighborhood clustered in a valley.",
        "industrial": "An industrial warehouse district with large number of buildings grouped together.",
        "coastal": "A coastal urban center with dense housing",
        "mixed": "A mixed urban layout with clusters of residential buildings."
    }
    
    scenario_prompt = themes_map.get(config.scenario, "")
    print(f"Generating Map Config: {scenario_prompt}")
    blueprint = map_generator.generate_semantic_blueprint(scenario_prompt, config.num_survivors)
    if blueprint is None: return {"status": "error", "message": "Failed to generate AI map."}

    obstacle_diff = config.obstacle_difficulty
    if obstacle_diff == "high": obstacle_prob = 0.15
    elif obstacle_diff == "low": obstacle_prob = 0.05
    else: obstacle_prob = 0.10

    cells = map_generator.build_terrain_matrix(blueprint, obstacle_prob, 20, 20)
    map_data = {
        "blueprint": blueprint.model_dump() if hasattr(blueprint, 'model_dump') else blueprint.dict(),
        "cells": cells,
    }
    return {"status": "success", "message": "Map generated", "map_data": map_data}

@app.post("/api/start_mission")
def start_mission(config: SimulationConfig):
    """Receives the deploy signal and boots up the background engine."""
    simulation.initialize_world(config.dict())
    
    import threading
    import sys
    import os
    if os.path.abspath(os.path.join(os.path.dirname(__file__))) not in sys.path:
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))
    
    def run_flow_async():
        from swarm_flow.main import kickoff
        try:
            kickoff()
        except Exception as e:
            print(f"Error running Flow: {e}")
            
    t = threading.Thread(target=run_flow_async, daemon=True)
    t.start()
        
    return {
        "status": "success", 
        "message": "Simulation Running."
    }

# WebSocket endpoint
from fastapi import WebSocketDisconnect

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_manager.manager.connect(websocket)
    try:
        while True:
            # We wait for messages from the client (or just keep it open)
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.manager.disconnect(websocket)