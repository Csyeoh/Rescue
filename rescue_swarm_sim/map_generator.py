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

class Building(Location):
    pass

class MapBlueprint(BaseModel):
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
    buildings = [{"x": b.x, "y": b.y} for b in blueprint.buildings]
    survivors_locs = {(s.x, s.y) for s in blueprint.survivors}
        
    building_map = {(b["x"], b["y"]) for b in buildings}
    
    cells = []
    
    for x in range(width):
        for y in range(height):
            
            # Base Camp
            if x == 9 and y == 9:
                cells.append({
                    "x": x, "y": y,
                    "is_obstacle": False,
                    "terrain_type": "terrain"
                })
                continue
                
            # 3. Apply Building Types
            t_type = "terrain"
            if (x, y) in building_map:
                t_type = "building"
            
            # Generate Physical Obstacles (NEVER on buildings or survivors)
            is_ob = False
            if t_type == "terrain" and (x, y) not in survivors_locs:
                is_ob = random.random() < obstacle_prob
                
            cells.append({
                "x": x, "y": y,
                "is_obstacle": is_ob,
                "terrain_type": t_type
            })
            
    return cells
