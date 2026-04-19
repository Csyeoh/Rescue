export interface EntityCoord { x: number; y: number; }

export interface BuildingNode extends EntityCoord { revealed: boolean; }

export interface ObstacleNode extends EntityCoord { discovered: boolean; }

export interface SurvivorNode extends EntityCoord { isRescued: boolean; }

export interface SectorData {
  drone_id: string;
  cx: number;
  cy: number;
  radius: number;
}

export interface EnvironmentState {
  buildings: BuildingNode[];
  obstacles: ObstacleNode[];
  survivors: SurvivorNode[];
  thermalScans: EntityCoord[];
  sectors: SectorData[];
}

export interface DroneStatus {
  id: string;
  battery: number;
  status: 'searching' | 'returning' | 'charging' | 'idle';
  x: number;
  y: number;
  stepsTaken: number;
  heading?: number;                    // yaw in degrees, derived from movement vector
  velocityMag?: number;                // speed magnitude, used for pitch tilt
  trail?: [number, number, number][];  // ring-buffer of last 20 positions
}

export interface SurvivorPoint {
  position: [number, number, number];  // [x, y, z] — z lifted if inside building
  rescued: boolean;                    // true = cyan, false = neon orange
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
  droneCount: number;
}
