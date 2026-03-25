import { BASE_X, BASE_Y, GRID_SIZE } from "../constants";
import { GridCell, MissionConfig, EntityType } from "../types";

export const toBackendConfig = (cfg: MissionConfig) => {
  const scenario = cfg.scenario || 'mixed urban';
  const num_drones = Math.max(3, Math.min(5, Number(cfg.droneCount) || 3));
  const num_survivors = Math.max(1, Math.min(20, Number(cfg.survivors) || 1));
  const obstacle_difficulty = cfg.obstacleDensity; // It is already 'low' | 'med' | 'high'
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
      const isBase = x === BASE_X && y === BASE_Y;
      const type: EntityType = isBase ? 'base' : 'empty';
      row.push({
        x,
        y,
        type,
        height: type === 'base' ? 9 : 1,
        revealed: isBase,
        isIlluminated: isBase,
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
    
    cell.altitude = Number(c.altitude ?? 0);
    cell.buildingHeight = Number(c.building_height ?? 0);

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
      const scaled = Math.max(1, Math.min(9, Math.round((cell.altitude / 100) * 8) + 1));
      cell.height = scaled;
    }
  }

  const survivors = map_data?.survivors ?? [];
  for (const s of survivors) {
    const x = Number(s.x);
    const y = Number(s.y);
    if (!(x >= 0 && x < GRID_SIZE && y >= 0 && y < GRID_SIZE)) continue;
    // FAIL-SAFE: Never render a survivor at the base station (9,9)
    if (x === BASE_X && y === BASE_Y) continue;
    
    const cell = newGrid[y][x];
    cell.hasSurvivor = true;
    cell.isRescued = Boolean(s.discovered);
  }
  return newGrid;
};
