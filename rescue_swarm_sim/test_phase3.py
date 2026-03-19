from __future__ import annotations
from dataclasses import dataclass

def _build_target_cells(target_pos: tuple[int, int], n: int) -> list[tuple[int, int]]:
    tx, ty = target_pos
    cells: list[tuple[int, int]] = [(tx, ty)]
    step = 1
    while len(cells) < n:
        for dx, dy in [(step, 0), (-step, 0), (0, step), (0, -step)]:
            if len(cells) >= n:
                break
            cells.append((tx + dx, ty + dy))
        step += 1
    return cells[:n]

@dataclass
class FakeCellAgent:
    is_obstacle: bool = False
    obstacle_discovered: bool = False

@dataclass
class FakeDroneAgent:
    unique_id: str
    pos: tuple[int, int]
    battery: int
    status: str
    priority_searching_list: list[tuple[int, int]]

@dataclass
class FakeSchedule:
    agents: list

class FakeGrid:
    def __init__(self, discovered_obstacles: int):
        self._cells = [[FakeCellAgent(is_obstacle=True, obstacle_discovered=True)] for _ in range(discovered_obstacles)]

    def coord_iter(self):
        for i, contents in enumerate(self._cells):
            yield contents, (i, 0)

@dataclass
class FakeWorld:
    schedule: FakeSchedule
    grid: FakeGrid
    global_discovered_cells: set[tuple[int, int]]

def _run_phase3_scenario(scenario_name: str, target_c_pos: tuple[int, int]):
    import simulation
    # Ensure this import matches where your SimpleSwarmController lives!
    try:
        from swarm_flow.main import SimpleSwarmController
    except ImportError:
        from main import SimpleSwarmController

    total_explored = 50
    total_discovered_obstacles = 5
    base_pos = (9, 9)

    # Base Drone A (100% Battery)
    drone_a = FakeDroneAgent(
        unique_id="drone_a", pos=base_pos, battery=100, status="IDLE", priority_searching_list=[]
    )

    # Active Drone B (Distance = 4)
    drone_b = FakeDroneAgent(
        unique_id="drone_b", pos=(9, 13), battery=80, status="SEARCHING", 
        priority_searching_list=_build_target_cells((9, 13), 14)
    )

    # Active Drone C (Distance to B varies based on scenario)
    drone_c = FakeDroneAgent(
        unique_id="drone_c", pos=target_c_pos, battery=80, status="SEARCHING", 
        priority_searching_list=_build_target_cells(target_c_pos, 20)
    )

    world = FakeWorld(
        schedule=FakeSchedule(agents=[drone_a, drone_b, drone_c]),
        grid=FakeGrid(discovered_obstacles=total_discovered_obstacles),
        global_discovered_cells=set((i % 20, i // 20) for i in range(total_explored)),
    )

    original_drone_agent = simulation.DroneAgent
    original_terrain_agent = simulation.TerrainAgent
    simulation.DroneAgent = FakeDroneAgent
    simulation.TerrainAgent = FakeCellAgent
    
    try:
        controller = SimpleSwarmController()
        controller._phase3_base_multi_zone_assist(world)

        claimed_total = len(drone_a.priority_searching_list)
        print(f"Result -> status={drone_a.status}, total_cells_claimed={claimed_total}")
        if claimed_total > 5:
            print("Decision: DOUBLE-DIP SUCCESSFUL (Claimed from B and C)")
        elif claimed_total > 0:
            print("Decision: SINGLE MISSION (Claimed from B only)")
        else:
            print("Decision: STAY IDLE")
            
    finally:
        simulation.DroneAgent = original_drone_agent
        simulation.TerrainAgent = original_terrain_agent

def main() -> None:
    print("\n--- Phase 3 Test: Multi-Zone Assist (Double-Dip) ---")
    print("Scenario A: Target C is close at (12,13) [Expect: DOUBLE-DIP]")
    _run_phase3_scenario("Scenario A", (12, 13))
    
    print("\nScenario B: Target C is far at (2,2) [Expect: SINGLE MISSION]")
    _run_phase3_scenario("Scenario B", (2, 2))
    print("--- Tests Complete ---\n")

if __name__ == "__main__":
    main()