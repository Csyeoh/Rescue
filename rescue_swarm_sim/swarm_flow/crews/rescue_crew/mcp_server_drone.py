import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from fastmcp import FastMCP
import json
import math
import time
import random
import db

mcp = FastMCP("DroneSwarm")


# ─────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────────────────────────────────────

def _bearing(ox, oy, tx, ty) -> float:
    """Compass bearing in degrees from (ox,oy) to (tx,ty). 0=North(+y), 90=East(+x)."""
    dx = tx - ox
    dy = ty - oy
    angle = math.degrees(math.atan2(dx, dy)) % 360
    return round(angle, 1)


def _ray_occluded(ox, oy, tx, ty, blockers: set, step=0.25) -> bool:
    """
    Walk a ray from (ox,oy) towards (tx,ty) in small steps.
    Return True if the ray passes within 0.5 units of any blocker center.
    """
    dist = math.hypot(tx - ox, ty - oy)
    if dist == 0:
        return False
    ux = (tx - ox) / dist
    uy = (ty - oy) / dist
    d = step
    while d < dist - step:
        px, py = ox + ux * d, oy + uy * d
        for (ax, ay) in blockers:
            if math.hypot(px - ax, py - ay) < 0.5:
                return True
        d += step
    return False


def _angle_in_arc(bearing: float, center_deg: float, arc_deg: float) -> bool:
    """Check if a bearing falls inside a symmetric arc [center - arc/2, center + arc/2]."""
    half = arc_deg / 2.0
    diff = (bearing - center_deg + 180) % 360 - 180   # normalise to [-180, 180]
    return abs(diff) <= half


# ─────────────────────────────────────────────────────────────────────────────
# Tools
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_drone_context(drone_id: str) -> dict:
    """
    Returns live telemetry and immediate visual surroundings for a drone:
    - pos: current continuous-space position {x, y}
    - battery: remaining battery %
    - status: SEARCHING | RETURNING | CHARGING | IDLE | CRASHED
    - assigned_sector: {cx, cy, radius} search zone
    - surroundings: list of entities within a 1.0 unit optical radius
    Base station is at (9.5, 9.5).
    """
    conn = db.get_db_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT x, y, battery, status, thermal_memory, assigned_sector FROM drones WHERE id=?",
        (drone_id,)
    )
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {"error": "drone not found"}

    x, y, batt, status, t_mem_raw, sector_raw = row
    cx, cy = x, y
    
    # --- Integration of Optical Scan (formerly view_surrounding) ---
    detected = []

    # Obstacles
    cursor.execute("SELECT id, x, y FROM obstacles")
    for obs_id, ox, oy in cursor.fetchall():
        dist = math.hypot(cx - ox, cy - oy)
        if dist <= 1.0:
            cursor.execute("UPDATE obstacles SET discovered=1 WHERE id=?", (obs_id,))
            detected.append({
                "type": "OBSTACLE", "distance": round(dist, 2), "angle_deg": _bearing(cx, cy, ox, oy)
            })

    # Buildings
    cursor.execute("SELECT id, x, y FROM buildings")
    for bld_id, bx, by in cursor.fetchall():
        dist = math.hypot(cx - bx, cy - by)
        if dist <= 1.0:
            cursor.execute("UPDATE buildings SET revealed=1 WHERE id=?", (bld_id,))
            detected.append({
                "type": "BUILDING", "distance": round(dist, 2), "angle_deg": _bearing(cx, cy, bx, by)
            })

    # Survivors
    cursor.execute("SELECT id, x, y FROM survivors WHERE found=0")
    for s_id, sx, sy in cursor.fetchall():
        dist = math.hypot(cx - sx, cy - sy)
        if dist <= 1.0:
            detected.append({
                "type": "SURVIVOR", "distance": round(dist, 2), "angle_deg": _bearing(cx, cy, sx, sy)
            })

    conn.commit()
    conn.close()

    sector = json.loads(sector_raw) if sector_raw else None
    return {
        "id": drone_id,
        "pos": {"x": round(x, 2), "y": round(y, 2)},
        "battery": batt,
        "status": status,
        "assigned_sector": sector,
        "thermal_memory": json.loads(t_mem_raw) if t_mem_raw else [],
        "surroundings": detected if detected else [{"type": "EMPTY", "distance": 0, "angle_deg": 0}],
        "summary": f"{drone_id} at ({round(x,1)},{round(y,1)}), battery {batt}%, status {status}. Detected {len(detected)} nearby entities (within 1.0 units)."
    }


@mcp.tool()
def mcp_get_navigation_step(drone_id: str, target_x: float, target_y: float) -> dict:
    """
    Calculates the optimal next step (dx, dy) to reach a target coordinate.
    Maximum step distance is 1.0 units. 
    Includes basic obstacle avoidance based on known/detected obstacles.
    Returns: {"dx": float, "dy": float, "bearing": float}
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
    
    if dist == 0:
        return {"dx": 0.0, "dy": 0.0, "bearing": 0.0, "summary": "Already at target."}
        
    # Standardize to 1.0 max step
    step_mag = min(1.0, dist)
    ux, uy = vx / dist, vy / dist
    
    base_angle = math.degrees(math.atan2(ux, uy)) % 360 # Compass bearing
    
    # 2. Obstacle Avoidance (Check if direct path is blocked)
    # Checks multiple points along the proposed step segment
    def is_blocked(dx, dy):
        # Ray-cast collision check (0.25 radius)
        check_dist = math.hypot(dx, dy)
        if check_dist == 0: return False
        n_ux, n_uy = dx / check_dist, dy / check_dist
        
        for d in [check_dist * 0.5, check_dist]: # Check midpoint and endpoint
            px, py = cx + n_ux * d, cy + n_uy * d
            for ox, oy in blockers:
                if math.hypot(px - ox, py - oy) < 0.25:
                    return True
        return False

    # Try different angles (sweep ±90 deg) if direct path blocked
    best_dx, best_dy = ux * step_mag, uy * step_mag
    if is_blocked(best_dx, best_dy):
        found_path = False
        # Sweep ±15, ±30, ..., ±90
        for offset in [15, -15, 30, -30, 45, -45, 60, -60, 75, -75, 90, -90]:
            rad = math.radians(offset)
            # Rotation matrix for compass bearing: 
            # Note: math.atan2 is (y,x), compass is different. 
            # Simpler to rotate base vector:
            nx = ux * math.cos(rad) - uy * math.sin(rad)
            ny = ux * math.sin(rad) + uy * math.cos(rad)
            
            if not is_blocked(nx * step_mag, ny * step_mag):
                best_dx, best_dy = nx * step_mag, ny * step_mag
                found_path = True
                break
        
        if not found_path:
            return {"dx": 0.0, "dy": 0.0, "bearing": 0.0, "summary": "STUCK: Direct path and alternatives blocked by obstacles."}

    new_bearing = math.degrees(math.atan2(best_dx, best_dy)) % 360
    return {
        "dx": round(best_dx, 3),
        "dy": round(best_dy, 3),
        "bearing": round(new_bearing, 1),
        "summary": f"Calculated step towards ({round(tx,1)}, {round(ty,1)}) | dx: {round(best_dx,2)}, dy: {round(best_dy,2)}"
    }


@mcp.tool()
def thermal_scan(drone_id: str, angle_deg: float) -> dict:
    """
    Emits a fan-shaped thermal sensor beam from the drone in a chosen degree bearing.

    HOW IT WORKS:
    - angle_deg: the centre bearing of the fan (0=North, 90=East, 180=South, 270=West).
    - Fixed Scale: radius = 6.0 units (300m), arc = 60°.
    - Signal Logic: 95% at 1.0u distance, 20% at 6.0u distance.
    - Obstacles block the heat (occlusion).
    - Detection Results: Includes a list of hits with signal strength, distance, and relative bearing.
    
    OUTPUT: {"angle_deg": float, "highest_signal": "XX%", "detections": [...]}
    """
    conn = db.get_db_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT x, y, thermal_memory FROM drones WHERE id=?", (drone_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"error": "drone not found"}
    cx, cy, t_mem_raw = row

    # Load obstacles and survivors
    cursor.execute("SELECT x, y FROM obstacles")
    obstacles = {(r[0], r[1]) for r in cursor.fetchall()}

    cursor.execute("SELECT x, y FROM survivors WHERE found=0")
    survivors = [(r[0], r[1]) for r in cursor.fetchall()]

    SCAN_RADIUS = 6.0
    ARC_DEG = 60.0
    detections = []
    highest_true_score = 0.0

    for sx, sy in survivors:
        dist = math.hypot(cx - sx, cy - sy)
        if dist > SCAN_RADIUS:
            continue

        bearing = _bearing(cx, cy, sx, sy)
        if not _angle_in_arc(bearing, angle_deg, ARC_DEG):
            continue

        # Line-of-sight occlusion check
        if _ray_occluded(cx, cy, sx, sy, obstacles):
            continue

        # Signal Formula: 95% at 1u, 20% at 6u -> 95 - (d-1)*15
        d_clamped = max(1.0, dist)
        score = 95.0 - (d_clamped - 1.0) * 15.0
        
        # Apply ±2% jitter for realism
        score += random.uniform(-2, 2)
        score = max(0, min(100, score))

        detections.append({
            "bearing": bearing,
            "distance": round(dist, 2),
            "score": score
        })
        
        if score > highest_true_score:
            highest_true_score = score

    # Process detections (Format for result)
    results = []
    for d in detections:
        results.append({
            "bearing": d["bearing"],
            "distance": d["distance"],
            "signal_strength": f"{int(d['score'])}%"
        })

    # PROBABILITY: 10% chance to generate a phantom "ghost" detection (0-30% strength)
    if random.random() < 0.1:
        p_dist = random.uniform(0.5, SCAN_RADIUS)
        # Random bearing inside the arc [angle_deg - 30, angle_deg + 30]
        p_offset = random.uniform(-ARC_DEG/2, ARC_DEG/2)
        p_bearing = (angle_deg + p_offset) % 360
        p_strength = random.randint(0, 20)
        
        results.append({
            "bearing": round(p_bearing, 1),
            "distance": round(p_dist, 2),
            "signal_strength": f"{p_strength}%"
        })
        if p_strength > highest_true_score:
            highest_true_score = p_strength

    # Overall strongest signal for quick reference
    final_score = int(highest_true_score)

    # Update thermal memory: update existing entry if at the same location (0.1 precision)
    mem = json.loads(t_mem_raw) if t_mem_raw else []
    target_x, target_y = round(cx, 1), round(cy, 1)
    
    found = False
    for entry in mem:
        if round(entry.get("x", 0), 1) == target_x and round(entry.get("y", 0), 1) == target_y:
            entry.update({
                "x": round(cx, 2),
                "y": round(cy, 2),
                "angle": angle_deg,
                "strength": f"{final_score}%",
                "timestamp": time.time(),
                "detections_count": len(results)
            })
            found = True
            break
            
    if not found:
        mem.append({
            "x": round(cx, 2), "y": round(cy, 2), 
            "angle": angle_deg, "strength": f"{final_score}%",
            "timestamp": time.time(),
            "detections_count": len(results)
        })
    
    cursor.execute("UPDATE drones SET thermal_memory=? WHERE id=?", (json.dumps(mem), drone_id))

    conn.commit()
    conn.close()

    det_count = len(results)
    summary = f"Thermal scan at {angle_deg}° (±30°): detected {det_count} survivor(s). Peak signal {final_score}%."
    if det_count == 0:
        summary = f"Thermal scan at {angle_deg}° (±30°): no survivors detected."

    return {
        "angle_deg": angle_deg,
        "highest_signal": f"{final_score}%",
        "detections": results,
        "summary": summary
    }


@mcp.tool()
def mcp_check_task_viability(drone_id: str, target_x: float, target_y: float) -> dict:
    """
    Estimates whether the drone has enough battery to fly to (target_x, target_y)
    and return safely to base at (9.5, 9.5).
    Uses Euclidean distance. Battery cost = 2 per unit of movement.
    Returns: {viable: bool, required_battery: float, current_battery: int}
    """
    conn = db.get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT x, y, battery FROM drones WHERE id=?", (drone_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"error": "drone not found"}

    cx, cy, battery = row
    base_x, base_y = 9.5, 9.5

    d_to_target = math.hypot(target_x - cx, target_y - cy)
    d_to_base   = math.hypot(base_x - target_x, base_y - target_y)

    # 2 battery per unit moved, +10 safety buffer
    required = (d_to_target + d_to_base) * 2.0 + 10.0

    viable = battery >= required
    return {
        "viable": viable,
        "required_battery": round(required, 1),
        "current_battery": battery,
        "summary": f"{'Viable' if viable else 'Not viable'}: needs {round(required,1)}% battery, has {battery}%."
    }


if __name__ == "__main__":
    mcp.run()
