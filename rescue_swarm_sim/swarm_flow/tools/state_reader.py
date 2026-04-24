import sys
import os
import json
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
import simulation


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
        {"id": a.unique_id, "x": a.pos[0], "y": a.pos[1], "height": getattr(a, "height", 1.2), "discovered": a.discovered}
        for a in world.obstacle_map.values()
    ]

    buildings = [
        {"id": a.unique_id, "x": a.pos[0], "y": a.pos[1],
         "height": getattr(a, "height", 1.6), "revealed": a.revealed}
        for a in world.building_map.values()
    ]

    # ── Drones & Sectors ────────────────────────────────────────────────────────
    drones = []
    for agent in world.schedule.agents:
        if isinstance(agent, DroneAgent):
            drones.append({
                "id": agent.unique_id,
                "x": agent.pos[0],
                "y": agent.pos[1],
                "z": getattr(agent, "z", 1.8),
                "battery": agent.battery,
                "status": agent.status,
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
                "found_tick": agent.found_tick,
            })

    # Active thermal scans are now isolated to their own API endpoint.

    return {
        "tick": world.tick_count,
        "grid": {"width": world.space.x_max, "height": world.space.y_max},
        "obstacles": obstacles,
        "buildings": buildings,
        "drones": drones,
        "survivors": survivors,
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
    for agent in world.schedule.agents:
        if isinstance(agent, DroneAgent):
            drones.append({
                "id": agent.unique_id,
                "x": agent.pos[0],
                "y": agent.pos[1],
                "z": getattr(agent, "z", 1.8),
                "battery": agent.battery,
                "status": agent.status,
            })

    return {
        "drones": drones,
    }

def get_coverage_state() -> dict:
    """
    Returns only the coordinates (x_idx, y_idx) of cells that are revealed.
    """
    import db
    cells = db.get_revealed_coverage()
    return {
        "cells": [[c[0], c[1]] for c in cells]
    }
