from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import simulation
import websocket_manager
from typing import Optional, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
import os
import tempfile
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

client = genai.Client()

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

@app.post("/api/survivors/{survivor_id}/voice-intel")
async def process_survivor_voice(survivor_id: int, file: UploadFile = File(...)):
    """Receives voice audio, extracts intel via Gemini, and returns structured data."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
        temp_audio.write(await file.read())
        temp_audio_path = temp_audio.name

    try:
        uploaded_file = client.files.upload(file=temp_audio_path)
        
        prompt = """
        Listen to this survivor transmission. Extract the situation into a strict JSON format:
        {
            "transcription": "exact words spoken",
            "medical_needs": ["list", "of", "injuries"],
            "requested_supplies": ["list", "of", "items"],
            "urgency_level": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
        }
        """
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[uploaded_file, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text.replace("```json", "").replace("```", "").strip()
            
        intel_data = json.loads(raw_text)
        
        
        # HACKATHON NOTE: For now, we return it to the frontend. 
        # Later, inject `intel_data` into simulation.sim_world here if needed.
        
        client.files.delete(name=uploaded_file.name)
        return {"status": "success", "survivor_id": survivor_id, "intel": intel_data}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.remove(temp_audio_path)

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
