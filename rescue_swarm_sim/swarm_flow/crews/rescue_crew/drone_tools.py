import math
import json
import db

def _bearing(ox, oy, tx, ty) -> float:
    """Compass bearing in degrees from (ox,oy) to (tx,ty). 0=North(+y), 90=East(+x)."""
    dx = tx - ox
    dy = ty - oy
    angle = math.degrees(math.atan2(dx, dy)) % 360
    return round(angle, 1)

def get_navigation_step(drone_id: str, target_x: float, target_y: float) -> dict:
    """
    Calculates the optimal next step (dx, dy) to reach a target coordinate.
    Maximum step distance is 1.0 units. 
    Includes basic obstacle avoidance based on known/detected obstacles.
    Returns: {"dx": float, "dy": float, "bearing": float, "arrived": bool}
    """
    conn = db.get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT x, y FROM drones WHERE id=?", (drone_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"error": "drone not found"}
    cx, cy = row
    
    # Pre-load known obstacles and buildings
    cursor.execute("SELECT x, y FROM obstacles")
    obstacles = cursor.fetchall()
    cursor.execute("SELECT x, y FROM buildings")
    buildings = cursor.fetchall()
    blockers = obstacles + buildings
    conn.close()
    
    # 1. Calculate ideal vector
    tx, ty = target_x, target_y
    vx, vy = tx - cx, ty - cy
    dist = math.hypot(vx, vy)
    
    # 0.5 unit tolerance for arrival
    if dist <= 0.5:
        return {
            "dx": 0.0, 
            "dy": 0.0, 
            "bearing": 0.0, 
            "arrived": True,
            "summary": f"Target reached within 0.5 unit radius (current distance: {round(dist, 2)})."
        }
        
    # Standardize to 1.0 max step
    step_mag = min(1.0, dist)
    ux, uy = vx / dist, vy / dist
    
    # 2. Obstacle Avoidance (Check if direct path is blocked)
    def is_blocked(dx, dy):
        check_dist = math.hypot(dx, dy)
        if check_dist == 0: return False
        n_ux, n_uy = dx / check_dist, dy / check_dist
        
        for d in [check_dist * 0.5, check_dist]:
            px, py = cx + n_ux * d, cy + n_uy * d
            for ox, oy in blockers:
                if math.hypot(px - ox, py - oy) < 0.25:
                    return True
        return False

    best_dx, best_dy = ux * step_mag, uy * step_mag
    if is_blocked(best_dx, best_dy):
        found_path = False
        for offset in [15, -15, 30, -30, 45, -45, 60, -60, 75, -75, 90, -90]:
            rad = math.radians(offset)
            nx = ux * math.cos(rad) - uy * math.sin(rad)
            ny = ux * math.sin(rad) + uy * math.cos(rad)
            
            if not is_blocked(nx * step_mag, ny * step_mag):
                best_dx, best_dy = nx * step_mag, ny * step_mag
                found_path = True
                break
        
        if not found_path:
            return {"dx": 0.0, "dy": 0.0, "bearing": 0.0, "arrived": False, "summary": "STUCK: Direct path and alternatives blocked by obstacles."}

    new_bearing = math.degrees(math.atan2(best_dx, best_dy)) % 360
    return {
        "dx": round(best_dx, 3),
        "dy": round(best_dy, 3),
        "bearing": round(new_bearing, 1),
        "arrived": False,
        "summary": f"Calculated step towards ({round(tx,1)}, {round(ty,1)}) | dx: {round(best_dx,2)}, dy: {round(best_dy,2)}"
    }
