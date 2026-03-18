from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from pydantic import BaseModel
import simulation
import websocket_manager
from dotenv import load_dotenv
load_dotenv()

# Guard: prevent multiple concurrent flow spawns
_flow_running = False

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
async def generate_map(config: SimulationConfig):
    """Generates the map and returns it to the client for preview."""
    import map_generator
    
    themes_map = {
        "downtown": "A dense downtown commercial district.",
        "suburban": "A tight-knit suburban neighborhood clustered in a valley.",
        "industrial": "An industrial warehouse district with large number of buildings grouped together.",
        "coastal": "A coastal urban center with dense housing",
        "mixed": "A mixed urban layout with clusters of residential buildings."
    }
    
    scenario_prompt = themes_map.get(config.scenario, "A mixed urban layout")
    print(f"Generating Map Config: {scenario_prompt}")
    
    # Run CPU/Network bound generation in a thread to avoid blocking loop
    blueprint = await asyncio.to_thread(map_generator.generate_semantic_blueprint, scenario_prompt, config.num_survivors)
    
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
async def start_mission(config: SimulationConfig):
    """Receives the deploy signal and boots up the background engine."""
    global _flow_running
    if _flow_running:
        return {"status": "already_running", "message": "Swarm is already active."}
    
    # Initialize simulation world
    simulation.initialize_world(config.dict())
    _flow_running = True
    
    # Start background loop
    async def run_flow_wrapper():
        global _flow_running
        from swarm_flow.main import kickoff
        try:
            print("[Nexus] Starting AI Swarm Commander in background task...")
            # Use to_thread for the blocking kickoff
            await asyncio.to_thread(kickoff)
        except Exception as e:
            print(f"Error running Flow: {e}")
        finally:
            _flow_running = False
            print("[Nexus] AI Swarm Commander task finished.")

    asyncio.create_task(run_flow_wrapper())
        
    return {
        "status": "success", 
        "message": "Simulation Running.",
        "config": config.dict()
    }

# ──────────────────────────────────────────────
# MCP Bridge Endpoints
# ──────────────────────────────────────────────

@app.get("/api/mcp/drones")
def mcp_get_drones():
    if not simulation.sim_world: return []
    from simulation import DroneAgent
    return [a.unique_id for a in simulation.sim_world.schedule.agents if isinstance(a, DroneAgent)]

@app.get("/api/mcp/drone/{drone_id}/battery")
def mcp_get_battery(drone_id: str):
    if not simulation.sim_world: return -1
    for a in simulation.sim_world.schedule.agents:
        if a.unique_id == drone_id and hasattr(a, 'battery'):
            return a.battery
    return -1

@app.get("/api/mcp/drone/{drone_id}/status")
def mcp_get_status(drone_id: str):
    if not simulation.sim_world: return "Error: simulation resting."
    for a in simulation.sim_world.schedule.agents:
        if a.unique_id == drone_id and hasattr(a, 'status'):
            return a.status
    return f"Error: {drone_id} not found."

@app.post("/api/mcp/drone/{drone_id}/status")
def mcp_set_status(drone_id: str, payload: dict):
    if not simulation.sim_world: return "Error: simulation resting."
    new_status = payload.get("status")
    for a in simulation.sim_world.schedule.agents:
        if a.unique_id == drone_id:
            a.status = new_status
            return f"Success: {drone_id} status changed to {new_status}"
    return f"Error: {drone_id} not found."

@app.get("/api/mcp/drone/{drone_id}/pos")
def mcp_get_pos(drone_id: str):
    if not simulation.sim_world: return {"error": "no sim"}
    for a in simulation.sim_world.schedule.agents:
        if a.unique_id == drone_id and a.pos:
            return {"x": a.pos[0], "y": a.pos[1]}
    return {"x": 9, "y": 9}

@app.get("/api/mcp/drone/{drone_id}/waypoints")
def mcp_get_waypoints(drone_id: str):
    if not simulation.sim_world: return []
    for a in simulation.sim_world.schedule.agents:
        if a.unique_id == drone_id and hasattr(a, 'priority_searching_list'):
            remaining = [pos for pos in a.priority_searching_list if pos not in simulation.sim_world.global_discovered_cells]
            return remaining[:10]
    return []

@app.get("/api/mcp/drone/{drone_id}/thermal")
def mcp_get_thermal(drone_id: str):
    if not simulation.sim_world: return []
    for a in simulation.sim_world.schedule.agents:
        if a.unique_id == drone_id and hasattr(a, 'thermal_memory'):
            return a.thermal_memory
    return []

@app.get("/api/mcp/drone/{drone_id}/thermal_scan")
def mcp_thermal_scan(drone_id: str):
    if not simulation.sim_world: return "Error: no sim"
    from simulation import DroneAgent, SurvivorAgent
    world = simulation.sim_world
    drone = next((a for a in world.schedule.agents if a.unique_id == drone_id), None)
    if not drone or not drone.pos: return "Error: not found"
    
    for obj in world.grid.get_cell_list_contents([drone.pos]):
        if isinstance(obj, SurvivorAgent) and not obj.found:
            return f"THERMAL SIGNATURE DETECTED at {drone.pos}."
    return "No thermal signatures detected here."

@app.get("/api/mcp/drone/{drone_id}/step_towards")
def mcp_step_towards(drone_id: str, tx: int, ty: int):
    if not simulation.sim_world: return {"error": "no sim"}
    from simulation import DroneAgent, CellAgent
    world = simulation.sim_world
    drone = next((a for a in world.schedule.agents if a.unique_id == drone_id), None)
    if not drone or not drone.pos: return {"error": "not found"}
    
    cx, cy = drone.pos
    if cx == tx and cy == ty: return {"already_at_target": True, "x": cx, "y": cy}
    
    candidates = []
    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        nx, ny = cx + dx, cy + dy
        if 0 <= nx < world.width and 0 <= ny < world.height:
            is_blocked = any(isinstance(o, CellAgent) and getattr(o, "is_obstacle", False) 
                            for o in world.grid.get_cell_list_contents([(nx, ny)]))
            if not is_blocked:
                dist = abs(nx - tx) + abs(ny - ty)
                candidates.append((dist, nx, ny))
    
    if not candidates: return {"error": "blocked"}
    candidates.sort(key=lambda t: t[0])
    return {"already_at_target": False, "x": candidates[0][1], "y": candidates[0][2]}

@app.get("/api/mcp/drone/{drone_id}/thermal_scan")
def mcp_thermal_scan(drone_id: str):
    if not simulation.sim_world: return "Error: no sim"
    from simulation import DroneAgent, SurvivorAgent
    world = simulation.sim_world
    drone = next((a for a in world.schedule.agents if a.unique_id == drone_id), None)
    if not drone or not drone.pos: return "Error: not found"
    
    for obj in world.grid.get_cell_list_contents([drone.pos]):
        if isinstance(obj, SurvivorAgent) and not obj.found:
            return f"THERMAL SIGNATURE DETECTED at {drone.pos}. Rescue recommended."
    return "No thermal signatures detected here."

@app.get("/api/mcp/mission_data")
def mcp_mission_data():
    if not simulation.sim_world: return {"mission_status": "error"}
    w = simulation.sim_world
    return {
        "mission_status": "complete" if getattr(w, "mission_complete", False) else "in_progress",
        "remaining_survivors": w.total_survivors - w.found_survivors,
        "global_discovered_count": len(w.global_discovered_cells)
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