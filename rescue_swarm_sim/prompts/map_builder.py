MAP_BUILDER_PROMPT = """
You are an expert Map Urban Planner generating a logical, random disaster map.
Design a blueprint for a 20x20 grid (x: 0-19, y: 0-19) representing the disaster zone.

SCENARIO INSPIRATION: {scenario}

REAL-WORLD LOGIC RULES:
1. Base Camp: Grid (9,9) MUST be completely empty. Do not place anything here.
2. Geography: Define 1 to 3 'hills' (peak_altitude 20.0-80.0, spread 1.5-3.0). Space them out.
3. Buildings: Place a logical number of 'single_story' (suburbs) and 'multiple_story' (downtowns) buildings to form an urban layout.
   - Do NOT just spread buildings randomly across the map. Group them locally into dense residential areas, neighborhoods, or city centers.
4. Survivors: You MUST place exactly {num_survivors} survivors. 
   - Survivors can be placed outdoors OR indoors.
   - If a survivor is placed on the EXACT same x,y coordinate as a building, they are considered trapped INSIDE the building.
   - Never put two survivors on the exact same coordinate.

5. Survivor Exclusion Zone: Survivors MUST NOT be placed in the four extreme corners of the map: (0,0), (0,19), (19,0), and (19,19).
   - Ensure x and y are strictly between 0 and 19.
"""
