import { EnvironmentState, BuildingNode, ObstacleNode, SurvivorNode } from "../types";

export const initializeEnvironmentState = (map_data: any): EnvironmentState => {
  const state: EnvironmentState = {
    buildings: [],
    obstacles: [],
    survivors: [],
    thermalScans: [],
    bases: [],
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
    const x = Number(s.x);
    const y = Number(s.y);
    state.survivors.push({
      id: String(s.id ?? `survivor_${Math.floor(x)}_${Math.floor(y)}`),
      x,
      y,
      isRescued: Boolean(s.discovered),
      foundTick: s.found_tick !== undefined && s.found_tick !== null ? Number(s.found_tick) : null,
    });
  }

  const bases = map_data?.bases ?? [{ x: 9, y: 9 }];
  for (const bs of bases) {
    state.bases.push({
      x: Number(bs.x),
      y: Number(bs.y),
    });
  }

  return state;
};
