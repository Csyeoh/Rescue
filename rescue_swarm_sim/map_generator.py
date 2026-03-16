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
    type: str = Field(description="'single_story' or 'multiple_story'")
    height: float = Field(description="Building height in meters, single story (3.0-5.0), multi-story (6.0-10.0)", ge=3.0, le=10.0)

class TopographyRegion(BaseModel):
    center_x: int = Field(description="Center X coordinate of this region (0-19)")
    center_y: int = Field(description="Center Y coordinate of this region (0-19)")
    base_altitude: float = Field(description="Base ground altitude around this center (between 1.0 and 100.0)")
    spread: float = Field(description="How fast the terrain altitude blends from this center, larger means it covers more area (e.g., 10.0 to 30.0)")

class MapBlueprint(BaseModel):
    topography: list[TopographyRegion] = Field(description="1 to 4 topographic anchor points defining the semantic layout of the land (e.g. hills, valleys, coast)")
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
        return MapBlueprint.model_validate_json(response.text)
    except Exception as e:
        print(f"AI Generation Failed: {e}")
        return None

# Algorithm for Building the Map
def build_terrain_matrix(blueprint: MapBlueprint, obstacle_prob: float, width: int = 20, height: int = 20) -> list[dict]:   
    buildings = [{"x": b.x, "y": b.y, "type": b.type, "height": b.height} for b in blueprint.buildings]
    survivors_locs = {(s.x, s.y) for s in blueprint.survivors}
        
    building_map = {(b["x"], b["y"]): b for b in buildings}
    
    cells = []
    
    # Pre-compute topography parameters to avoid redundant calculations
    regions = []
    if blueprint.topography:
        for r in blueprint.topography:
            spread_sq = max(0.1, r.spread) ** 2
            regions.append((r.center_x, r.center_y, r.base_altitude, 1.0 / spread_sq))

    # Pre-compute and smooth terrain altitude
    base_terrain = [[5.0] * height for _ in range(width)]
    for x in range(width):
        for y in range(height):
            if regions:
                weighted_altitude = 0.0
                total_weight = 0.0
                for cx, cy, base_alt, inv_spread_sq in regions:
                    dist_sq = (x - cx) ** 2 + (y - cy) ** 2
                    weight = 1.0 / (dist_sq * inv_spread_sq + 0.1)
                    weighted_altitude += base_alt * weight
                    total_weight += weight
                altitude = weighted_altitude / total_weight
            else:
                altitude = 50.0 + 30.0 * math.sin(x * 0.3) * math.cos(y * 0.3)
            
            base_terrain[x][y] = max(1.0, min(100.0, altitude + random.uniform(-0.5, 0.5)))
            
    # Apply 3x3 smoothing pass with optimized loop bounds
    smoothed_terrain = [[5.0] * height for _ in range(width)]
    for x in range(width):
        nx_min = max(0, x - 1)
        nx_max = min(width, x + 2)
        for y in range(height):
            ny_min = max(0, y - 1)
            ny_max = min(height, y + 2)
            
            alt_sum = 0.0
            neighbors = 0
            # Direct slice iteration is faster and skips the within-loop bounds checks
            for nx in range(nx_min, nx_max):
                for ny in range(ny_min, ny_max):
                    alt_sum += base_terrain[nx][ny]
                    neighbors += 1
            smoothed_terrain[x][y] = alt_sum / neighbors

    for x in range(width):
        for y in range(height):
            
            # Base Camp
            if x == 9 and y == 9:
                cells.append({
                    "x": x, "y": y,
                    "altitude": 10.0,
                    "building_height": 0.0,
                    "is_obstacle": False,
                    "terrain_type": "terrain"
                })
                continue
                
            # Use smoothed altitude
            altitude = smoothed_terrain[x][y]
            
            # 3. Apply Building Types & Heights
            t_type = "terrain"
            b_height = 0.0
            if (x, y) in building_map:
                b = building_map[(x, y)]
                b_type = b["type"]
                b_height = b["height"]
                if b_type == "multiple_story":
                    t_type = "multiple_story"
                else:
                    t_type = "single_story"
                altitude += b_height
                altitude = min(100.0, altitude) # keep bounded up to 100
            
            # Generate Physical Obstacles (NEVER on buildings or survivors)
            is_ob = False
            if t_type == "terrain" and (x, y) not in survivors_locs:
                is_ob = random.random() < obstacle_prob
                
            cells.append({
                "x": x, "y": y,
                "altitude": altitude,
                "building_height": b_height,
                "is_obstacle": is_ob,
                "terrain_type": t_type
            })
            
    return cells
