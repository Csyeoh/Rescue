MAP_BUILDER_PROMPT = """
You are an expert Map Urban Planner generating a logical, structured disaster map for a drone simulation.
Design a blueprint for a 20x20 grid (x: 0-19, y: 0-19).

SCENARIO: {scenario}

CORE PLACEMENT LOGIC:
1. Central Base (9,9): MUST be completely empty terrain. Maintain a 2-cell clear buffer around it (no buildings in coordinates where x or y is 8, 9, or 10).
2. Sparse Distribution: Do not pack the map. Aim for 15-25% total building coverage. Buildings should feel like they belong to a planned area, not randomly scattered dots.
3. Road Network: To simulate a logical city/village, you MUST maintain 'empty corridors' (roads). 
   - Leave at least one row or column empty every 3 to 4 units to act as streets.
   - Buildings should line up along these imaginary streets.
4. Cluster Logic: Groups of buildings should not exceed 3x3 areas. Ensure there is at least 1-2 cells of terrain between different clusters or individual buildings.

SCENARIO GUIDELINES:
- Downtown: Focused on clusters of 'multiple_story' buildings (6-10m). Use 'Avenues' (2-cell wide empty columns/rows).
- Suburban: Mostly 'single_story' (3-5m) spaced out significantly. Each house should have terrain (yards) around it.
- Industrial: 2 or 3 large isolated clusters of buildings near the edges, leaving the center mostly clear terrain.
- Mountain Outpost: Buildings should follow the 'topography' anchors. Place buildings on similar altitudes to simulate tiered slopes.
- Coastal: Buildings should be clustered away from the lowest altitude points (the water/shore).

DATA REQUIREMENTS:
- Topography: Define 2 to 4 'topography' anchor points. Use 'base_altitude' (1.0 to 100.0) and 'spread' (10.0-30.0) to create slopes or flat zones.
- Buildings: Assigned 'single_story' or 'multiple_story' with a specific `height` (meters).
- Survivors: Place exactly {num_survivors} survivors. 90% should be inside buildings (same x,y as a building).

Ensure all coordinates are strictly integers 0-19.
"""
