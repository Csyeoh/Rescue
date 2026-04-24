import os
from pydantic import BaseModel, Field

# Pydantic Schemas for Structured Output 
class Location(BaseModel):
    x: int = Field(description="X coordinate (0-19)")
    y: int = Field(description="Y coordinate (0-19)")

def parse_ascii_map(file_path: str = "map.txt") -> dict:
    """Reads a valid ASCII map and natively compiles the arrays."""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    
    buildings = []
    survivors = []
    obstacles = []
    bases = []
    
    for y, line in enumerate(lines):
        for x, char in enumerate(line):
            if char == "B":
                buildings.append({"x": x, "y": y})
            elif char == "S":
                buildings.append({"x": x, "y": y})
                if not (x == 9 and y == 9):
                    survivors.append({"x": x, "y": y})
            elif char == "s":
                if not (x == 9 and y == 9):
                    survivors.append({"x": x, "y": y})
            elif char == "#":
                obstacles.append({"x": x, "y": y})
            elif char == "@":
                bases.append({"x": x, "y": y})
            
    return {"buildings": buildings, "survivors": survivors, "obstacles": obstacles, "bases": bases}
