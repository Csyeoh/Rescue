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

num_drones = 3
initial_drone_battery = 100

class SimulationConfig(BaseModel):
    pass

@app.post("/api/generate_map")
def generate_map():
    import map_generator
    try:
        map_data = map_generator.parse_ascii_map("map.txt")
        return {"status": "success", "message": "Map generated", "map_data": map_data, "num_drones": num_drones}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Failed to parse map.txt: {str(e)}"}

@app.post("/api/start_mission")
def start_mission():
    import map_generator
    try:
        map_data = map_generator.parse_ascii_map("map.txt")
        config_dict = {
            "num_drones": num_drones, 
            "drone_battery": initial_drone_battery,
            "map_data": map_data
        }
        simulation.initialize_world(config_dict)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Failed to initialize world: {str(e)}"}

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
    try:
        await websocket.accept()
    except Exception as e:
        print(f"[WS] Handshake failed: {e}")
        return

    websocket_manager.manager.active_connections.append(websocket)
    print(f"[WS] Client connected. Active={len(websocket_manager.manager.active_connections)}")

    try:
        while True:
            # receive() handles text, bytes, ping/pong, and close frames.
            # It will raise WebSocketDisconnect when the client disconnects.
            await websocket.receive()
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        websocket_manager.manager.disconnect(websocket)
