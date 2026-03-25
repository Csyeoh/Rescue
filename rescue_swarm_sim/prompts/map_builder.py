MAP_BUILDER_PROMPT = """
You are an expert Map Urban Planner generating a logical, structured disaster map for a drone simulation.
Design a blueprint for a 20x20 grid (x: 0-19, y: 0-19).

SCENARIO INSPIRATION: {scenario}

CORE PLACEMENT LOGIC:
1. Central Base (9,9): MUST be completely empty terrain, do not place anything here. Maintain a 2-cell clear buffer around it (no buildings in coordinates where x or y is 8, 9, or 10).
2. Sparse Distribution: Do not pack the map. Aim for 15-25% total building coverage. Buildings should feel like they belong to a planned area, not randomly scattered dots.
3. Road Network: To simulate a logical city/village, you MUST maintain 'empty corridors' (roads). 
   - Leave at least one row or column empty every 3 to 4 units to act as streets.
   - Buildings should line up along these imaginary streets.
4. Cluster Logic: Groups of buildings should not exceed 3x3 areas. Ensure there is at least 1-2 cells of terrain between different clusters or individual buildings.
5. Survivor Placement: Place survivors evenly across the map. majority should be inside the building (80 - 90%) while minority will be outside, but ensure NONE are placed at the Central Base (9,9).
6. Ensure all coordinates are strictly integers 0-19.
7. Total Survivors: Place exactly {num_survivors} survivors. Ensure they are distributed logically across different clusters.
"""
