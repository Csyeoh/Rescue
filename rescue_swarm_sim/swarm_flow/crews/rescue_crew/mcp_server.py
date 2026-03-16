from fastmcp import FastMCP
import time
import json
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
import simulation

# Initialize the MCP Server
mcp = FastMCP("RescueSwarm")

@mcp.tool()
def discover_drones() -> list[str]:
    """Returns a list of all active drone IDs available for command in the simulation."""
    if not simulation.sim_world: return []
    from simulation import DroneAgent
    drones = []
    for agent in simulation.sim_world.schedule.agents:
        if isinstance(agent, DroneAgent):
            drones.append(agent.unique_id)
    return drones

@mcp.tool()
def check_battery(drone_id: str) -> int:
    """Returns the current battery level (0-100) as an integer for a specific drone."""
    if not simulation.sim_world: return -1
    from simulation import DroneAgent
    for agent in simulation.sim_world.schedule.agents:
        if isinstance(agent, DroneAgent) and agent.unique_id == drone_id:
            return agent.battery
    return -1

@mcp.tool()
def get_status(drone_id: str) -> str:
    """Returns the current status of the drone. Expected values are CHARGING, SEARCHING, IDLE or RETURNING."""
    if not simulation.sim_world: return f"Error: simulation resting."
    from simulation import DroneAgent
    for agent in simulation.sim_world.schedule.agents:
        if isinstance(agent, DroneAgent) and agent.unique_id == drone_id:
            return agent.status
    return f"Error: {drone_id} not found."

@mcp.tool()
def set_status(drone_id: str, new_status: str) -> str:
    """Changes the drone's status to a new value (e.g. SEARCHING, RETURNING, CHARGING, IDLE)."""
    if not simulation.sim_world: return f"Error: simulation resting."
    from simulation import DroneAgent
    valid_statuses = ["CHARGING", "SEARCHING", "IDLE", "RETURNING"]
    if new_status not in valid_statuses:
        return f"Error: Invalid status {new_status}."
    for agent in simulation.sim_world.schedule.agents:
        if isinstance(agent, DroneAgent) and agent.unique_id == drone_id:
            agent.status = new_status
            return f"Success: {drone_id} status changed to {new_status}"
    return f"Error: {drone_id} not found."

@mcp.tool()
def get_current_pos(drone_id: str) -> dict:
    """Returns the current (x, y) location of a given drone."""
    if not simulation.sim_world: return {"error": "no sim"}
    from simulation import DroneAgent
    for agent in simulation.sim_world.schedule.agents:
        if isinstance(agent, DroneAgent) and agent.unique_id == drone_id:
            if agent.pos:
                return {"x": agent.pos[0], "y": agent.pos[1]}
            else:
                return {"x": 9, "y": 9}
    return {"error": f"{drone_id} not found."}

@mcp.tool()
def get_base_pos() -> dict:
    """Returns the static base camp position (9, 9)."""
    return {"x": 9, "y": 9}

@mcp.tool()
def get_priority_list(drone_id: str) -> list:
    """Returns the list of (x, y) coordinates assigned to this drone to search."""
    if not simulation.sim_world: return []
    from simulation import DroneAgent
    for agent in simulation.sim_world.schedule.agents:
        if isinstance(agent, DroneAgent) and agent.unique_id == drone_id:
            # Filter out already discovered cells globally
            # Return up to 10 to keep context size manageable
            remaining = [pos for pos in agent.priority_searching_list if pos not in simulation.sim_world.global_discovered_cells]
            return remaining[:10]
    return []

@mcp.tool()
def get_thermal_memory(drone_id: str) -> list:
    """Returns the list of (x, y) thermal signatures this drone remembers it needs to check."""
    if not simulation.sim_world: return []
    from simulation import DroneAgent
    for agent in simulation.sim_world.schedule.agents:
        if isinstance(agent, DroneAgent) and agent.unique_id == drone_id:
            return agent.thermal_memory
    return []

@mcp.tool()
def mark_cell_discovered(drone_id: str, x: int, y: int) -> str:
    """Marks a cell as completely searched so no other drones explore it."""
    if not simulation.sim_world: return "Error: no sim"
    simulation.sim_world.global_discovered_cells.add((x, y))
    from simulation import DroneAgent
    # Clean from drone's local list if present
    for agent in simulation.sim_world.schedule.agents:
        if isinstance(agent, DroneAgent) and agent.unique_id == drone_id:
            if (x, y) in agent.priority_searching_list:
                agent.priority_searching_list.remove((x, y))
            if (x, y) in agent.thermal_memory:
                agent.thermal_memory.remove((x, y))
    simulation.sim_world.log_action(drone_id, f"Marked ({x}, {y}) as thoroughly searched.")
    return f"Success: marked ({x}, {y}) as discovered."

@mcp.tool()
def move_drone(drone_id: str, x: int, y: int) -> str:
    """
    Moves a rescue drone to specific (x, y) coordinates on the grid.
    Automatically drains battery by 1% per move, or recharges to 100% if moved to Base Camp (9,9).
    Includes Passive Sensors: Scans adjacent grids for obstacles and thermal auras upon arrival.
    """
    if not (0 <= x < 20 and 0 <= y < 20):
        return "Failure: Coordinates out of bounds. Grid is strictly 0 to 19."
        
    world = simulation.sim_world
    if not world: return "Failure: Simulation not running."
    from simulation import DroneAgent, CellAgent, SurvivorAgent
    
    drone = None
    for agent in world.schedule.agents:
        if isinstance(agent, DroneAgent) and agent.unique_id == drone_id:
            drone = agent
            break
            
    if not drone: return f"Error: {drone_id} not found."
    if drone.battery < 2: return f"Failure: {drone_id} battery exhausted. Drone is grounded."

    # Physical obstacles block movement
    for obj in world.grid.get_cell_list_contents([(x, y)]):
        if isinstance(obj, CellAgent) and getattr(obj, "is_obstacle", False):
            obj.obstacle_discovered = True
            world.log_action(drone_id, f"CRITICAL: Flight path to ({x}, {y}) blocked by physical obstacle!")
            return f"Failure: Movement to ({x}, {y}) blocked by an obstacle. Route around it."

    # Move logic
    drone.move((x, y)) 
    
    if x == 9 and y == 9: # Base
        drone.battery = 100
        drone.status = "CHARGING"

    # Passive Sensors
    detected_obstacles = []
    thermal_alert = False
    
    adjacent_coords = [(x, y-1), (x, y+1), (x-1, y), (x+1, y)]
    for ax, ay in adjacent_coords:
        if 0 <= ax < world.width and 0 <= ay < world.height:
            contents = world.grid.get_cell_list_contents([(ax, ay)])
            for obj in contents:
                if isinstance(obj, CellAgent) and getattr(obj, "is_obstacle", False):
                    if not obj.obstacle_discovered:
                        detected_obstacles.append((ax, ay))
                        obj.obstacle_discovered = True
                
                if getattr(obj, "thermal_aura", False):
                    # Survivor not yet found in the grid?
                    cell_survivors = world.grid.get_cell_list_contents([(ax, ay)])
                    is_found = False
                    for possible_sv in cell_survivors:
                        if isinstance(possible_sv, SurvivorAgent) and possible_sv.found:
                            is_found = True
                    if not is_found:
                        thermal_alert = True
                        if (ax, ay) not in drone.thermal_memory:
                            drone.thermal_memory.append((ax, ay))
                elif isinstance(obj, SurvivorAgent) and not getattr(obj, "found", False):
                    thermal_alert = True
                    if (ax, ay) not in drone.thermal_memory:
                        drone.thermal_memory.append((ax, ay))

    log_msg = "Returned to Base Camp. Recharging to 100%." if (x == 9 and y == 9) else f"Moved to sector ({x}, {y})."
    world.log_action(drone_id, log_msg)
    
    response_msg = f"Success: {drone_id} moved to ({x}, {y}). Battery now at {drone.battery}%."
    if detected_obstacles:
        obs_str = ", ".join([f"({ox},{oy})" for ox, oy in detected_obstacles])
        response_msg += f" [PROXIMITY WARNING: New obstacles mapped at {obs_str}.]"
        
    if thermal_alert:
        response_msg += " [SENSOR ALERT: Faint thermal aura detected in an adjacent sector! Added to thermal_memory.]"
        
    return response_msg

@mcp.tool()
def thermal_scan(drone_id: str) -> str:
    """
    Performs a high-powered thermal scan at the drone's EXACT current (x, y) location.
    Returns a message indicating if a hidden survivor was found on this specific grid square.
    """
    world = simulation.sim_world
    if not world: return "Failure: Simulation not running."
    from simulation import DroneAgent, SurvivorAgent
    
    drone = None
    for agent in world.schedule.agents:
        if isinstance(agent, DroneAgent) and agent.unique_id == drone_id:
            drone = agent
            break
            
    if not drone or not drone.pos: return f"Error: {drone_id} not found."
        
    dx, dy = drone.pos
    contents = world.grid.get_cell_list_contents([(dx, dy)])
    
    for obj in contents:
        if isinstance(obj, SurvivorAgent):
            if not obj.found:
                obj.found = True
                world.log_action(drone_id, f"URGENT: Thermal match! Discovered {obj.unique_id} at ({dx}, {dy})!")
                
                # Global condition triggers if all are found
                world.found_survivors += 1 
                if world.total_survivors > 0 and world.found_survivors == world.total_survivors:
                    if not getattr(world, "mission_complete", False):
                        world.mission_complete = True
                        world.log_action("SYSTEM", "🎉 MISSION ACCOMPLISHED! All survivors rescued.")
                
                return f"SUCCESS: Thermal signature detected! {obj.unique_id} found and logged."
            else:
                return "Thermal signature detected, but survivor is already marked as rescued."
                
    return "Scan complete. No thermal signatures detected at this exact location."

@mcp.tool()
def get_mission_data() -> dict:
    """
    Returns global state such as the simulation status.
    """
    world = simulation.sim_world
    if not world: 
        return {"mission_status": "error", "error": "sim offline"}
        
    return {
        "mission_status": "complete" if getattr(world, "mission_complete", False) else "in_progress",
        "remaining_survivors": world.total_survivors - world.found_survivors,
        "global_discovered_count": len(world.global_discovered_cells)
    }

if __name__ == "__main__":
    mcp.run_stdio()
