import json
import os
import sqlite3
import argparse
from typing import Any, Dict, List, Tuple
from pathlib import Path

import db
import map_generator
from pydantic import BaseModel, Field


class PlaybackBuilding(BaseModel):
    x: int
    y: int
    height: float | None = None


class PlaybackObstacle(BaseModel):
    x: int
    y: int
    height: float | None = None


class PlaybackBase(BaseModel):
    x: int
    y: int


class PlaybackDrone(BaseModel):
    id: str
    x: float
    y: float
    battery: int
    status: str
    thermal_memory: list = Field(default_factory=list)
    task_queue: list = Field(default_factory=list)


class PlaybackSurvivor(BaseModel):
    id: str
    x: float
    y: float
    found: bool


class PlaybackTick(BaseModel):
    tick: int
    drones: List[PlaybackDrone]
    survivors: List[PlaybackSurvivor]
    coverage: List[Tuple[int, int]]
    logs: List[str]
    buildings: List[PlaybackBuilding] | None = None
    obstacles: List[PlaybackObstacle] | None = None
    bases: List[PlaybackBase] | None = None


def _resolve_map_path(repo_root: Path, map_path: str | None) -> Path:
    default_map_path = Path(__file__).resolve().with_name("map.txt")
    env_map_path = os.getenv("RESCUE_MAP_PATH")

    if map_path:
        p = Path(map_path)
        if p.exists() and p.is_dir():
            p = p / "map.txt"
        if p.exists() and p.is_file():
            return p
        raise FileNotFoundError(f"--map path not found: {str(p)}")

    candidates: List[Path] = []
    if env_map_path:
        p = Path(env_map_path)
        candidates.append(p / "map.txt" if p.exists() and p.is_dir() else p)
    candidates.append(default_map_path)
    candidates.append(repo_root / "rescue_swarm_sim" / "map.txt")

    for c in candidates:
        try:
            if c.exists() and c.is_file():
                return c
        except Exception:
            continue

    raise FileNotFoundError(
        "map.txt not found. Tried:\n" + "\n".join(f"- {str(c)}" for c in candidates)
    )


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _compute_revealed_cells(cx: float, cy: float, radius: float = 1.0) -> List[Tuple[int, int]]:
    revealed: List[Tuple[int, int]] = []
    r = radius
    for ix in range(max(0, int((cx - r) * 2)), min(40, int((cx + r) * 2) + 1)):
        for iy in range(max(0, int((cy - r) * 2)), min(40, int((cy + r) * 2) + 1)):
            cell_x = ix * 0.5 + 0.25
            cell_y = iy * 0.5 + 0.25
            if ((cell_x - cx) ** 2 + (cell_y - cy) ** 2) ** 0.5 <= r:
                revealed.append((ix, iy))
    return revealed


def _init_world_in_db(map_data: Dict[str, Any], num_drones: int = 3, drone_battery: int = 100) -> None:
    db.init_db()

    buildings = map_data.get("buildings", [])
    obstacles = map_data.get("obstacles", [])
    survivors = map_data.get("survivors", [])

    base = {"x": 9, "y": 9}
    drones = []
    for i in range(num_drones):
        drones.append(
            (
                f"drone_{i+1}",
                base["x"] + 0.5,
                base["y"] + 0.5,
                0.5,
                drone_battery,
                "IDLE",
                0,
                json.dumps([]),
                json.dumps([]),
                0,
                json.dumps([]),
            )
        )

    obstacle_rows = []
    for o in obstacles:
        ix, iy = int(o["x"]), int(o["y"])
        obstacle_rows.append((f"obs_{ix}_{iy}", ix + 0.5, iy + 0.5, float(o.get("height") or 1.1), 0))

    building_rows = []
    for b in buildings:
        ix, iy = int(b["x"]), int(b["y"])
        building_rows.append((f"bld_{ix}_{iy}", ix + 0.5, iy + 0.5, float(b.get("height") or 1.5), 0))

    survivor_rows = []
    for i, s in enumerate(survivors):
        ix, iy = int(s.get("x", 0)), int(s.get("y", 0))
        survivor_rows.append((f"s_{i}", ix + 0.5, iy + 0.5, 0, None))

    db.sync_world_state(
        drones,
        obstacle_rows,
        building_rows,
        [],
        survivor_rows,
    )


def _read_db_snapshot(tick: int, logs_for_tick: List[str]) -> Dict[str, Any]:
    conn = db.get_db_conn()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, x, y, battery, status, thermal_memory, task_queue FROM drones ORDER BY id"
    )
    drone_rows = cursor.fetchall()
    drones = []
    for d_id, x, y, battery, status, thermal_memory, task_queue in drone_rows:
        drones.append(
            {
                "id": d_id,
                "x": float(x),
                "y": float(y),
                "battery": int(battery),
                "status": str(status),
                "thermal_memory": json.loads(thermal_memory) if thermal_memory else [],
                "task_queue": json.loads(task_queue) if task_queue else [],
            }
        )

    cursor.execute("SELECT id, x, y, found FROM survivors ORDER BY id")
    survivor_rows = cursor.fetchall()
    survivors = [
        {"id": str(sid), "x": float(x), "y": float(y), "found": bool(found)}
        for (sid, x, y, found) in survivor_rows
    ]

    cursor.execute("SELECT x_idx, y_idx FROM coverage WHERE revealed=1")
    coverage_rows = cursor.fetchall()
    coverage = [[int(ix), int(iy)] for (ix, iy) in coverage_rows]

    conn.close()

    return {
        "tick": tick,
        "drones": drones,
        "survivors": survivors,
        "coverage": coverage,
        "logs": logs_for_tick,
    }


def export_playback(
    output_json_path: str,
    ticks: int = 240,
    num_drones: int = 3,
    drone_battery: int = 100,
    map_path: str | None = None,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    export_db_path = repo_root / "rescue_swarm_sim" / "playback_export.db"
    chosen_map_path = _resolve_map_path(repo_root, map_path)

    db.DB_PATH = str(export_db_path)
    map_data = map_generator.parse_ascii_map(str(chosen_map_path))
    _init_world_in_db(map_data, num_drones=num_drones, drone_battery=drone_battery)

    hold_remaining: Dict[str, int] = {f"drone_{i+1}": 0 for i in range(num_drones)}

    all_ticks: List[Dict[str, Any]] = []

    try:
        for t in range(ticks):
            logs_for_tick: List[str] = []

            conn = db.get_db_conn()
            cursor = conn.cursor()

            cursor.execute("SELECT id, x, y, z, battery, status FROM drones ORDER BY id")
            drones = cursor.fetchall()

            cursor.execute("SELECT id, x, y, found FROM survivors ORDER BY id")
            survivors = cursor.fetchall()

            survivors_by_id = {
                str(sid): (float(x), float(y), int(found)) for (sid, x, y, found) in survivors
            }

            updated_drones = []
            for d_id, x, y, z, battery, status in drones:
                d_id = str(d_id)
                x = float(x)
                y = float(y)
                z = float(z)
                battery = int(battery)
                status = str(status)

                if hold_remaining.get(d_id, 0) > 0:
                    hold_remaining[d_id] -= 1
                    status = "TRIAGE_HOLD"
                    logs_for_tick.append(f"[tick {t}] {d_id} holding for triage.")
                    updated_drones.append((d_id, x, y, z, battery, status))
                    continue

                status = "SEARCHING"

                phase = (t + (int(d_id.split("_")[-1]) * 17)) % 80
                if phase < 40:
                    dx, dy = 0.5, 0.0
                else:
                    dx, dy = 0.0, 0.5

                nx = _clamp(x + dx, 0.5, 19.5)
                ny = _clamp(y + dy, 0.5, 19.5)

                if (abs(nx - x) < 1e-6 and abs(ny - y) < 1e-6) or (nx == x and ny == y):
                    if nx <= 0.5 or nx >= 19.5:
                        dx = -dx
                    if ny <= 0.5 or ny >= 19.5:
                        dy = -dy
                    nx = _clamp(x + dx, 0.5, 19.5)
                    ny = _clamp(y + dy, 0.5, 19.5)

                x, y = nx, ny
                battery = max(0, battery - 1)

                revealed_cells = _compute_revealed_cells(x, y, radius=1.0)
                if revealed_cells:
                    cursor.executemany(
                        "UPDATE coverage SET revealed=1, physical_visits = physical_visits + 1 WHERE x_idx=? AND y_idx=?",
                        revealed_cells,
                    )

                newly_found = None
                for sid, (sx, sy, found) in survivors_by_id.items():
                    if found:
                        continue
                    if ((sx - x) ** 2 + (sy - y) ** 2) ** 0.5 <= 1.0:
                        newly_found = sid
                        break

                if newly_found is not None:
                    cursor.execute(
                        "UPDATE survivors SET found=1, found_tick=? WHERE id=?",
                        (t, newly_found),
                    )
                    hold_remaining[d_id] = 6
                    status = "TRIAGE_HOLD"
                    logs_for_tick.append(
                        f"[tick {t}] {d_id} discovered survivor {newly_found} and entered TRIAGE_HOLD."
                    )
                else:
                    logs_for_tick.append(f"[tick {t}] {d_id} moved to ({x:.2f},{y:.2f}).")

                updated_drones.append((d_id, x, y, z, battery, status))

            for d_id, x, y, z, battery, status in updated_drones:
                cursor.execute(
                    "UPDATE drones SET x=?, y=?, z=?, battery=?, status=? WHERE id=?",
                    (x, y, z, battery, status, d_id),
                )

            conn.commit()
            conn.close()

            if t == 0:
                tick_obj = _read_db_snapshot(t, logs_for_tick)
                tick_obj["buildings"] = map_data.get("buildings", [])
                tick_obj["obstacles"] = map_data.get("obstacles", [])
                tick_obj["bases"] = map_data.get("bases", [{"x": 9, "y": 9}])
            else:
                tick_obj = _read_db_snapshot(t, logs_for_tick)

            validated = PlaybackTick.model_validate(tick_obj)
            all_ticks.append(validated.model_dump(exclude_none=True))

        out_path = Path(output_json_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(all_ticks, indent=2), encoding="utf-8")
    finally:
        try:
            for suffix in ("", "-wal", "-shm"):
                p = Path(str(export_db_path) + suffix)
                if p.exists():
                    p.unlink()
        except Exception:
            pass


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    default_output = root / "rescue-ui" / "public" / "playback_data.json"

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=str, default=str(default_output))
    parser.add_argument("--ticks", type=int, default=240)
    parser.add_argument("--num-drones", type=int, default=3)
    parser.add_argument("--battery", type=int, default=100)
    parser.add_argument("--map", type=str, default=None)
    args = parser.parse_args()

    export_playback(
        args.output,
        ticks=args.ticks,
        num_drones=args.num_drones,
        drone_battery=args.battery,
        map_path=args.map,
    )


if __name__ == "__main__":
    main()
