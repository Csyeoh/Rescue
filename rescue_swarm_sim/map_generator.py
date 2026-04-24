import os
import random
from pydantic import BaseModel, Field

# Pydantic Schemas for Structured Output 
class Location(BaseModel):
    x: int = Field(description="X coordinate (0-19)")
    y: int = Field(description="Y coordinate (0-19)")

def parse_ascii_map(file_path: str = "map.txt") -> dict:
    """Reads a valid ASCII map and natively compiles the arrays."""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    
    building_heights = [0.9, 1.5, 2.9]
    obstacle_heights = [0.4, 1.1, 1.8]

    buildings = []
    survivors = []
    obstacles = []
    bases = []
    
    for y, line in enumerate(lines):
        for x, char in enumerate(line):
            if char == "B":
                buildings.append({"x": x, "y": y, "height": building_heights[(x + y) % 3]})
            elif char == "S":
                buildings.append({"x": x, "y": y, "height": building_heights[(x + y) % 3]})
                if not (x == 9 and y == 9):
                    survivors.append({"x": x, "y": y})
            elif char == "s":
                if not (x == 9 and y == 9):
                    survivors.append({"x": x, "y": y})
            elif char == "#":
                obstacles.append({"x": x, "y": y, "height": obstacle_heights[(x * 3 + y) % 3]})
            elif char == "@":
                bases.append({"x": x, "y": y})
            
    return {"buildings": buildings, "survivors": survivors, "obstacles": obstacles, "bases": bases}
