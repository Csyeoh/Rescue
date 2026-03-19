from fastapi import FastAPI, WebSocket, WebSocketDisconnect, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import database
import simulation
from typing import Optional, Dict, Any, List
import autopilot
import asyncio

# Initialize the API
app = FastAPI(title="Rescue Swarm API")

database.init_db()

# Fix CORS so your Next.js frontend can fetch data without browser errors
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 1. PYDANTIC MODELS (Validates UI Inputs)
# ==========================================
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
    conn = database._connect()
    conn.execute("DELETE FROM drone_waypoints")
    conn.execute("DELETE FROM drone_zones")
    conn.execute("DELETE FROM cell_weights")
    conn.commit()
    conn.close()
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
    # Fixed: Removed Optional to ensure config is parsed correctly
    cfg_dict = config.model_dump() if hasattr(config, 'model_dump') else config.dict()
    
    simulation.initialize_world(cfg_dict, start_sim=True)
        
    return {
        "status": "success", 
        "message": "Swarm Heartbeat Active."
    }

# ==========================================
# 3. GET ENDPOINT (Broadcasts the Live World)
# ==========================================
@app.get("/api/state")
@app.get("/state")
def get_world_state():
    """Returns the live state using a.is_scanned to drive the Fog of War."""
    try:
        conn = sqlite3.connect(database.DB_NAME, timeout=10.0)
        cursor = conn.cursor()
        
        # 1. Fetch live drone data
        cursor.execute("SELECT drone_id, x, y, battery FROM drones")
        drones = [{"id": row[0], "x": row[1], "y": row[2], "battery": row[3]} for row in cursor.fetchall()]
        
        # 2. Fetch survivor data
        cursor.execute("SELECT survivor_id, x, y, is_discovered FROM survivors")
        survivors = [{"id": row[0], "x": row[1], "y": row[2], "discovered": bool(row[3])} for row in cursor.fetchall()]
        
        # 3. Fetch terrain data (FIX: Using a.is_scanned for 'discovered' flag)
        try:
            cursor.execute('''
                SELECT q.x, q.y, q.altitude, q.is_obstacle, q.terrain_type, a.obstacle_discovered, a.is_scanned 
                FROM question_plane q
                JOIN answer_plane a ON q.x = a.x AND q.y = a.y
            ''')
            terrain = [
                {
                    "x": row[0], "y": row[1], "altitude": row[2], 
                    "is_obstacle": bool(row[3]), "terrain_type": row[4], 
                    "obstacle_discovered": bool(row[5]),
                    "discovered": bool(row[6]) # Dynamic Fog of War
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

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await asyncio.sleep(0.1)
        while True:
            try:
                state = get_world_state()
                # Fixed: Wrapped state in type: tick_update to satisfy UI requirements
                await websocket.send_json({"type": "tick_update", "payload": state})
            except RuntimeError as e:
                break 
            except Exception as e:
                if "close message" in str(e):
                    break
                print(f"WS Loop Error: {e}")
            
            await asyncio.sleep(0.5) 
    except WebSocketDisconnect:
        pass 
    finally:
        try:
            manager.disconnect(websocket)
        except:
            pass

# ==========================================
# 4. MCP ENDPOINTS (Bridge to Simulation)
# ==========================================
# Fixed: Removed prefix here to allow double-routing in app.include_router
mcp_router = APIRouter()

@mcp_router.get("/drones")
def get_drones():
    conn = database._connect()
    cursor = conn.cursor()
    cursor.execute("SELECT drone_id FROM drones")
    drones = [row[0] for row in cursor.fetchall()]
    conn.close()
    return drones

@mcp_router.get("/drone/{drone_id}/battery")
def get_drone_battery(drone_id: str):
    conn = database._connect()
    cursor = conn.cursor()
    cursor.execute("SELECT battery FROM drones WHERE drone_id=?", (drone_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else -1

@mcp_router.get("/drone/{drone_id}/pos")
def get_drone_pos(drone_id: str):
    conn = database._connect()
    cursor = conn.cursor()
    cursor.execute("SELECT x, y FROM drones WHERE drone_id=?", (drone_id,))
    row = cursor.fetchone()
    conn.close()
    return {"x": row[0], "y": row[1]} if row else {"error": "not found"}

@mcp_router.get("/drone/{drone_id}/status")
def get_drone_status(drone_id: str):
    conn = database._connect()
    cursor = conn.cursor()
    cursor.execute("SELECT health_status FROM drones WHERE drone_id=?", (drone_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else "IDLE"

@mcp_router.get("/drone/{drone_id}/waypoints")
def get_drone_waypoints(drone_id: str):
    conn = database._connect()
    cursor = conn.cursor()
    cursor.execute("SELECT x, y FROM drone_waypoints WHERE drone_id=? AND is_done=0 ORDER BY seq ASC", (drone_id,))
    wps = cursor.fetchall()
    conn.close()
    return wps

@mcp_router.get("/drone/{drone_id}/thermal")
def get_drone_thermal(drone_id: str):
    conn = database._connect()
    cursor = conn.cursor()
    cursor.execute("SELECT x, y FROM survivors WHERE is_discovered=1")
    survivors = cursor.fetchall()
    conn.close()
    return survivors

@mcp_router.get("/drone/{drone_id}/scan_adjacent")
def scan_adjacent(drone_id: str):
    conn = database._connect()
    cursor = conn.cursor()
    cursor.execute("SELECT x, y FROM drones WHERE drone_id=?", (drone_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"error": "drone not found"}
    
    cx, cy = row
    neighbors = {"up": (cx, cy-1), "down": (cx, cy+1), "left": (cx-1, cy), "right": (cx+1, cy)}
    results = {}
    
    with database.DB_WRITE_LOCK:
        for direction, (nx, ny) in neighbors.items():
            if not (0 <= nx < 20 and 0 <= ny < 20):
                results[direction] = "out_of_bounds"
                continue
            
            cursor.execute("SELECT is_obstacle FROM question_plane WHERE x=? AND y=?", (nx, ny))
            obs_row = cursor.fetchone()
            is_obs = bool(obs_row[0]) if obs_row else False
            
            if is_obs:
                cursor.execute("UPDATE answer_plane SET obstacle_discovered=1, is_scanned=1 WHERE x=? AND y=?", (nx, ny))
                results[direction] = "obstacle"
                if simulation.sim_world:
                    for agent in simulation.sim_world.grid.get_cell_list_contents([(nx, ny)]):
                        if isinstance(agent, simulation.TerrainAgent):
                            agent.obstacle_discovered = True
            else:
                cursor.execute("UPDATE answer_plane SET is_scanned=1 WHERE x=? AND y=?", (nx, ny))
                results[direction] = "clear"
            
            cursor.execute("SELECT is_discovered FROM survivors WHERE x=? AND y=?", (nx, ny))
            surv_row = cursor.fetchone()
            if surv_row:
                results[f"{direction}_thermal"] = True
            else:
                results[f"{direction}_thermal"] = False
        conn.commit()
    conn.close()
    return results

@mcp_router.get("/drone/{drone_id}/step_towards")
def step_towards(drone_id: str, tx: int, ty: int):
    conn = database._connect()
    cursor = conn.cursor()
    cursor.execute("SELECT x, y FROM drones WHERE drone_id=?", (drone_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"error": "drone not found"}
    
    start = (row[0], row[1])
    target = (tx, ty)
    
    cursor.execute("SELECT x, y FROM answer_plane WHERE obstacle_discovered=1")
    obstacles = {(r[0], r[1]) for r in cursor.fetchall()}
    conn.close()
    
    path = autopilot._a_star_path(start, target, obstacles)
    if path:
        return {"x": path[0][0], "y": path[0][1], "already_at_target": False}
    elif start == target:
        return {"x": start[0], "y": start[1], "already_at_target": True}
    else:
        return {"error": "unreachable"}

@mcp_router.get("/drone/{drone_id}/thermal_scan")
def thermal_scan_api(drone_id: str):
    return simulation.resolve_intent({"drone_id": drone_id, "action": "THERMAL_SCAN"})

class DroneIntentPayload(BaseModel):
    drone_id: str
    action: str
    target_x: Optional[int] = None
    target_y: Optional[int] = None
    rationale: Optional[str] = None
    new_status: Optional[str] = None

@mcp_router.post("/intent")
def post_intent(payload: DroneIntentPayload):
    return simulation.resolve_intent(payload.model_dump() if hasattr(payload, 'model_dump') else payload.dict())

@mcp_router.get("/mission_data")
def get_mission_data():
    conn = database._connect()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), SUM(is_discovered) FROM survivors")
    row = cursor.fetchone()
    total = row[0] if row else 0
    found = row[1] if row and row[1] is not None else 0
    conn.close()
    return {"total_survivors": total, "found_survivors": found, "mission_status": "ACTIVE" if found < total else "COMPLETE"}

# Implementation of double-routing to support both /api/... and /api/mcp/...
app.include_router(mcp_router, prefix="/api")
app.include_router(mcp_router, prefix="/api/mcp")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
