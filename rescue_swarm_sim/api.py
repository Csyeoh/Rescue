from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
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
    num_drones: int = 2
    drone_battery: int = 100
    num_survivors: int = 5
    obstacle_difficulty: str = "med"
    map_data: Optional[Dict[str, Any]] = None

@app.post("/api/generate_map")
def generate_map(config: SimulationConfig):
    import map_generator
    try:
        blueprint, cells = map_generator.parse_ascii_map("map.txt")
        map_data = {
            "blueprint": blueprint.model_dump() if hasattr(blueprint, 'model_dump') else blueprint.dict(),
            "cells": cells,
            "survivors": [s.model_dump() if hasattr(s, 'model_dump') else s.dict() for s in blueprint.survivors]
        }
        return {"status": "success", "message": "Map strictly generated via static ascii txt.", "map_data": map_data}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Failed to parse map.txt: {str(e)}"}

@app.post("/api/start_mission")
def start_mission(config: SimulationConfig):
    config_dict = config.model_dump() if hasattr(config, 'model_dump') else config.dict()
    print(f"Starting mission with config: {config_dict}")
    simulation.initialize_world(config_dict)
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
        if hasattr(simulation.sim_world, 'generate_log_file'):
            simulation.sim_world.generate_log_file()
    return {"status": "success", "message": "Aborted."}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_manager.manager.connect(websocket)
    try:
        await asyncio.sleep(0.1)
        while True:
            await asyncio.sleep(10) 
    except WebSocketDisconnect:
        websocket_manager.manager.disconnect(websocket)
