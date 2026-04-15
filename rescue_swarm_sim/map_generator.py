import os
from pydantic import BaseModel, Field

# Pydantic Schemas for Structured Output 
class Location(BaseModel):
    x: int = Field(description="X coordinate (0-19)")
    y: int = Field(description="Y coordinate (0-19)")

class Building(Location):
    pass

class MapBlueprint(BaseModel):
    buildings: list[Building] = Field(description="A list of specific buildings in the urban areas")
    survivors: list[Location] = Field(description="Coordinates of trapped survivors, which MUST be inside buildings")

def parse_ascii_map(file_path: str = "map.txt") -> tuple[MapBlueprint, list[dict]]:
    """Reads a valid ASCII map and natively compiles the arrays."""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    
    buildings = []
    survivors = []
    cells = []
    
    for y, line in enumerate(lines):
        for x, char in enumerate(line):
            is_ob = False
            t_type = "terrain"
            
            if char == "B":
                t_type = "building"
                buildings.append(Building(x=x, y=y))
            elif char == "S":
                t_type = "building" 
                buildings.append(Building(x=x, y=y))
                if not (x == 9 and y == 9):
                    survivors.append(Location(x=x, y=y))
            elif char == "s":
                t_type = "terrain" 
                if not (x == 9 and y == 9):
                    survivors.append(Location(x=x, y=y))
            elif char == "#":
                is_ob = True
            
            cells.append({
                "x": x, "y": y,
                "is_obstacle": is_ob,
                "terrain_type": t_type
            })
            
    blueprint = MapBlueprint(buildings=buildings, survivors=survivors)
    return blueprint, cells
