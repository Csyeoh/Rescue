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
    """Compass bearing in degrees from (ox,oy) to (tx,ty). 0=North(up/−y), 90=East(+x)."""
    dx = tx - ox
    dy = -(ty - oy)   # invert Y because screen-Y increases downward
    angle = math.degrees(math.atan2(dx, dy)) % 360
    return round(angle, 1)


def _ray_occluded(ox, oy, tx, ty, obstacles: set, step=0.25) -> bool:
    """
    Walk a ray from (ox,oy) towards (tx,ty) in small steps.
    Return True if the ray passes within 0.5 units of any obstacle centre.
    """
    dist = math.hypot(tx - ox, ty - oy)
    if dist == 0:
        return False
    ux = (tx - ox) / dist
    uy = (ty - oy) / dist
    d = step
    while d < dist - step:
        px, py = ox + ux * d, oy + uy * d
        for (ax, ay) in obstacles:
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
    Returns live telemetry for a drone:
    - pos: current continuous-space position {x, y} (float, 1 unit = 50 m)
    - battery: remaining battery %
    - status: SEARCHING | RETURNING | CHARGING | IDLE | CRASHED
    - assigned_sector: {cx, cy, radius} circular search zone, or null
    - thermal_memory: list of past heat-trace positions
    Base station is at (9.5, 9.5).
    """
    conn = db.get_db_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT x, y, battery, status, thermal_memory, assigned_sector FROM drones WHERE id=?",
        (drone_id,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"error": "drone not found"}

    x, y, batt, status, t_mem_raw, sector_raw = row
    return {
        "id": drone_id,
        "pos": {"x": round(x, 2), "y": round(y, 2)},
        "battery": batt,
        "status": status,
        "assigned_sector": json.loads(sector_raw) if sector_raw else None,
        "thermal_memory": json.loads(t_mem_raw) if t_mem_raw else [],
        "base_pos": {"x": 9.5, "y": 9.5},
    }


@mcp.tool()
def view_surrounding(drone_id: str) -> dict:
    """
    Reveals everything within a 1-unit radius (= 50 m) of the drone.
    Returns a list of detected entities, each with:
      - type: OBSTACLE | BUILDING | SURVIVOR
      - distance: float (units)
      - angle_deg: compass bearing from drone (0=North, 90=East, 180=South, 270=West)
    Also marks encountered buildings and obstacles as revealed/discovered in the DB.
    """
    conn = db.get_db_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT x, y FROM drones WHERE id=?", (drone_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"error": "drone not found"}
    cx, cy = row

    detected = []

    # Obstacles
    cursor.execute("SELECT id, x, y FROM obstacles")
    for obs_id, ox, oy in cursor.fetchall():
        dist = math.hypot(cx - ox, cy - oy)
        if dist <= 1.0:
            cursor.execute("UPDATE obstacles SET discovered=1 WHERE id=?", (obs_id,))
            detected.append({
                "type": "OBSTACLE",
                "distance": round(dist, 2),
                "angle_deg": _bearing(cx, cy, ox, oy)
            })

    # Buildings
    cursor.execute("SELECT id, x, y FROM buildings")
    for bld_id, bx, by in cursor.fetchall():
        dist = math.hypot(cx - bx, cy - by)
        if dist <= 1.0:
            cursor.execute("UPDATE buildings SET revealed=1 WHERE id=?", (bld_id,))
            detected.append({
                "type": "BUILDING",
                "distance": round(dist, 2),
                "angle_deg": _bearing(cx, cy, bx, by)
            })

    # Survivors (unfound)
    cursor.execute("SELECT id, x, y FROM survivors WHERE found=0")
    for s_id, sx, sy in cursor.fetchall():
        dist = math.hypot(cx - sx, cy - sy)
        if dist <= 1.0:
            detected.append({
                "type": "SURVIVOR",
                "distance": round(dist, 2),
                "angle_deg": _bearing(cx, cy, sx, sy)
            })

    conn.commit()
    conn.close()

    return {
        "drone_pos": {"x": round(cx, 2), "y": round(cy, 2)},
        "reveal_radius_units": 1.0,
        "detected": detected if detected else [{"type": "EMPTY", "distance": 0, "angle_deg": 0}]
    }


@mcp.tool()
def thermal_scan(drone_id: str, angle_deg: float, arc_deg: float = 60.0) -> dict:
    """
    Emits a fan-shaped thermal sensor beam from the drone in a chosen direction.

    HOW IT WORKS:
    - angle_deg: the centre bearing of the fan (0=North/up, 90=East, 180=South, 270=West).
      Use any angle for diagonal sweeps (e.g. 45 = NE).
    - arc_deg: total width of the fan in degrees (default 60°, i.e. ±30° around centre).
    - Scan radius: 6 units (= 300 m).
    - Obstacles block the heat — if a wall is between the drone and a survivor, no signal.

    INTERPRETING THE RESULT:
    - signal_strength ≥ 70%: high confidence — a survivor is likely nearby in this direction.
    - 30–69%: weak signal — possible survivor, consider scanning adjacent angles or moving closer.
    - < 30%: likely noise / ghost signal — do NOT act on this alone.
    - The reading contains ±12% atmospheric noise. Scan the same angle twice to confirm.

    OUTPUT: {"angle_deg": float, "arc_deg": float, "signal_strength": "XX%"}
    """
    conn = db.get_db_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT x, y FROM drones WHERE id=?", (drone_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"error": "drone not found"}
    cx, cy = row

    # Load obstacles and survivors
    cursor.execute("SELECT x, y FROM obstacles")
    obstacles = {(r[0], r[1]) for r in cursor.fetchall()}

    cursor.execute("SELECT x, y FROM survivors WHERE found=0")
    survivors = [(r[0], r[1]) for r in cursor.fetchall()]

    SCAN_RADIUS = 6.0
    highest_true_score = 0.0
    scanned_cells = []

    for sx, sy in survivors:
        dist = math.hypot(cx - sx, cy - sy)
        if dist > SCAN_RADIUS:
            continue

        bearing = _bearing(cx, cy, sx, sy)
        if not _angle_in_arc(bearing, angle_deg, arc_deg):
            continue

        # Line-of-sight occlusion check
        if _ray_occluded(cx, cy, sx, sy, obstacles):
            continue

        score = max(0.0, 100.0 - dist * 15.0)
        if score > highest_true_score:
            highest_true_score = score

    # Mark swept visual cells for UI (sample arc at 0.5-unit intervals)
    NUM_RAYS = max(5, int(arc_deg / 5))
    for ray_i in range(NUM_RAYS + 1):
        frac = ray_i / NUM_RAYS if NUM_RAYS > 0 else 0
        ray_angle = (angle_deg - arc_deg / 2) + frac * arc_deg
        ray_rad = math.radians(ray_angle)
        for depth_step in range(1, int(SCAN_RADIUS * 2) + 1):
            d = depth_step * 0.5
            # North = -y, East = +x
            ray_x = cx + math.sin(ray_rad) * d
            ray_y = cy - math.cos(ray_rad) * d
            if not (0 <= ray_x < 20 and 0 <= ray_y < 20):
                break
            # Stop if ray hits an obstacle
            tile = (int(ray_x), int(ray_y))
            if tile in {(int(ox), int(oy)) for ox, oy in obstacles}:
                break
            scanned_cells.append({"x": round(ray_x, 1), "y": round(ray_y, 1)})

    # Atmospheric noise ±12%
    noise = random.randint(-12, 12)
    final_score = max(0, min(100, int(highest_true_score + noise)))

    if scanned_cells:
        cursor.execute(
            "INSERT INTO thermal_scans (cells_json, timestamp) VALUES (?, ?)",
            (json.dumps(scanned_cells), time.time())
        )
        conn.commit()

    conn.close()

    return {
        "angle_deg": angle_deg,
        "arc_deg": arc_deg,
        "signal_strength": f"{final_score}%"
    }


@mcp.tool()
def check_task_viability(drone_id: str, target_x: float, target_y: float) -> dict:
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

    return {
        "viable": battery >= required,
        "required_battery": round(required, 1),
        "current_battery": battery,
        "distance_to_target_units": round(d_to_target, 2),
        "distance_target_to_base_units": round(d_to_base, 2),
    }


if __name__ == "__main__":
    mcp.run()
