import heapq
import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import database
import mcp_server

try:
    from crewai.tools import tool as crewai_tool
except Exception:  # pragma: no cover
    crewai_tool = None

GRID_WIDTH = 20
GRID_HEIGHT = 20
BASE_CAMP_X = 9
BASE_CAMP_Y = 9


def read_world_state() -> Dict[str, Any]:
    conn = sqlite3.connect(database.DB_NAME, timeout=10.0)
    cursor = conn.cursor()

    cursor.execute("SELECT x, y, altitude, is_obstacle FROM grid")
    grid_rows = cursor.fetchall()
    grid = [
        {"x": int(x), "y": int(y), "altitude": float(alt), "is_obstacle": bool(is_ob)}
        for (x, y, alt, is_ob) in grid_rows
    ]

    cursor.execute("SELECT global_water_level, water_speed FROM environment WHERE id=1")
    env_row = cursor.fetchone()
    environment = {
        "global_water_level": float(env_row[0]) if env_row else 0.0,
        "water_speed": float(env_row[1]) if env_row else 0.0,
    }

    cursor.execute("SELECT drone_id, x, y, battery, is_active, health_status FROM drones WHERE is_active=1")
    drones_rows = cursor.fetchall()
    drones = [
        {
            "id": drone_id,
            "x": int(x),
            "y": int(y),
            "battery": int(battery),
            "is_active": int(is_active),
            "health_status": health_status,
        }
        for (drone_id, x, y, battery, is_active, health_status) in drones_rows
    ]

    conn.close()
    return {"grid": grid, "environment": environment, "drones": drones}


def _read_obstacle_set(conn: sqlite3.Connection) -> set[Tuple[int, int]]:
    cursor = conn.cursor()
    cursor.execute("SELECT x, y FROM grid WHERE is_obstacle=1")
    return {(int(x), int(y)) for (x, y) in cursor.fetchall()}


def _in_bounds(x: int, y: int) -> bool:
    return 0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT


def _neighbors(x: int, y: int) -> Iterable[Tuple[int, int]]:
    yield x + 1, y
    yield x - 1, y
    yield x, y + 1
    yield x, y - 1


def _heuristic(ax: int, ay: int, bx: int, by: int) -> int:
    return abs(ax - bx) + abs(ay - by)


@dataclass(frozen=True)
class PathResult:
    path: List[Tuple[int, int]]
    steps: int


def _a_star(
    obstacles: set[Tuple[int, int]],
    start: Tuple[int, int],
    goal: Tuple[int, int],
) -> Optional[PathResult]:
    if start == goal:
        return PathResult(path=[], steps=0)

    if goal in obstacles:
        return None

    open_heap: List[Tuple[int, int, Tuple[int, int]]] = []
    heapq.heappush(open_heap, (_heuristic(*start, *goal), 0, start))

    came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
    g_score: Dict[Tuple[int, int], int] = {start: 0}

    visited: set[Tuple[int, int]] = set()

    while open_heap:
        _, current_g, current = heapq.heappop(open_heap)
        if current in visited:
            continue
        visited.add(current)

        if current == goal:
            rev: List[Tuple[int, int]] = []
            node = goal
            while node != start:
                rev.append(node)
                node = came_from[node]
            rev.reverse()
            return PathResult(path=rev, steps=len(rev))

        cx, cy = current
        for nx, ny in _neighbors(cx, cy):
            if not _in_bounds(nx, ny):
                continue
            neighbor = (nx, ny)
            if neighbor in obstacles:
                continue

            tentative_g = current_g + 1
            prev_g = g_score.get(neighbor)
            if prev_g is not None and tentative_g >= prev_g:
                continue

            came_from[neighbor] = current
            g_score[neighbor] = tentative_g
            f = tentative_g + _heuristic(nx, ny, *goal)
            heapq.heappush(open_heap, (f, tentative_g, neighbor))

    return None


def calculate_path_and_battery(
    start_x: int,
    start_y: int,
    target_x: int,
    target_y: int,
) -> Dict[str, Any]:
    start = (int(start_x), int(start_y))
    target = (int(target_x), int(target_y))
    base = (BASE_CAMP_X, BASE_CAMP_Y)

    if not _in_bounds(*start) or not _in_bounds(*target):
        return {"ok": False, "error": "Coordinates out of bounds.", "path": [], "battery_required": None}

    conn = sqlite3.connect(database.DB_NAME, timeout=10.0)
    obstacles = _read_obstacle_set(conn)
    conn.close()

    to_target = _a_star(obstacles, start, target)
    if to_target is None:
        return {"ok": False, "error": "No valid path to target (blocked).", "path": [], "battery_required": None}

    back_to_base = _a_star(obstacles, target, base)
    if back_to_base is None:
        return {"ok": False, "error": "No valid return path to Base Camp (blocked).", "path": [], "battery_required": None}

    steps_total = to_target.steps + back_to_base.steps
    battery_required = steps_total * 2

    return {
        "ok": True,
        "path": [{"x": x, "y": y} for (x, y) in to_target.path],
        "steps_to_target": to_target.steps,
        "steps_to_base": back_to_base.steps,
        "battery_required": battery_required,
        "base_camp": {"x": BASE_CAMP_X, "y": BASE_CAMP_Y},
    }


def execute_drone_move(drone_id: str, x: int, y: int) -> Dict[str, Any]:
    msg = mcp_server.move_drone(drone_id, int(x), int(y))
    aura_detected = "Faint thermal aura detected" in msg
    success = msg.startswith("Success:")

    new_battery: Optional[int] = None
    if "Battery now at" in msg:
        try:
            tail = msg.split("Battery now at", 1)[1].strip()
            pct = tail.split("%", 1)[0].strip()
            new_battery = int(pct)
        except Exception:
            new_battery = None

    return {"ok": success, "message": msg, "aura_detected": aura_detected, "battery": new_battery}


def execute_thermal_scan(drone_id: str) -> Dict[str, Any]:
    msg = mcp_server.thermal_scan(drone_id)
    found = msg.startswith("SUCCESS:")
    return {"ok": True, "found_survivor": found, "message": msg}


read_world_state_tool = None
calculate_path_and_battery_tool = None
execute_drone_move_tool = None
execute_thermal_scan_tool = None

if crewai_tool:

    @crewai_tool("read_world_state")
    def read_world_state_tool() -> str:
        """Read current world state (grid, environment, drones) from SQLite and return JSON."""
        return json.dumps(read_world_state())

    @crewai_tool("calculate_path_and_battery")
    def calculate_path_and_battery_tool(start_x: int, start_y: int, target_x: int, target_y: int) -> str:
        """Compute A* path and Bingo Fuel required (to target + return to base) and return JSON."""
        return json.dumps(calculate_path_and_battery(start_x, start_y, target_x, target_y))

    @crewai_tool("execute_drone_move")
    def execute_drone_move_tool(drone_id: str, x: int, y: int) -> str:
        """Move a drone via MCP move_drone and return JSON with aura detection and battery."""
        return json.dumps(execute_drone_move(drone_id, x, y))

    @crewai_tool("execute_thermal_scan")
    def execute_thermal_scan_tool(drone_id: str) -> str:
        """Trigger MCP thermal_scan for a drone and return JSON with scan results."""
        return json.dumps(execute_thermal_scan(drone_id))
