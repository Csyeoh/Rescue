#!/usr/bin/env python
from typing import Dict, List, Any
from crewai.flow.flow import Flow, listen, start, router, FlowState
from pydantic import BaseModel, Field
import sys
import os
import time

# Add parent dir to path so we can import simulation
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from .crews.rescue_crew.rescue_crew import RescueCrew, DroneIntent, thinking_logger
print(f"[Controller] thinking_logger ID: {id(thinking_logger)}")


class SwarmMissionState(FlowState):
    simulation_active: bool = True
    active_drones: List[str] = []
    tick_count: int = 0
    pending_claims: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


def calculate_obstacle_multiplier(total_discovered: int, total_explored: int) -> float:
    ratio_smoothed = (float(total_discovered) + 2.0) / (float(total_explored) + 10.0)
    gap = 0.15 * (1.0 - ratio_smoothed)
    return 1.0 + ratio_smoothed + gap


def calculate_true_battery_cost(d_commute: float, n_unsearched: float, d_rtb: float, multiplier: float) -> int:
    search_steps = float(n_unsearched) * float(multiplier)
    return int((float(d_commute) + search_steps + float(d_rtb)) * 2.0)


def calculate_detour_penalty(
    current_pos: tuple[int, int],
    target_pos: tuple[int, int],
    base_pos: tuple[int, int] = (9, 9),
) -> int:
    cx, cy = int(current_pos[0]), int(current_pos[1])
    tx, ty = int(target_pos[0]), int(target_pos[1])
    bx, by = int(base_pos[0]), int(base_pos[1])
    direct_distance = abs(cx - tx) + abs(cy - ty)
    detour_distance = (abs(cx - bx) + abs(cy - by)) + (abs(bx - tx) + abs(by - ty))
    return detour_distance - direct_distance


class SimpleSwarmController:
    def __init__(self):
        self.state = SwarmMissionState()
        self.rescue_crew = RescueCrew()

    def _get_exploration_stats(self, world) -> tuple[int, int]:
        from simulation import TerrainAgent
        total_explored_cells = len(getattr(world, "global_discovered_cells", set()))
        total_discovered_obstacles = 0
        for contents, _ in world.grid.coord_iter():
            for obj in contents:
                if isinstance(obj, TerrainAgent) and obj.is_obstacle and obj.obstacle_discovered:
                    total_discovered_obstacles += 1
        return total_discovered_obstacles, total_explored_cells

    def _manhattan(self, a: tuple[int, int], b: tuple[int, int]) -> int:
        return abs(int(a[0]) - int(b[0])) + abs(int(a[1]) - int(b[1]))

    def _remaining_waypoints(self, world, drone) -> list[tuple[int, int]]:
        discovered = getattr(world, "global_discovered_cells", set())
        return [p for p in getattr(drone, "priority_searching_list", []) if p not in discovered]

    def _remove_cells(self, waypoint_list: list[tuple[int, int]], cells: set[tuple[int, int]]) -> list[tuple[int, int]]:
        return [p for p in waypoint_list if p not in cells]

    def _prepend_cells(self, waypoint_list: list[tuple[int, int]], cells: list[tuple[int, int]]) -> list[tuple[int, int]]:
        cell_set = set(cells)
        return list(cells) + [p for p in waypoint_list if p not in cell_set]

    def _apply_pending_claims(self, world, drones_by_id: dict, multiplier: float) -> None:
        base_pos = (9, 9)
        done = []
        for drone_id, payload in self.state.pending_claims.items():
            drone = drones_by_id.get(drone_id)
            if not drone or not drone.pos:
                continue
            if (int(drone.pos[0]), int(drone.pos[1])) != base_pos:
                continue
            if drone.battery < 100:
                continue

            cells = list(payload.get("cells", []))
            if not cells:
                done.append(drone_id)
                continue

            target_pos = tuple(payload.get("target_pos", cells[0]))
            d_commute = self._manhattan(base_pos, target_pos)
            d_rtb = self._manhattan(target_pos, base_pos)
            cost = calculate_true_battery_cost(d_commute, len(cells), d_rtb, multiplier)
            if drone.battery >= cost + 10:
                drone.priority_searching_list = self._prepend_cells(drone.priority_searching_list, cells)
                drone.status = "SEARCHING"
                done.append(drone_id)

        for drone_id in done:
            self.state.pending_claims.pop(drone_id, None)

    def _phase2_idle_detour_reassign(self, world) -> None:
        if not world:
            return

        from simulation import DroneAgent

        drones = [a for a in world.schedule.agents if isinstance(a, DroneAgent)]
        drones_by_id = {d.unique_id: d for d in drones}
        base_pos = (9, 9)

        total_discovered, total_explored = self._get_exploration_stats(world)
        multiplier = calculate_obstacle_multiplier(total_discovered, total_explored)

        remaining_by_id: dict[str, list[tuple[int, int]]] = {}
        for d in drones:
            remaining_by_id[d.unique_id] = self._remaining_waypoints(world, d)

        self._apply_pending_claims(world, drones_by_id, multiplier)

        for drone in drones:
            if not drone.pos:
                continue
            drone_id = drone.unique_id
            if drone_id in self.state.pending_claims:
                drone.status = "RETURNING"
                continue
            if remaining_by_id.get(drone_id):
                continue
            if (int(drone.pos[0]), int(drone.pos[1])) == base_pos:
                continue

            donors = [(len(v), k) for k, v in remaining_by_id.items() if k != drone_id and len(v) > 0]
            if not donors:
                drone.status = "RETURNING"
                continue
            donors.sort(reverse=True)
            donor_id = donors[0][1]
            donor = drones_by_id.get(donor_id)
            donor_cells = remaining_by_id.get(donor_id, [])
            if not donor or not donor_cells:
                drone.status = "RETURNING"
                continue

            curr_pos = (int(drone.pos[0]), int(drone.pos[1]))
            target_pos = min(donor_cells, key=lambda p: self._manhattan(curr_pos, p))
            direct_distance = self._manhattan(curr_pos, target_pos)
            n_target = len(donor_cells)
            n_claim = int((n_target - direct_distance) / 2)
            if n_claim <= 0:
                drone.status = "RETURNING"
                continue

            sorted_cells = sorted(donor_cells, key=lambda p: self._manhattan(curr_pos, p))
            claim_cells = sorted_cells[: min(n_claim, len(sorted_cells))]
            d_rtb = self._manhattan(target_pos, base_pos)
            cost_direct = calculate_true_battery_cost(direct_distance, len(claim_cells), d_rtb, multiplier)

            if drone.battery >= cost_direct + 10:
                donor.priority_searching_list = self._remove_cells(donor.priority_searching_list, set(claim_cells))
                drone.priority_searching_list = self._prepend_cells(drone.priority_searching_list, claim_cells)
                drone.status = "SEARCHING"
                continue

            penalty = calculate_detour_penalty(curr_pos, target_pos, base_pos)
            if penalty <= 4:
                d_commute_after = self._manhattan(base_pos, target_pos)
                cost_after = calculate_true_battery_cost(d_commute_after, len(claim_cells), d_rtb, multiplier)
                if 100 >= cost_after + 10:
                    donor.priority_searching_list = self._remove_cells(donor.priority_searching_list, set(claim_cells))
                    self.state.pending_claims[drone_id] = {"cells": claim_cells, "from": donor_id, "target_pos": target_pos}
                    drone.status = "RETURNING"
                else:
                    drone.status = "RETURNING"
            else:
                drone.status = "RETURNING"

    def _phase3_base_multi_zone_assist(self, world) -> None:
        if not world:
            return

        from simulation import DroneAgent

        base_pos = (9, 9)
        drones = [a for a in world.schedule.agents if isinstance(a, DroneAgent)]
        drones_by_id = {d.unique_id: d for d in drones}

        total_discovered, total_explored = self._get_exploration_stats(world)
        multiplier = calculate_obstacle_multiplier(total_discovered, total_explored)

        remaining_by_id: dict[str, list[tuple[int, int]]] = {}
        for d in drones:
            remaining_by_id[d.unique_id] = self._remaining_waypoints(world, d)

        base_ready = []
        for d in drones:
            if not d.pos:
                continue
            if (int(d.pos[0]), int(d.pos[1])) != base_pos:
                continue
            if int(getattr(d, "battery", 0)) < 100:
                continue
            if remaining_by_id.get(d.unique_id):
                continue
            base_ready.append(d)

        for drone_a in base_ready:
            a_id = drone_a.unique_id
            donors = [(len(v), k) for k, v in remaining_by_id.items() if k != a_id and len(v) > 0]
            donors.sort(reverse=True)
            if not donors:
                continue

            b_id = donors[0][1]
            b_cells = remaining_by_id.get(b_id, [])
            if not b_cells:
                continue

            b_entry = min(b_cells, key=lambda p: self._manhattan(base_pos, p))
            d_base_to_b = self._manhattan(base_pos, b_entry)
            n_b = len(b_cells)
            n_a1 = int((n_b - d_base_to_b) / 2)
            if n_a1 <= 0:
                continue

            b_claim = sorted(b_cells, key=lambda p: self._manhattan(base_pos, p))[: min(n_a1, len(b_cells))]

            chain_ok = False
            c_claim: list[tuple[int, int]] = []
            c_entry = None

            if len(donors) >= 2:
                c_id = donors[1][1]
                c_cells = remaining_by_id.get(c_id, [])
                if c_cells:
                    c_entry = min(c_cells, key=lambda p: self._manhattan(b_entry, p))
                    d_b_to_c = self._manhattan(b_entry, c_entry)

                    if d_b_to_c <= d_base_to_b:
                        n_c = len(c_cells)
                        n_c_remaining = n_c - (d_base_to_b + n_a1 + d_b_to_c)
                        if n_c_remaining > 0:
                            n_a2 = int(n_c_remaining / 2)
                            if n_a2 > 0:
                                d_c_to_base = self._manhattan(c_entry, base_pos)
                                total_cost = int(
                                    (
                                        d_base_to_b
                                        + (n_a1 * multiplier)
                                        + d_b_to_c
                                        + (n_a2 * multiplier)
                                        + d_c_to_base
                                    )
                                    * 2.0
                                )
                                if total_cost + 10 <= 100:
                                    c_claim = sorted(c_cells, key=lambda p: self._manhattan(c_entry, p))[: min(n_a2, len(c_cells))]
                                    if c_claim:
                                        chain_ok = True

            if chain_ok and c_entry is not None:
                drones_by_id[b_id].priority_searching_list = self._remove_cells(
                    drones_by_id[b_id].priority_searching_list,
                    set(b_claim),
                )
                drones_by_id[c_id].priority_searching_list = self._remove_cells(
                    drones_by_id[c_id].priority_searching_list,
                    set(c_claim),
                )
                drone_a.priority_searching_list = self._prepend_cells(
                    drone_a.priority_searching_list,
                    list(b_claim) + list(c_claim),
                )
                drone_a.status = "SEARCHING"
                remaining_by_id[b_id] = [p for p in remaining_by_id[b_id] if p not in set(b_claim)]
                remaining_by_id[c_id] = [p for p in remaining_by_id[c_id] if p not in set(c_claim)]
                remaining_by_id[a_id] = self._remaining_waypoints(world, drone_a)
                continue

            d_rtb = self._manhattan(b_entry, base_pos)
            single_cost = calculate_true_battery_cost(d_base_to_b, len(b_claim), d_rtb, multiplier)
            if 100 >= single_cost + 10:
                drones_by_id[b_id].priority_searching_list = self._remove_cells(
                    drones_by_id[b_id].priority_searching_list,
                    set(b_claim),
                )
                drone_a.priority_searching_list = self._prepend_cells(
                    drone_a.priority_searching_list,
                    list(b_claim),
                )
                drone_a.status = "SEARCHING"
                remaining_by_id[b_id] = [p for p in remaining_by_id[b_id] if p not in set(b_claim)]
                remaining_by_id[a_id] = self._remaining_waypoints(world, drone_a)

    def run(self):
        print("\n[Controller] Starting Mission Control Loop...")
        
        # Phase 0: Partition
        print("[Controller] Phase 0: Map Partitioning...")
        from .tools.partition import get_active_drone_count, partition_grid_greedy_bfs
        num_drones = get_active_drone_count()
        if num_drones > 0:
            partitions = partition_grid_greedy_bfs(num_drones, 9, 9)
            self.state.active_drones = sorted(list(partitions.keys()), key=lambda x: int(x.split("_")[1]))
            # Mark simulation as active
            self.state.simulation_active = True
            print(f"[Controller] Partitioned for {num_drones} drones: {self.state.active_drones}")
        else:
            print("[Controller] No drones found. Exiting.")
            return

        # Main Loop
        import simulation
        from simulation import DroneAgent, resolve_intent
        import websocket_manager
        from .crews.rescue_crew.rescue_crew import thinking_logger
        controller_tick_s = float(os.getenv("CONTROLLER_TICK_S", "1.0"))

        while self.state.simulation_active:
            self.state.tick_count += 1
            print(f"\n--- [Controller] TICK {self.state.tick_count} ---")

            # 1. Build Tasks
            tasks = []
            global_states = {}
            if simulation.sim_world:
                self._phase2_idle_detour_reassign(simulation.sim_world)
                self._phase3_base_multi_zone_assist(simulation.sim_world)
                for agent in simulation.sim_world.schedule.agents:
                    if isinstance(agent, DroneAgent):
                        global_states[agent.unique_id] = agent.status

            for d_id in self.state.active_drones:
                state = global_states.get(d_id, "IDLE")
                if state == "SEARCHING":
                    tasks.append(self.rescue_crew.build_task("searching_task", d_id))
                elif state == "CHARGING":
                    tasks.append(self.rescue_crew.build_task("charging_task", d_id))
                elif state == "RETURNING":
                    tasks.append(self.rescue_crew.build_task("returning_task", d_id))
                elif state == "IDLE":
                    tasks.append(self.rescue_crew.build_task("idle_task", d_id))

            if not tasks:
                print("[Controller] No active tasks. Objective reached?")
                break

            # 2. Execute Crew
            print(f"[Controller] Executing Crew with {len(tasks)} tasks for {self.state.active_drones}...")
            tick_crew = self.rescue_crew.crew(tasks)
            tick_start = time.time()
            try:
                tick_crew.kickoff()
            except Exception as e:
                print(f"[Controller] Crew Execution ERROR: {e}")
            print(f"[Controller] Crew Done in {time.time() - tick_start:.2f}s")
            
            agent_logs = thinking_logger.get_and_flush_logs()
            print(f"[Controller] Captured {len(agent_logs)} thinking logs from event bus (ID: {id(thinking_logger)}).")

            # 6. Check End
            if simulation.sim_world and getattr(simulation.sim_world, "mission_complete", False):
                print("[Controller] MISSION COMPLETE!")
                break
            
            time.sleep(controller_tick_s)

def kickoff():
    controller = SimpleSwarmController()
    controller.run()


if __name__ == "__main__":
    kickoff()
