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
    - status: SEARCHING | RETURNING | IDLE | CRASHED
    - task_queue: contains {"task": string, "status": pending|completed, "feedback": []}
    - surroundings: list of entities within a 1.0 unit optical radius
    Base station is at (9.5, 9.5).
    """
    conn = db.get_db_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT x, y, battery, status, task_queue, thermal_memory FROM drones WHERE id=?",
        (drone_id,)
    )
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {"error": "drone not found"}

    x, y, batt, status, task_queue_raw, t_mem_raw = row
    cx, cy = x, y
    
    # Optical Scan use to scan for surroundings entities
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

    task_queue = json.loads(task_queue_raw) if task_queue_raw else []
    thermal_memory = json.loads(t_mem_raw) if t_mem_raw else []
    
    # Get only the very top incomplete task
    current_task = None
    for t in task_queue:
        if t.get("status") == "pending":
            current_task = t
            break

    return {
        "id": drone_id,
        "pos": {"x": round(x, 2), "y": round(y, 2)},
        "status": status,
        "current_task": current_task,
        "thermal_memory": thermal_memory,
        "surroundings": detected if detected else [{"type": "EMPTY", "distance": 0, "angle_deg": 0}],
        "summary": f"{drone_id} at ({round(x,1)},{round(y,1)}), status {status}. Active Task: {'Yes' if current_task else 'No'}. Detected {len(detected)} nearby entities."
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
def thermal_scan(drone_id: str, cluster_id: str) -> dict:
    """
    Emits a fan-shaped thermal sensor beam from the drone accurately pointing towards the given building cluster.

    HOW IT WORKS:
    - Automatically calculates the optimal angle bearing towards the cluster_id.
    - Fixed Scale: radius = 6.0 units (300m), arc = 60°.
    - Signal Logic: 95% at 1.0u distance, 20% at 6.0u distance.
    - Obstacles block the heat (occlusion).
    - Detection Results: Includes a list of hits with signal strength, distance, and relative bearing.
    """
    conn = db.get_db_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT x, y, thermal_memory FROM drones WHERE id=?", (drone_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"error": "drone not found"}
    cx, cy, t_mem_raw = row
    thermal_memory = json.loads(t_mem_raw) if t_mem_raw else []
    
    cursor.execute("SELECT cx, cy FROM building_clusters WHERE id=?", (cluster_id,))
    target = cursor.fetchone()
    if not target:
        conn.close()
        return {"error": "Cluster not found"}
        
    angle_deg = _bearing(cx, cy, target[0], target[1])

    # Load obstacles and survivors
    cursor.execute("SELECT x, y FROM obstacles")
    obstacles = {(r[0], r[1]) for r in cursor.fetchall()}

    cursor.execute("SELECT x, y FROM survivors WHERE found=0")
    survivors = [(r[0], r[1]) for r in cursor.fetchall()]

    SCAN_RADIUS = 6.0
    ARC_DEG = 60.0
    detections = []
    highest_true_score = 0.0

    # 1. Coverage Map Sync
    # Mathematically find all 0.5x0.5 tiles within this arc to mark as revealed
    revealed_cells = []
    # Grid limits are 0-40 because map is 20x20 and cells are 0.5
    for ix in range(40):
        for iy in range(40):
            cell_x = ix * 0.5 + 0.25
            cell_y = iy * 0.5 + 0.25
            cdist = math.hypot(cell_x - cx, cell_y - cy)
            if cdist <= SCAN_RADIUS:
                cbearing = _bearing(cx, cy, cell_x, cell_y)
                if _angle_in_arc(cbearing, angle_deg, ARC_DEG):
                    if not _ray_occluded(cx, cy, cell_x, cell_y, obstacles):
                        revealed_cells.append((ix, iy))
    
    if revealed_cells:
        db.sync_coverage(revealed_cells)

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
        rad = math.radians(d["bearing"])
        est_x = round(cx + d["distance"] * math.sin(rad), 2)
        est_y = round(cy + d["distance"] * math.cos(rad), 2)

        results.append({
            "bearing": d["bearing"],
            "distance": d["distance"],
            "signal_strength": f"{int(d['score'])}%"
        })

        matched = False
        for tm in thermal_memory:
            if math.hypot(tm["x"] - est_x, tm["y"] - est_y) <= 0.6:
                tm["signal"] = int(max(tm["signal"], d["score"]))
                tm["x"] = round((tm["x"] + est_x) / 2.0, 2)
                tm["y"] = round((tm["y"] + est_y) / 2.0, 2)
                matched = True
                break
        if not matched:
            thermal_memory.append({"x": est_x, "y": est_y, "signal": int(d["score"])})

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

        p_rad = math.radians(p_bearing)
        est_x = round(cx + p_dist * math.sin(p_rad), 2)
        est_y = round(cy + p_dist * math.cos(p_rad), 2)

        matched = False
        for tm in thermal_memory:
            if math.hypot(tm["x"] - est_x, tm["y"] - est_y) <= 0.6:
                tm["signal"] = int(max(tm["signal"], p_strength))
                matched = True
                break
        if not matched:
            thermal_memory.append({"x": est_x, "y": est_y, "signal": p_strength})

    cursor.execute("UPDATE drones SET thermal_memory=? WHERE id=?", (json.dumps(thermal_memory), drone_id))

    # Overall strongest signal for quick reference
    final_score = int(highest_true_score)

    conn.commit()
    conn.close()

    det_count = len(results)
    summary = f"Thermal scan at {angle_deg}° (±30°): detected {det_count} heat signature    s. Peak signal {final_score}%."
    if det_count == 0:
        summary = f"Thermal scan at {angle_deg}° (±30°): no heat signatures detected."

    return {
        "angle_deg": angle_deg,
        "highest_signal": f"{final_score}%",
        "detections": results,
        "summary": summary
    }


@mcp.tool()
def get_nearest_base(drone_id: str) -> dict:
    """
    Returns the nearest base station coordinates to the drone.
    Use this when you are setting RETURNING status and need to know where to fly.
    """
    conn = db.get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT x, y FROM drones WHERE id=?", (drone_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"error": "drone not found"}

    cx, cy = row
    
    import map_generator
    bases = map_generator.parse_ascii_map()['bases']
    
    if not bases: 
        return {"x": 9.5, "y": 9.5}

    nearest = min(bases, key=lambda b: math.hypot(b["x"] + 0.5 - cx, b["y"] + 0.5 - cy))
    
    return {
        "x": nearest["x"] + 0.5,
        "y": nearest["y"] + 0.5,
        "summary": f"Nearest base is at ({nearest['x'] + 0.5}, {nearest['y'] + 0.5})."
    }

@mcp.tool()
def report_to_commander(drone_id: str, message: str) -> dict:
    """
    Send a report directly to the Central Commander.
    Use this after EVERY thermal scan, if your path is blocked, or if your battery is critically low.
    """
    conn = db.get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT messages_for_commander FROM drones WHERE id=?", (drone_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"error": "drone not found"}
        
    msgs = json.loads(row[0]) if row[0] else []
    import time
    msgs.append({"time": time.time(), "message": message})
    
    cursor.execute("UPDATE drones SET messages_for_commander=? WHERE id=?", (json.dumps(msgs), drone_id))
    conn.commit()
    conn.close()
    
    return {"summary": "Report successfully queued for the Commander's review."}

@mcp.tool()
def declare_survivor(drone_id: str, x: float, y: float) -> dict:
    """
    Declare a confirmed survivor at the given coordinates (within a 0.5 unit tolerance).
    If a survivor actually exists near here, they will be rescued.
    If you are wrong, your error_count increases!
    """
    conn = db.get_db_conn()
    cursor = conn.cursor()
    
    # Clean up thermal memory around the area
    cursor.execute("SELECT thermal_memory FROM drones WHERE id=?", (drone_id,))
    row = cursor.fetchone()
    if row and row[0]:
        t_mem = json.loads(row[0])
        new_mem = [tm for tm in t_mem if math.hypot(tm["x"] - x, tm["y"] - y) > 0.6]
        cursor.execute("UPDATE drones SET thermal_memory=? WHERE id=?", (json.dumps(new_mem), drone_id))

    cursor.execute("SELECT id, x, y FROM survivors WHERE found=0")
    survivors = cursor.fetchall()
    
    found_id = None
    for s_id, sx, sy in survivors:
        if math.hypot(sx - x, sy - y) <= 0.5:
            found_id = s_id
            break
            
    if found_id:
        cursor.execute("UPDATE survivors SET found=1 WHERE id=?", (found_id,))
        # Find drone and insert fake log message so simulation knows about the rescue
        import simulation
        if simulation.sim_world:
            simulation.sim_world.found_survivors += 1
            simulation.sim_world.log_action(drone_id, f"Survivor officially declared and rescued near {round(x,1)}, {round(y,1)}!")
        conn.commit()
        conn.close()
    else:
        cursor.execute("UPDATE drones SET error_count = error_count + 1 WHERE id=?", (drone_id,))
        conn.commit()
        conn.close()
        
    return {"summary": "You have submitted a declaration. Please send a report back to the Commander."}

@mcp.tool()
def remove_thermal_noise(drone_id: str, x: float, y: float) -> dict:
    """
    Removes a specific thermal signature from your thermal memory if you determine it is noise.
    Use this when you have investigated a heat signature at close range and the signal is weak (< 30%).
    """
    conn = db.get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT thermal_memory FROM drones WHERE id=?", (drone_id,))
    row = cursor.fetchone()
    if not row or not row[0]:
        conn.close()
        return {"summary": "No thermal memory to remove."}
    
    t_mem = json.loads(row[0])
    new_mem = [tm for tm in t_mem if math.hypot(tm["x"] - x, tm["y"] - y) > 0.6]
    
    cursor.execute("UPDATE drones SET thermal_memory=? WHERE id=?", (json.dumps(new_mem), drone_id))
    conn.commit()
    conn.close()
    return {"summary": f"Thermal noise near ({x}, {y}) has been wiped from memory."}


if __name__ == "__main__":
    mcp.run()
