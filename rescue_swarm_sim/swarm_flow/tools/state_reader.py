import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
import simulation

def get_current_map_state() -> dict:
    """
    Assembles the complete world state directly from the Mesa environment and the DB.
    Used for WebSocket broadcasts – no dependency on api.py.
    """
    world = simulation.sim_world
    if not world: return {"error": "Simulation not initialized."}

    from simulation import CellAgent, DroneAgent, SurvivorAgent
    
    terrain = []
    survivors = []
    for contents, (x, y) in world.grid.coord_iter():
        for obj in contents:
            if isinstance(obj, CellAgent):
                terrain.append({
                    "x": x, "y": y,
                    "altitude": obj.altitude,
                    "building_height": obj.building_height,
                    "is_obstacle": obj.is_obstacle,
                    "terrain_type": obj.terrain_type,
                    "obstacle_discovered": obj.obstacle_discovered,
                    "thermal_aura": obj.thermal_aura,
                    "revealed": obj.revealed,
                    "assigned_drone": getattr(obj, "assigned_drone", None),
                })
            elif isinstance(obj, SurvivorAgent):
                survivors.append({"id": obj.unique_id, "x": x, "y": y, "discovered": obj.found})

    # Drones are dynamic — collect from schedule
    drones = []
    for agent in world.schedule.agents:
        if isinstance(agent, DroneAgent):
            drones.append({
                "id": agent.unique_id,
                "x": agent.pos[0] if agent.pos else 9,
                "y": agent.pos[1] if agent.pos else 9,
                "battery": agent.battery,
                "status": agent.status,
            })

    return {
        "grid": {"width": world.width, "height": world.height},
        "terrain": terrain,
        "drones": drones,
        "survivors": survivors,
    }
