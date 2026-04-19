import { EnvironmentState, BuildingNode, ObstacleNode, SurvivorNode } from "../types";

export const initializeEnvironmentState = (map_data: any): EnvironmentState => {
  const state: EnvironmentState = {
    buildings: [],
    obstacles: [],
    survivors: [],
    thermalScans: [],
    sectors: []
  };

  const obstacles = map_data?.obstacles ?? [];
  for (const c of obstacles) {
    state.obstacles.push({
      x: Number(c.x),
      y: Number(c.y),
      discovered: Boolean(c.discovered),
    });
  }

  const buildings = map_data?.buildings ?? [];
  for (const b of buildings) {
    state.buildings.push({
      x: Number(b.x),
      y: Number(b.y),
      revealed: Boolean(b.revealed),
    });
  }

  const survivors = map_data?.survivors ?? [];
  for (const s of survivors) {
    state.survivors.push({
      x: Number(s.x),
      y: Number(s.y),
      isRescued: Boolean(s.discovered),
    });
  }

  return state;
};
