MAP_BUILDER_PROMPT = """
You are an expert Map Urban Planner generating a logical, random disaster map.
Design a blueprint for a 20x20 grid (x: 0-19, y: 0-19) representing the disaster zone.

SCENARIO: {scenario}

REAL-WORLD LOGIC RULES:
1. Base Camp: Grid (9,9) MUST be completely empty. Do not place anything here.
2. Topography: Define 1 to 4 'topography' anchor points that represent the semantic topography of the scenario.
   - For example, if it's a coastal scenario, you might have a high-altitude anchor inland (e.g., 80.0) and a low-altitude anchor near the coast (e.g., 5.0).
   - Set 'base_altitude' (between 1.0 and 100.0) and 'spread' (e.g. 10.0-30.0) thoughtfully to shape the land organically.
3. Buildings: Place a logical number of 'single_story' (suburbs) and 'multiple_story' (downtowns) buildings to form an urban layout.
   - Based on the given scenario, either group them locally into dense residential areas or spread them out.
   - Every building MUST have a logical `height` assigned natively in the structured output.
   - Single-story buildings must be between 3.0 and 5.0 meters.
   - Multi-story buildings must be between 6.0 and 10.0 meters.
4. Survivors: You MUST place exactly {num_survivors} survivors. 
   - Survivors should mostly stay indoors (inside buildings), and rare cases (10%) outdoors.
   - If a survivor is placed on the EXACT same x,y coordinate as a building, they are considered trapped INSIDE the building.
   - Never put two survivors on the exact same coordinate.

Ensure x and y are strictly between 0 and 19.
"""
