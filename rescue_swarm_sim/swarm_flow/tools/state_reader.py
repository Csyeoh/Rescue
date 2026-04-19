import sys
import os
import json
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
import simulation
import db


def get_current_map_state() -> dict:
    """
    Assembles the complete world state directly from the Mesa ContinuousSpace
    environment and the DB. Used for WebSocket broadcasts.
    """
    world = simulation.sim_world
    if not world:
        return {"error": "Simulation not initialized."}

    from simulation import DroneAgent, SurvivorAgent, ObstacleAgent, BuildingAgent

    # ── Terrain ─────────────────────────────────────────────────────────────
    obstacles = [
        {"id": a.unique_id, "x": a.pos[0], "y": a.pos[1], "discovered": a.discovered}
        for a in world.obstacle_map.values()
    ]

    buildings = [
        {"id": a.unique_id, "x": a.pos[0], "y": a.pos[1],
         "revealed": a.revealed}
        for a in world.building_map.values()
    ]

    # ── Drones & Sectors ────────────────────────────────────────────────────────
    drones = []
    sectors = []
    for agent in world.schedule.agents:
        if isinstance(agent, DroneAgent):
            drones.append({
                "id": agent.unique_id,
                "x": agent.pos[0],
                "y": agent.pos[1],
                "battery": agent.battery,
                "status": agent.status,
            })
            if getattr(agent, "assigned_sector", None):
                sectors.append({
                    "drone_id": agent.unique_id,
                    "cx": agent.assigned_sector.get("cx", 0),
                    "cy": agent.assigned_sector.get("cy", 0),
                    "radius": agent.assigned_sector.get("radius", 0)
                })

    # ── Survivors ────────────────────────────────────────────────────────────
    survivors = []
    for agent in world.schedule.agents:
        if isinstance(agent, SurvivorAgent):
            survivors.append({
                "id": agent.unique_id,
                "x": agent.pos[0],
                "y": agent.pos[1],
                "discovered": agent.found,
            })

    # ── Active thermal scans (last 5 seconds) ────────────────────────────────
    scanned_cells = []
    try:
        conn = db.get_db_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT cells_json FROM thermal_scans WHERE timestamp > ?",
            (time.time() - 5.0,)
        )
        for (cells_json,) in cursor.fetchall():
            try:
                scanned_cells.extend(json.loads(cells_json))
            except Exception:
                pass
        conn.close()
    except Exception:
        pass

    return {
        "grid": {"width": world.space.x_max, "height": world.space.y_max},
        "obstacles": obstacles,
        "buildings": buildings,
        "drones": drones,
        "sectors": sectors,
        "survivors": survivors,
        "thermal_scans": scanned_cells,
        "logs": world.mission_logs,
    }


def get_dispatcher_state() -> dict:
    """
    Lightweight state snapshot containing ONLY dispatcher-modified data:
      - drone statuses  (IDLE → SEARCHING)
      - sector assignments  (cx, cy, radius per drone)

    This is broadcast as 'dispatcher_update' after the dispatcher phase,
    separate from the full 'tick_update' used after the drone/physics phase.
    """
    world = simulation.sim_world
    if not world:
        return {"error": "Simulation not initialized."}

    from simulation import DroneAgent

    drones = []
    sectors = []
    for agent in world.schedule.agents:
        if isinstance(agent, DroneAgent):
            drones.append({
                "id": agent.unique_id,
                "x": agent.pos[0],
                "y": agent.pos[1],
                "battery": agent.battery,
                "status": agent.status,
            })
            if agent.assigned_sector:
                sectors.append({
                    "drone_id": agent.unique_id,
                    "cx": agent.assigned_sector.get("cx", 0),
                    "cy": agent.assigned_sector.get("cy", 0),
                    "radius": agent.assigned_sector.get("radius", 0),
                })

    return {
        "drones": drones,
        "sectors": sectors,
    }

