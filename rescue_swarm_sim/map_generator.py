import random
import math
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv

from prompts.map_builder import MAP_BUILDER_PROMPT

load_dotenv()

# Pydantic Schemas for Structured Output 
class Location(BaseModel):
    x: int = Field(description="X coordinate (0-19)")
    y: int = Field(description="Y coordinate (0-19)")

class Hill(Location):
    peak_altitude: float = Field(description="Peak altitude in meters (20.0 to 80.0)")
    spread: float = Field(description="How fast the altitude drops off (1.5 to 3.0)")

class Building(Location):
    type: str = Field(description="'single_story' or 'multiple_story'")

class MapBlueprint(BaseModel):
    hills: list[Hill] = Field(description="1 to 3 hills on the map")
    buildings: list[Building] = Field(description="A list of specific buildings in the urban areas")
    survivors: list[Location] = Field(description="Coordinates of trapped survivors, which MUST be inside buildings")

# Generate a Semantic Blueprint
def generate_semantic_blueprint(scenario: str, num_survivors: int) -> MapBlueprint | None:
    """Uses Gemini to design a logical, realistic disaster zone using Pydantic structured output."""
    client = genai.Client()

    prompt = MAP_BUILDER_PROMPT.format(scenario=scenario, num_survivors=num_survivors)

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=MapBlueprint,
                temperature=0.3
            ),
        )
        blueprint = MapBlueprint.model_validate_json(response.text)
        
        # FAIL-SAFE: Filter out any survivors accidentally placed within 2-cell buffer of base (9,9)
        filtered_survivors = [
            s for s in blueprint.survivors 
            if not (s.x == 9 and s.y == 9)
        ]
        blueprint.survivors = filtered_survivors
        
        return blueprint
    except Exception as e:
        print(f"AI Generation Failed: {e}")
        return None

# Algorithm for Building the Map
def build_terrain_matrix(blueprint: MapBlueprint, obstacle_prob: float, width: int = 20, height: int = 20) -> list[dict]:   
    hills = [{"x": h.x, "y": h.y, "peak_altitude": h.peak_altitude, "spread": h.spread} for h in blueprint.hills]
    buildings = [{"x": b.x, "y": b.y, "type": b.type} for b in blueprint.buildings]
    survivors_locs = {(s.x, s.y) for s in blueprint.survivors}
        
    building_map = {(b["x"], b["y"]): b["type"] for b in buildings}
    
    cells = []
    
    for x in range(width):
        for y in range(height):
            
            # Base Camp
            if x == 9 and y == 9:
                cells.append({
                    "x": x, "y": y,
                    "altitude": 150.0,
                    "is_obstacle": False,
                    "terrain_type": "terrain"
                })
                continue
                
            # 2. Base altitude from Hills
            altitude = 1.0 
            for hill in hills:
                hx, hy = hill["x"], hill["y"]
                h_max = hill.get("peak_altitude", 40.0)
                h_spread = hill.get("spread", 1.5)
                
                dist = math.sqrt((x - hx)**2 + (y - hy)**2)
                hill_height = h_max - (dist * h_spread)
                if hill_height > altitude:
                    altitude = hill_height
                    
            altitude += random.uniform(-0.5, 0.5)
            altitude = max(1.0, altitude) 
            
            # 3. Apply Building Types & Heights
            t_type = "terrain"
            if (x, y) in building_map:
                b_type = building_map[(x, y)]
                if b_type == "multiple_story":
                    t_type = "multiple_story"
                    altitude += random.uniform(6.0, 10.0)
                else:
                    t_type = "single_story"
                    altitude += random.uniform(3.0, 5.0)
            
            # Generate Physical Obstacles (NEVER on buildings or survivors)
            is_ob = False
            if t_type == "terrain" and (x, y) not in survivors_locs:
                is_ob = random.random() < obstacle_prob
                
            cells.append({
                "x": x, "y": y,
                "altitude": altitude,
                "is_obstacle": is_ob,
                "terrain_type": t_type
            })
            
    return cells
