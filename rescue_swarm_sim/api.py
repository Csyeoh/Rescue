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
import requests
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

class VoiceIntelRequest(BaseModel):
    transcript: str

# Update the prompt inside the process_survivor_voice function
@app.post("/api/survivors/{survivor_id}/voice-intel")
async def process_survivor_voice(survivor_id: int, payload: VoiceIntelRequest):
    """Receives transcript, translates if necessary, and extracts structured data."""
    transcript = payload.transcript
    
    # Prompt updated to handle English, Malay, Chinese, Tamil, and Thai
    prompt = f"""
    Analyze the following survivor transmission. It may be in English, Malay, Chinese, Tamil, or Thai. 
    Translate all findings into English and extract them into a strict JSON format.

    Transmission: "{transcript}"

    IMPORTANT: "medical_needs" and "requested_supplies" MUST be lists of strings in English.

    {{
        "transcription": "{transcript}",
        "medical_needs": ["injury_in_english", "injury_in_english"],
        "requested_supplies": ["item_in_english", "item_in_english"],
        "urgency_level": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
    }}
    """

    try:
        use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
        
        if use_local:
            # --- LOCAL OFFLINE MODE (Qwen via Ollama) ---
            raw_model = os.getenv("LOCAL_MODEL", "qwen2.5-coder:7b")
            if raw_model.startswith("ollama/"):
                raw_model = raw_model.replace("ollama/", "")
                
            ollama_base = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
            
            response = requests.post(
                f"{ollama_base}/api/generate",
                json={
                    "model": raw_model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json" 
                }
            )
            
            if response.status_code != 200:
                raise Exception(f"Ollama API Error: {response.text}")
                
            raw_text = response.json().get("response", "").strip()
            
        else:
            # --- FALLBACK CLOUD MODE (Gemini text-only) ---
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            raw_text = response.text.strip()

        # Clean JSON and parse
        if raw_text.startswith("```json"):
            raw_text = raw_text.replace("```json", "").replace("```", "").strip()
        elif raw_text.startswith("```"):
            raw_text = raw_text.replace("```", "").strip()
            
        intel_data = json.loads(raw_text)
        
        return {"status": "success", "survivor_id": survivor_id, "intel": intel_data}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

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
