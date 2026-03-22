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

from typing import Optional, Dict, Any, List

class SimulationConfig(BaseModel):
    scenario: str = ""
    num_drones: int = 3
    drone_battery: int = 100
    num_survivors: int = 5
    obstacle_difficulty: str = "med"
    map_data: Optional[Dict[str, Any]] = None

def get_world_state():
    """Extracts live state from simulation.sim_world for the frontend."""
    if not simulation.sim_world:
        return {
            "drones": [],
            "terrain": [],
            "survivors": [],
            "logs": [],
            "is_mission_complete": False
        }

    world = simulation.sim_world
    drones = []
    terrain = []
    survivors = []

    from simulation import DroneAgent, CellAgent, SurvivorAgent

    for cell_contents, (x, y) in world.grid.coord_iter():
        for obj in cell_contents:
            if isinstance(obj, DroneAgent):
                drones.append({
                    "id": obj.unique_id,
                    "x": x,
                    "y": y,
                    "battery": obj.battery,
                    "status": obj.status
                })
            elif isinstance(obj, CellAgent):
                terrain.append({
                    "x": x,
                    "y": y,
                    "altitude": obj.altitude,
                    "is_obstacle": obj.is_obstacle,
                    "terrain_type": obj.terrain_type,
                    "obstacle_discovered": obj.obstacle_discovered
                })
            elif isinstance(obj, SurvivorAgent):
                survivors.append({
                    "x": x,
                    "y": y,
                    "discovered": obj.found
                })

    return {
        "drones": drones,
        "terrain": terrain,
        "survivors": survivors,
        "logs": world.mission_logs[-50:], # Last 50 logs
        "is_mission_complete": getattr(world, "mission_complete", False)
    }

# Endpoint for Generate Map
@app.post("/api/generate_map")
def generate_map(config: SimulationConfig):
    """Generates the map and returns it to the client for preview."""
    import map_generator

    themes_map = {
        "downtown": "A structured city center with multi-story blocks and wide transport avenues.",
        "suburban": "A sparse residential neighborhood with houses separated by large yards and gardens.",
        "industrial": "A low-density industrial park with warehouses placed in isolated clusters.",
        "coastal": "A seaside settlement with buildings clustered on elevated ground away from the shore.",
        "mixed urban": "A versatile urban environment with a mix of structures along a clean grid.",
        "mountain outpost": "A rugged mountain village where outposts are tiered along natural terrain contours."
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
        "survivors": [s.model_dump() if hasattr(s, 'model_dump') else s.dict() for s in blueprint.survivors]
    }
    return {"status": "success", "message": "Map generated", "map_data": map_data}

@app.post("/api/start_mission")
def start_mission(config: SimulationConfig):
    """Receives the deploy signal and boots up the background engine."""
    simulation.initialize_world(config.dict() if hasattr(config, 'dict') else config.model_dump())

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

@app.post("/api/reset")
def reset_simulation():
    """Wipes the simulation state."""
    simulation.sim_world = None
    simulation.sim_running = False
    return {"status": "success", "message": "Simulation reset."}

@app.post("/api/abort")
def abort_mission():
    """Aborts the mission."""
    if simulation.sim_world:
        simulation.sim_world.mission_complete = True
        simulation.sim_world.log_action("SYSTEM", "🛑 MISSION ABORTED.")
    return {"status": "success", "message": "Mission aborted."}

# WebSocket endpoint
from fastapi import WebSocketDisconnect

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_manager.manager.connect(websocket)
    try:
        while True:
            # Send tick updates periodically
            state = get_world_state()
            await websocket.send_json({"type": "tick_update", "payload": state})
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        websocket_manager.manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        websocket_manager.manager.disconnect(websocket)