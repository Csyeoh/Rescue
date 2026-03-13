import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

def generate_disaster_blueprint(scenario: str, num_survivors: int, flood_type: str):
    """Uses Gemini to design a logical, realistic disaster zone based on specific flood physics."""
    
    client = genai.Client()

    prompt = f"""
    You are an expert Urban Planner and Search & Rescue Commander simulating a severe flood.
    Design a blueprint for a 20x20 grid (x: 0-19, y: 0-19) representing the disaster zone.
    
    SCENARIO: {scenario}
    FLOOD TYPE: {flood_type}
    
    REAL-WORLD LOGIC RULES:
    1. Base Camp: Grid (9,9) MUST be completely empty. Do not place anything here.
    2. Geography: Define 1 to 3 'hills' (peak_altitude 20.0-80.0, spread 1.5-3.0). Define 1 to 3 'city_centers'. Space your 'city_centers' away from your 'hills'.
    3. Flood Evacuation (Survivors): You MUST place exactly {num_survivors} survivors. 
       - Behavior A (Trapped): Place a cluster within a 1-grid radius of a 'city_center'.
       - Behavior B (Evacuees): Place the remaining cluster within a 1-grid radius of a 'hill' peak.
       - Grouping: Keep survivors in tight, adjacent clusters. Never put two on the exact same coordinate.
    4. Weather Physics (1 tick = 1 second):
       - 'initial_water_level': Pick a float between 0.0 and 1.5.
       - 'initial_water_speed': You MUST set this speed based on the FLOOD TYPE using this real-world scaling:
           * River (Monsoon) Flood: Extremely gradual. Pick between 0.0005 and 0.001 m/tick.
           * Flash Flood: Fast and dangerous. Pick between 0.002 and 0.005 m/tick.
           * Storm Surge: Rapid coastal wall of water. Pick between 0.010 and 0.020 m/tick.
           * Dam Break: Instantaneous catastrophe. Pick between 0.050 and 0.100 m/tick.
    
    Return ONLY valid JSON matching the schema.
    """

    schema = {
        "type": "OBJECT",
        "properties": {
            "initial_water_level": {"type": "NUMBER"},
            "initial_water_speed": {"type": "NUMBER"},
            "city_centers": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {"x": {"type": "INTEGER"}, "y": {"type": "INTEGER"}, "description": {"type": "STRING"}}
                }
            },
            "hills": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {"x": {"type": "INTEGER"}, "y": {"type": "INTEGER"}, "peak_altitude": {"type": "NUMBER"}, "spread": {"type": "NUMBER"}}
                }
            },
            "survivors": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {"x": {"type": "INTEGER"}, "y": {"type": "INTEGER"}}
                }
            }
        },
        "required": ["initial_water_level", "initial_water_speed", "city_centers", "hills", "survivors"]
    }

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema, temperature=0.3),
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"AI Generation Failed: {e}")
        return None