export type EntityType = 'empty' | 'building' | 'survivor' | 'base' | 'obstacle';
export type DisasterType = 'typhoon' | 'earthquake' | 'tsunami' | 'fire' | 'flash_flood' | 'default';

export interface GridCell {
  x: number;
  y: number;
  type: EntityType;
  height: number;
  revealed: boolean;
  isIlluminated: boolean;
  isRescued?: boolean;
  hasSurvivor?: boolean;
  obstacleDiscovered?: boolean;
  isThermalScanned?: boolean;
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
  details?: {
    type?: 'reasoning' | 'tool_execution';
    plan?: string;
    task_id?: string;
    ready?: boolean;
    tool_name?: string;
    tool_args?: Record<string, unknown>;
    execution_duration_ms?: number;
    result?: unknown;
    [key: string]: unknown;
  };
}

export interface MissionConfig {
  scenario: string;
  survivors: number;
  droneCount: number;
  obstacleDensity: 'low' | 'med' | 'high';
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
