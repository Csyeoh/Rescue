import json

def generate_global_map(cursor):
    """
    Generates a 20x20 ASCII map for the dispatcher.
    Legend:
    . = Revealed/Searched
    B = Unrevealed Building (High Priority)
    U = Unrevealed Terrain
    A = Unrevealed but Assigned
    D1 = Drone ID at location
    (D1,D2) = Multiple drones at location
    """
    # 1. Fetch Cells
    cursor.execute("SELECT x, y, revealed, assigned_to, terrain_type FROM cells")
    cells = {}
    for x, y, rev, asgn, t_type in cursor.fetchall():
        cells[(x, y)] = {"revealed": rev, "assigned_to": asgn, "type": t_type}

    # 2. Fetch Drones
    cursor.execute("SELECT id, x, y FROM drones")
    drones_at = {}
    for d_id, dx, dy in cursor.fetchall():
        if (dx, dy) not in drones_at:
            drones_at[(dx, dy)] = []
        drones_at[(dx, dy)].append(d_id.replace("drone_", "D"))

    # 3. Build ASCII
    output = "CURRENT GRID LAYOUT (20x20)\n"
    output += ". = Searched, B = Unrevealed Building, U = Unrevealed Terrain, A = Assigned\n\n"
    
    for y in range(20):
        row_str = f"Row {y:02d}: "
        row_parts = []
        for x in range(20):
            cell = cells.get((x, y))
            drones = drones_at.get((x, y), [])

            char = "?"
            if drones:
                if len(drones) > 1:
                    char = f"({','.join(drones)})"
                else:
                    char = drones[0]
            else:
                if not cell:
                    char = "U"
                elif cell["revealed"]:
                    char = "." # Any revealed/searched cell is now "."
                else:
                    if cell["assigned_to"]:
                        char = "A"
                    else:
                        char = "B" if cell["type"] == "building" else "U"
            
            row_parts.append(char)
        
        row_str += " ".join(row_parts)
        output += row_str + "\n"
    
    return output

def generate_local_map(cursor, drone_id, assigned_cells):
    """
    Generates a localized ASCII map for a specific drone's assigned cells.
    Includes 1-cell padding around the assigned area for navigation context.
    """
    if not assigned_cells:
        return "NO CELLS ASSIGNED", False

    # 1. Determine bounding box for the view window
    try:
        pts = assigned_cells
        pts_set = set(tuple(p) for p in pts)
        
        # Include drone position in bounding box to ensure it's always visible
        cursor.execute("SELECT x, y FROM drones WHERE id=?", (drone_id,))
        drone_pos = cursor.fetchone()
        dx, dy = drone_pos if drone_pos else (9, 9)
        
        all_x = [p[0] for p in pts] + [dx]
        all_y = [p[1] for p in pts] + [dy]
        
        # Add 1-cell padding
        min_x = max(0, min(all_x) - 1)
        max_x = min(19, max(all_x) + 1)
        min_y = max(0, min(all_y) - 1)
        max_y = min(19, max(all_y) + 1)
    except Exception:
        return "ERROR PARSING ASSIGNED CELLS", False

    # 2. Fetch all cells in the window
    cursor.execute("SELECT x, y, revealed, is_obstacle, terrain_type, assigned_to FROM cells WHERE x >= ? AND x <= ? AND y >= ? AND y <= ?", 
                   (min_x, max_x, min_y, max_y))
    cells = {(r[0], r[1]): {"revealed": r[2], "obstacle": r[3], "type": r[4], "assigned_to": r[5]} for r in cursor.fetchall()}

    output = f"LOCAL SECTOR MAP FOR {drone_id.upper()}\n"
    output += "@ = You, . = Revealed, B = Building, U = Your Target, # = Obstacle, ? = Unrevealed Other\n\n"

    for y in range(min_y, max_y + 1):
        row_parts = []
        for x in range(min_x, max_x + 1):
            cell = cells.get((x, y))
            char = "?"
            
            if x == dx and y == dy:
                char = "@"
            elif not cell:
                char = "?"
            elif cell["revealed"]:
                if cell["obstacle"]: char = "#"
                elif cell["type"] == "building": char = "B"
                else: char = "."
            else:
                # Unrevealed cell
                if (x, y) in pts_set:
                    char = "U" # Assigned to THIS drone
                elif cell["assigned_to"]:
                    char = "A" # Assigned to ANOTHER drone
                else:
                    char = "?" # Unassigned and unrevealed
            row_parts.append(char)
        output += " ".join(row_parts) + "\n"

    is_inside = (dx, dy) in pts_set
    return output, is_inside
