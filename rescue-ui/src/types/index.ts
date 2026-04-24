export interface EntityCoord { x: number; y: number; }

export interface BuildingNode extends EntityCoord { revealed: boolean; }

export interface ObstacleNode extends EntityCoord { discovered: boolean; }

export interface SurvivorNode extends EntityCoord { isRescued: boolean; }



export interface ThermalScanNode {
  cx: number;
  cy: number;
  angle: number;
  arc: number;
  radius: number;
  createdAt?: number;
}

export interface EnvironmentState {
  buildings: BuildingNode[];
  obstacles: ObstacleNode[];
  survivors: SurvivorNode[];
  thermalScans: ThermalScanNode[];
  bases: EntityCoord[];
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
  tick?: number;
  agent: string;
  message: string;
  type: 'info' | 'warning' | 'success' | 'error' | 'reasoning' | 'tool_call' | 'tool_response';
  details?: {
    type?: 'reasoning' | 'tool_call' | 'tool_response';
    // Reasoning
    thought?: string;          // sentence under [THOUGHT: True]
    // Tool call / response
    tool_name?: string;
    tool_args?: Record<string, unknown>;
    result_message?: string;   // human-readable result from the MCP tool
    [key: string]: unknown;
  };
}

export interface MissionConfig {
  droneCount: number;
}

export interface ThermalZone {
  id: string;
  polygon: number[][]; // [x, y, z]
  createdAt: number;
}
export interface CoverageCell {
  x: number; // x_idx (0-39)
  y: number; // y_idx (0-39)
}
