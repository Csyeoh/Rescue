import { BASE_X, BASE_Y, GRID_SIZE } from "../constants";
import { GridCell, MissionConfig, EntityType } from "../types";

export const toBackendConfig = (cfg: MissionConfig) => {
  const scenarioMap: Record<string, string> = {
    typhoon: 'coastal',
    tsunami: 'coastal',
    earthquake: 'downtown',
    fire: 'industrial',
    flash_flood: 'suburban',
    default: 'mixed',
  };
  const scenario = scenarioMap[cfg.disasterType] ?? 'mixed';
  const num_drones = Math.max(1, Math.min(10, Number(cfg.droneCount) || 3));
  const num_survivors = Math.max(0, Math.min(100, Number(cfg.survivors) || 0));
  const d = Number(cfg.obstacleDensity) || 0;
  const obstacle_difficulty = d <= 7 ? 'low' : d <= 15 ? 'med' : 'high';
  return {
    scenario,
    num_drones,
    drone_battery: 100,
    num_survivors,
    obstacle_difficulty,
  };
};

export const buildGridFromMapData = (map_data: any): GridCell[][] => {
  const newGrid: GridCell[][] = [];
  for (let y = 0; y < GRID_SIZE; y++) {
    const row: GridCell[] = [];
    for (let x = 0; x < GRID_SIZE; x++) {
      const type: EntityType = x === BASE_X && y === BASE_Y ? 'base' : 'empty';
      row.push({
        x,
        y,
        type,
        height: type === 'base' ? 9 : 1,
        revealed: true,
        isIlluminated: false,
        isRescued: false,
        hasSurvivor: false,
        obstacleDiscovered: false,
      });
    }
    newGrid.push(row);
  }

  const cells = map_data?.cells ?? [];
  for (const c of cells) {
    const x = Number(c.x);
    const y = Number(c.y);
    if (!(x >= 0 && x < GRID_SIZE && y >= 0 && y < GRID_SIZE)) continue;
    const cell = newGrid[y][x];
    if (x === BASE_X && y === BASE_Y) continue;
    const terrainType = String(c.terrain_type ?? '');
    const isObstacle = Boolean(c.is_obstacle);
    if (isObstacle) {
      cell.type = 'obstacle';
      cell.obstacleDiscovered = Boolean(c.obstacle_discovered);
    } else if (terrainType === 'single_story' || terrainType === 'multiple_story') {
      cell.type = 'building';
    } else {
      cell.type = 'empty';
    }
    if (cell.type === 'building') {
      cell.height = terrainType === 'multiple_story' ? 2 : 1;
    } else {
      const alt = Number(c.altitude ?? 0);
      const scaled = Math.max(1, Math.min(9, Math.round((alt / 100) * 8) + 1));
      cell.height = scaled;
    }
  }

  const survivors = map_data?.survivors ?? [];
  for (const s of survivors) {
    const x = Number(s.x);
    const y = Number(s.y);
    if (!(x >= 0 && x < GRID_SIZE && y >= 0 && y < GRID_SIZE)) continue;
    const cell = newGrid[y][x];
    cell.hasSurvivor = true;
    cell.isRescued = Boolean(s.discovered);
  }
  return newGrid;
};
