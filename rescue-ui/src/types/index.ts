export type EntityType = 'empty' | 'building' | 'survivor' | 'base' | 'obstacle';
export type DisasterType = 'typhoon' | 'earthquake' | 'tsunami' | 'fire' | 'flash_flood' | 'default';

export interface GridCell {
  x: number;
  y: number;
  type: EntityType;
  height: number; // 1-9 for elevation
  revealed: boolean;
  isIlluminated: boolean;
  isRescued?: boolean;
  hasSurvivor?: boolean;
  obstacleDiscovered?: boolean;
  altitude?: number;
}

export interface DroneStatus {
  id: string;
  battery: number;
  status: 'patrolling' | 'returning' | 'charging' | 'idle';
  x: number;
  y: number;
  stepsTaken: number;
}

export interface LogEntry {
  id: string;
  timestamp: string;
  agent: string;
  message: string;
  type: 'info' | 'warning' | 'success' | 'error';
}

export interface MissionConfig {
  survivors: number;
  droneCount: number;
  obstacleDensity: number;
  buildingHeight: number;
  terrainHeight: number;
  disasterType: DisasterType;
  difficulty: 'easy' | 'normal' | 'hard';
  // Environmental Unknowns
  windSpeed: number;
  windDirection: string;
  debrisProb: number;
  rainfall: number;
  aftershockProb: number;
  collapseRisk: number;
  waterFlow: number;
  secondaryWave: number;
  waterLevel: number;
  fireSpread: number;
  smokeDensity: number;
  heatZones: number;
  risingSpeed: number;
}
