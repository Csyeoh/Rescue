from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from pydantic import BaseModel
import simulation
import websocket_manager
from typing import Optional, Dict, Any

app = FastAPI(title="Rescue Swarm API")

@app.on_event("startup")
async def startup_event():
    websocket_manager.manager.loop = asyncio.get_running_loop()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SimulationConfig(BaseModel):
    scenario: str = ""
    num_drones: int = 3
    drone_battery: int = 100
    num_survivors: int = 5
    obstacle_difficulty: str = "med"
    map_data: Optional[Dict[str, Any]] = None

@app.post("/api/generate_map")
def generate_map(config: SimulationConfig):
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
    blueprint = map_generator.generate_semantic_blueprint(scenario_prompt, config.num_survivors)
    if blueprint is None: return {"status": "error", "message": "Failed to generate AI map."}

    obstacle_diff = config.obstacle_difficulty
    prob_map = {"high": 0.15, "low": 0.05, "med": 0.10}
    obstacle_prob = prob_map.get(obstacle_diff, 0.10)

    cells = map_generator.build_terrain_matrix(blueprint, obstacle_prob, 20, 20)
    map_data = {
        "blueprint": blueprint.model_dump() if hasattr(blueprint, 'model_dump') else blueprint.dict(),
        "cells": cells,
        "survivors": [s.model_dump() if hasattr(s, 'model_dump') else s.dict() for s in blueprint.survivors]
    }
    return {"status": "success", "message": "Map generated", "map_data": map_data}

@app.post("/api/start_mission")
def start_mission(config: SimulationConfig):
    simulation.initialize_world(config.model_dump() if hasattr(config, 'model_dump') else config.dict())
    import threading
    def run_flow():
        from swarm_flow.main import kickoff
        try: kickoff()
        except Exception as e: print(f"Flow Error: {e}")
    threading.Thread(target=run_flow, daemon=True).start()
    return {"status": "success", "message": "Mission started."}

@app.post("/api/reset")
def reset_simulation():
    simulation.sim_world = None
    return {"status": "success", "message": "Reset."}

@app.post("/api/abort")
def abort_mission():
    if simulation.sim_world:
        simulation.sim_world.mission_complete = True
    return {"status": "success", "message": "Aborted."}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_manager.manager.connect(websocket)
    try:
        while True:
            await asyncio.sleep(10) 
    except WebSocketDisconnect:
        websocket_manager.manager.disconnect(websocket)
