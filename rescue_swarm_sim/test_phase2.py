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
        self._cells: list[list] = [[FakeCellAgent(is_obstacle=True, obstacle_discovered=True)] for _ in range(discovered_obstacles)]

    def coord_iter(self):
        for i, contents in enumerate(self._cells):
            yield contents, (i, 0)


@dataclass
class FakeWorld:
    schedule: FakeSchedule
    grid: FakeGrid
    global_discovered_cells: set[tuple[int, int]]


def _run_scenario(battery: int) -> None:
    import simulation
    from swarm_flow.main import SimpleSwarmController

    total_explored = 50
    total_discovered_obstacles = 5

    current_pos = (5, 9)
    base_pos = (9, 9)
    target_pos = (15, 9)
    n_target = 20

    idle_drone = FakeDroneAgent(
        unique_id="drone_1",
        pos=current_pos,
        battery=battery,
        status="IDLE",
        priority_searching_list=[],
    )

    donor_cells = _build_target_cells(target_pos, n_target)
    donor_drone = FakeDroneAgent(
        unique_id="drone_2",
        pos=base_pos,
        battery=100,
        status="SEARCHING",
        priority_searching_list=list(donor_cells),
    )

    world = FakeWorld(
        schedule=FakeSchedule(agents=[idle_drone, donor_drone]),
        grid=FakeGrid(discovered_obstacles=total_discovered_obstacles),
        global_discovered_cells=set((i % 20, i // 20) for i in range(total_explored)),
    )

    original_drone_agent = simulation.DroneAgent
    original_cell_agent = simulation.CellAgent
    simulation.DroneAgent = FakeDroneAgent
    simulation.CellAgent = FakeCellAgent
    try:
        controller = SimpleSwarmController()
        controller._phase2_idle_detour_reassign(world)

        if idle_drone.status == "SEARCHING":
            decision = "GO_DIRECT"
        elif idle_drone.unique_id in controller.state.pending_claims:
            decision = "ROUTE_TO_BASE_RECHARGE_THEN_TARGET"
        else:
            decision = "RETURN_TO_BASE"

        print(f"Battery={battery}% -> status={idle_drone.status}, decision={decision}, claimed_cells={len(idle_drone.priority_searching_list)}")
    finally:
        simulation.DroneAgent = original_drone_agent
        simulation.CellAgent = original_cell_agent


def main() -> None:
    print("--- Phase 2 Test: IDLE Pass-By + Dispatch Check ---")
    print("Scenario A: Battery=80 (expect GO_DIRECT)")
    _run_scenario(80)
    print("Scenario B: Battery=30 (expect ROUTE_TO_BASE_RECHARGE_THEN_TARGET)")
    _run_scenario(30)
    print("--- Tests Complete ---")


if __name__ == "__main__":
    main()

