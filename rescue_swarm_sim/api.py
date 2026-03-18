from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from pydantic import BaseModel
import logging
import os
import threading
import time
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
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, level, logging.INFO), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("uvicorn").setLevel(getattr(logging, level, logging.INFO))
    logging.getLogger("uvicorn.error").setLevel(getattr(logging, level, logging.INFO))
    logging.getLogger("uvicorn.access").setLevel(getattr(logging, level, logging.INFO))
    _start_intent_flusher()

def _apply_intent_batch(intents: list[dict]) -> None:
    if not simulation.sim_world:
        return
    from simulation import resolve_intent, DroneAgent
    all_map_updates = []
    all_events = []
    for it in intents:
        res = resolve_intent(simulation.sim_world, it)
        all_map_updates.extend(res.get("map_updates", []))
        for e in res.get("events", []):
            all_events.append({"drone_id": res.get("drone_id"), "event": e})
    drone_states = []
    for a in simulation.sim_world.schedule.agents:
        if isinstance(a, DroneAgent):
            drone_states.append({"id": a.unique_id, "x": a.pos[0] if a.pos else 9, "y": a.pos[1] if a.pos else 9, "battery": a.battery, "status": a.status})
    agent_logs = [{"type": "intent", "drone_id": it.get("drone_id"), "content": it.get("rationale", "")[:300]} for it in intents]
    payload = {
        "tick": getattr(simulation.sim_world, "tick_count", 0),
        "drone_states": drone_states,
        "map_updates": all_map_updates,
        "events": all_events,
        "agent_logs": agent_logs
    }
    try:
        websocket_manager.send_to_ui("tick_update", payload)
        _log.info(f"Applied batch and broadcast with {len(all_map_updates)} updates")
    except Exception as e:
        _log.error(f"WS broadcast error: {e}")

def _start_intent_flusher() -> None:
    global _intent_flusher_started
    if _intent_flusher_started:
        return
    _intent_flusher_started = True

    def _loop():
        global _intent_batch_started_at
        while True:
            time.sleep(0.5)
            if not simulation.sim_world:
                continue
            with _intent_lock:
                if not _intent_buffer or _intent_batch_started_at is None:
                    continue
                age = time.time() - _intent_batch_started_at
                if age < _intent_batch_timeout_s:
                    continue
                from simulation import DroneAgent
                drone_ids = []
                for a in simulation.sim_world.schedule.agents:
                    if isinstance(a, DroneAgent):
                        drone_ids.append(a.unique_id)
                missing = [d for d in drone_ids if d not in _intent_buffer]
                intents = [v for k, v in sorted(_intent_buffer.items(), key=lambda x: x[0])]
                for d in missing:
                    intents.append({"drone_id": d, "action": "IDLE", "target_x": 0, "target_y": 0, "rationale": "Auto-flush: missing intent", "new_status": None})
                _intent_buffer.clear()
                _intent_batch_started_at = None
            try:
                _log.warning(f"Auto-flush applied. Missing={missing}")
                _apply_intent_batch(intents)
            except Exception as e:
                _log.error(f"Auto-flush error: {e}")

    t = threading.Thread(target=_loop, daemon=True)
    t.start()

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

class IntentPayload(BaseModel):
    drone_id: str
    action: str
    target_x: int
    target_y: int
    rationale: str
    new_status: Optional[str] = None

_intent_buffer: Dict[str, Dict[str, Any]] = {}
_intent_lock = threading.Lock()
_intent_batch_started_at: float | None = None
_intent_batch_timeout_s: float = float(os.getenv("INTENT_BATCH_TIMEOUT_S", "3.0"))
_intent_flusher_started = False
_intent_apply_mode: str = os.getenv("INTENT_APPLY_MODE", "sequential").lower()
_log = logging.getLogger("api")

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

@app.post("/api/mcp/intent")
def mcp_submit_intent(intent: IntentPayload):
    if not simulation.sim_world: 
        return {"status": "error", "message": "simulation not initialized"}
    from simulation import DroneAgent
    if _intent_apply_mode == "sequential":
        _log.info(f"Apply intent (sequential) from {intent.drone_id}: action={intent.action} target=({intent.target_x},{intent.target_y}) new_status={intent.new_status}")
        _apply_intent_batch([intent.dict()])
        return {"status": "applied_single", "drone_id": intent.drone_id}
    with _intent_lock:
        global _intent_batch_started_at
        if _intent_batch_started_at is None:
            _intent_batch_started_at = time.time()
        _intent_buffer[intent.drone_id] = intent.dict()
        _log.info(f"Queued intent from {intent.drone_id}: action={intent.action} target=({intent.target_x},{intent.target_y}) new_status={intent.new_status}")
        expected = 0
        for a in simulation.sim_world.schedule.agents:
            if isinstance(a, DroneAgent):
                expected += 1
        if len(_intent_buffer) < expected:
            _log.info(f"Intent queued {len(_intent_buffer)}/{expected}")
            return {"status": "queued", "queued": len(_intent_buffer), "expected": expected}
        intents = [v for k, v in sorted(_intent_buffer.items(), key=lambda x: x[0])]
        _intent_buffer.clear()
        _intent_batch_started_at = None
    _log.info(f"Applying batch of {len(intents)} intents")
    try:
        _apply_intent_batch(intents)
    except Exception as e:
        _log.error(f"WS broadcast error: {e}")
    return {"status": "applied_batch", "applied": len(intents)}

@app.get("/api/health")
def health():
    return {"ok": True}

@app.get("/api/debug/state")
def debug_state():
    if not simulation.sim_world:
        return {"sim": "down"}
    from simulation import DroneAgent
    drones = []
    for a in simulation.sim_world.schedule.agents:
        if isinstance(a, DroneAgent):
            drones.append(a.unique_id)
    with _intent_lock:
        started = _intent_batch_started_at
        age = None if started is None else time.time() - started
        qsize = len(_intent_buffer)
    return {"queue_size": qsize, "drones": drones, "tick": getattr(simulation.sim_world, "tick_count", 0), "batch_age_s": age, "batch_timeout_s": _intent_batch_timeout_s, "intent_apply_mode": _intent_apply_mode}

@app.get("/api/debug/intents")
def debug_intents():
    if not simulation.sim_world:
        return {"sim": "down"}
    with _intent_lock:
        return {"queued_drone_ids": sorted(list(_intent_buffer.keys()))}

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

@app.get("/api/mcp/drone/{drone_id}/scan_adjacent")
def mcp_scan_adjacent(drone_id: str):
    if not simulation.sim_world:
        return {"error": "no sim"}
    from simulation import DroneAgent, CellAgent, SurvivorAgent
    world = simulation.sim_world
    drone = next((a for a in world.schedule.agents if isinstance(a, DroneAgent) and a.unique_id == drone_id), None)
    if not drone or not drone.pos:
        return {"error": "not found"}
    cx, cy = drone.pos
    map_updates = []
    events = []
    adjacent = []
    for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
        x, y = cx + dx, cy + dy
        if not (0 <= x < world.width and 0 <= y < world.height):
            continue
        map_updates.append({"x": x, "y": y, "discovered": True})
        contents = world.grid.get_cell_list_contents([(x, y)])
        is_obstacle = any(isinstance(o, CellAgent) and getattr(o, "is_obstacle", False) for o in contents)
        has_aura = any(isinstance(o, CellAgent) and getattr(o, "thermal_aura", False) for o in contents)
        survivor_present = any(isinstance(o, SurvivorAgent) and not o.found for o in contents)
        if survivor_present:
            map_updates.append({"x": x, "y": y, "survivor_detected": True})
        for obj in contents:
            if isinstance(obj, CellAgent) and obj.is_obstacle and not obj.obstacle_discovered:
                obj.obstacle_discovered = True
                map_updates.append({"x": x, "y": y, "obstacle_discovered": True})
        if has_aura:
            sv_at = world.grid.get_cell_list_contents([(x, y)])
            already_found = any(isinstance(s, SurvivorAgent) and s.found for s in sv_at)
            if not already_found:
                map_updates.append({"x": x, "y": y, "thermal_aura": True})
                if (x, y) not in drone.thermal_memory:
                    drone.thermal_memory.append((x, y))
                    events.append(f"THERMAL ALERT at ({x},{y}) added to memory")
        if survivor_present:
            events.append(f"SURVIVOR DETECTED adjacent at ({x},{y})")
        adjacent.append({"x": x, "y": y, "is_obstacle": is_obstacle, "thermal_aura": has_aura, "survivor_present": survivor_present})
    return {"center": {"x": cx, "y": cy}, "adjacent": adjacent, "map_updates": map_updates, "events": events}

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

    if not (0 <= tx < world.width and 0 <= ty < world.height):
        return {"error": "out_of_bounds"}

    is_target_blocked = any(
        isinstance(o, CellAgent) and getattr(o, "is_obstacle", False)
        for o in world.grid.get_cell_list_contents([(tx, ty)])
    )
    if is_target_blocked:
        return {"error": "blocked_target"}

    from collections import deque
    start = (cx, cy)
    goal = (tx, ty)
    q = deque([start])
    prev = {start: None}

    while q:
        x, y = q.popleft()
        if (x, y) == goal:
            break
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < world.width and 0 <= ny < world.height):
                continue
            np = (nx, ny)
            if np in prev:
                continue
            blocked = any(
                isinstance(o, CellAgent) and getattr(o, "is_obstacle", False)
                for o in world.grid.get_cell_list_contents([np])
            )
            if blocked:
                continue
            prev[np] = (x, y)
            q.append(np)

    if goal not in prev:
        return {"error": "blocked"}

    cur = goal
    while prev[cur] is not None and prev[cur] != start:
        cur = prev[cur]
    if prev[cur] is None:
        return {"error": "blocked"}
    return {"already_at_target": False, "x": cur[0], "y": cur[1]}

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
