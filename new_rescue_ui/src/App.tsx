/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useRef } from 'react';
import { 
  Settings, 
  Activity, 
  Terminal, 
  Map as MapIcon, 
  Drone, 
  Users, 
  Waves, 
  Building2, 
  Mountain, 
  ShieldAlert,
  Play,
  Square,
  Eye,
  EyeOff,
  Trees,
  Battery,
  Home,
  Droplets,
  ChevronDown,
  ChevronUp,
  ChevronLeft,
  ChevronRight,
  Sliders
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

// --- Types ---
type EntityType = 'empty' | 'building' | 'survivor' | 'base' | 'obstacle';
type DisasterType = 'typhoon' | 'earthquake' | 'tsunami' | 'fire' | 'flash_flood' | 'default';

interface GridCell {
  x: number;
  y: number;
  type: EntityType;
  height: number; // 1-9 for elevation
  revealed: boolean;
  isIlluminated: boolean;
  isRescued?: boolean;
  hasSurvivor?: boolean;
  obstacleDiscovered?: boolean;
}

interface DroneStatus {
  id: string;
  battery: number;
  status: 'patrolling' | 'returning' | 'charging' | 'idle';
  x: number;
  y: number;
  stepsTaken: number;
}

interface LogEntry {
  id: string;
  timestamp: string;
  agent: string;
  message: string;
  type: 'info' | 'warning' | 'success' | 'error';
}

const GRID_SIZE = 20;
const BASE_X = 9;
const BASE_Y = 9;

const API_BASE: string = (import.meta as any).env?.VITE_API_BASE_URL ?? 'http://localhost:8000';
const WS_BASE = API_BASE.startsWith('https://')
  ? API_BASE.replace('https://', 'wss://')
  : API_BASE.replace('http://', 'ws://');
const WS_URL = `${WS_BASE}/ws`;

// Elevation Color Maps (Darker = Lower, Lighter = Higher)
// Base color: #7fff94 to #53a560
const TERRAIN_COLORS: Record<DisasterType, Record<number, string>> = {
  default: {
    1: '#53a560', 2: '#59bc66', 3: '#5fc36d',
    4: '#65ca73', 5: '#6bd17a', 6: '#71d880',
    7: '#77df87', 8: '#7de68d', 9: '#7fff94',
  },
  typhoon: {
    1: '#53a560', 2: '#59bc66', 3: '#5fc36d',
    4: '#65ca73', 5: '#6bd17a', 6: '#71d880',
    7: '#77df87', 8: '#7de68d', 9: '#7fff94',
  },
  earthquake: {
    1: '#53a560', 2: '#59bc66', 3: '#5fc36d',
    4: '#65ca73', 5: '#6bd17a', 6: '#71d880',
    7: '#77df87', 8: '#7de68d', 9: '#7fff94',
  },
  tsunami: {
    1: '#53a560', 2: '#59bc66', 3: '#5fc36d',
    4: '#65ca73', 5: '#6bd17a', 6: '#71d880',
    7: '#77df87', 8: '#7de68d', 9: '#7fff94',
  },
  fire: {
    1: '#53a560', 2: '#59bc66', 3: '#5fc36d',
    4: '#65ca73', 5: '#6bd17a', 6: '#71d880',
    7: '#77df87', 8: '#7de68d', 9: '#7fff94',
  },
  flash_flood: {
    1: '#53a560', 2: '#59bc66', 3: '#5fc36d',
    4: '#65ca73', 5: '#6bd17a', 6: '#71d880',
    7: '#77df87', 8: '#7de68d', 9: '#7fff94',
  }
};

const BUILDING_COLORS = {
  light: '#ff8a8a', // Single-story
  dark: '#b30000',  // Multi-story
};

export default function App() {
  // --- State ---
  const [view, setView] = useState<'dashboard' | 'config'>('dashboard');
  const [isSimulationRunning, setIsSimulationRunning] = useState(false);
  const [isAborting, setIsAborting] = useState(false);
  const [isMapGenerated, setIsMapGenerated] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isLogOpen, setIsLogOpen] = useState(true);
  const [isSwarmPanelOpen, setIsSwarmPanelOpen] = useState(true);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const logEndRef = useRef<HTMLDivElement>(null);

  // Simulation Config
  const [config, setConfig] = useState({
    survivors: 10,
    droneCount: 5,
    obstacleDensity: 15,
    buildingHeight: 7,
    terrainHeight: 5,
    disasterType: 'default' as DisasterType,
    difficulty: 'normal' as 'easy' | 'normal' | 'hard',
    // Environmental Unknowns
    windSpeed: 20,
    windDirection: 'NE',
    debrisProb: 5,
    rainfall: 10,
    aftershockProb: 8,
    collapseRisk: 12,
    waterFlow: 15,
    secondaryWave: 30,
    waterLevel: 2,
    fireSpread: 10,
    smokeDensity: 25,
    heatZones: 5,
    risingSpeed: 0.5,
  });

  // Mission Progress
  const [survivorsFound, setSurvivorsFound] = useState(0);
  const [survivorsDetected, setSurvivorsDetected] = useState(0);
  const [revealedCells, setRevealedCells] = useState(0);

  // Drones
  const [drones, setDrones] = useState<DroneStatus[]>([]);
  const [expandedDroneId, setExpandedDroneId] = useState<string | null>(null);
  const [mapData, setMapData] = useState<any | null>(null);
  const discoveredRef = useRef<Set<string>>(new Set());
  const wsRef = useRef<WebSocket | null>(null);

  // Grid State
  const [grid, setGrid] = useState<GridCell[][]>([]);

  // --- Initialization & Reset ---
  const resetMission = async (newConfig = config) => {
    try {
      await fetch(`${API_BASE}/api/reset`, { method: 'POST' });
    } catch (e) {
      console.error("Failed to reset backend:", e);
    }

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
    setGrid(newGrid);
    setSurvivorsFound(0);
    setSurvivorsDetected(0);
    discoveredRef.current = new Set();
    setRevealedCells(0);
    setIsSimulationRunning(false);
    setMapData(null);
    setIsMapGenerated(false);
    setIsGenerating(false);

    const initialDrones: DroneStatus[] = Array.from({ length: newConfig.droneCount }).map((_, i) => ({
      id: `drone_${i + 1}`,
      battery: 100,
      status: 'idle',
      x: BASE_X,
      y: BASE_Y,
      stepsTaken: 0
    }));
    setDrones(initialDrones);
    setLogs([]);
    addLog('SYSTEM', `Ready. Configure mission and generate a map preview.`, 'info');
  };

  const toBackendConfig = (cfg = config) => {
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

  const buildGridFromMapData = (map_data: any): GridCell[][] => {
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

  const generateMapPreview = async (cfg = config): Promise<any | null> => {
    setIsGenerating(true);
    try {
      const bcfg = toBackendConfig(cfg);
      const r = await fetch(`${API_BASE}/api/generate_map`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenario: bcfg.scenario,
          drone_battery: bcfg.drone_battery,
          num_survivors: bcfg.num_survivors,
          obstacle_difficulty: bcfg.obstacle_difficulty,
        }),
      });
      const json = await r.json();
      if (!r.ok || json?.status !== 'success') {
        addLog('SYSTEM', `Generate map failed: ${json?.message ?? r.status}`, 'error');
        return null;
      }
      setMapData(json.map_data);
      setGrid(buildGridFromMapData(json.map_data));
      discoveredRef.current = new Set();
      setRevealedCells(0);
      setSurvivorsFound(0);
      setSurvivorsDetected(0);
      setIsMapGenerated(true);
      addLog('SYSTEM', 'Map preview generated. Awaiting deployment.', 'success');
      return json.map_data;
    } catch (e: any) {
      addLog('SYSTEM', `Generate map failed: ${e?.message ?? String(e)}`, 'error');
      return null;
    } finally {
      setIsGenerating(false);
    }
  };

  useEffect(() => {
    resetMission();
  }, []);

  useEffect(() => {
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      addLog('SYSTEM', 'WebSocket connected.', 'success');
    };
    ws.onerror = () => {
      addLog('SYSTEM', 'WebSocket error.', 'error');
    };
    ws.onclose = () => {
      addLog('SYSTEM', 'WebSocket closed.', 'warning');
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'partitioning_start') {
          addLog('SYSTEM', msg.payload?.message ?? 'Partitioning started.', 'info');
          return;
        }

        if (msg.type === 'partitioning_complete') {
          const payload = msg.payload ?? {};
          if (payload?.terrain) {
            const map_data = { cells: payload.terrain, survivors: payload.survivors ?? [] };
            setGrid(buildGridFromMapData(map_data));
          }
          if (Array.isArray(payload?.drones)) {
            setDrones(payload.drones.map((d: any) => ({
              id: String(d.id),
              x: Number(d.x),
              y: Number(d.y),
              battery: Number(d.battery ?? 100),
              status: String(d.status ?? '').toUpperCase() === 'RETURNING' ? 'returning'
                : String(d.status ?? '').toUpperCase() === 'CHARGING' ? 'charging'
                : String(d.status ?? '').toUpperCase() === 'IDLE' ? 'idle'
                : 'patrolling',
              stepsTaken: 0,
            })));
          }
          addLog('SYSTEM', 'Partitioning complete. Mission running.', 'success');
          return;
        }

        if (msg.type === 'tick_update') {
          const payload = msg.payload ?? {};
          // MAPPING FIX: Match backend keys (drones, terrain, logs, survivors)
          const drone_states = Array.isArray(payload.drones) ? payload.drones : [];
          const map_updates = Array.isArray(payload.terrain) ? payload.terrain : [];
          const agent_logs = Array.isArray(payload.logs) ? payload.logs : [];
          const survivors = Array.isArray(payload.survivors) ? payload.survivors : [];

          // AUTO-STOP UI: If drones disappear after a mission was running, the simulation has reset.
          if (isSimulationRunning && drone_states.length === 0 && revealedCells > 10) {
            setIsSimulationRunning(false);
          }

          setDrones((prev) => {
            const prevById = new Map<string, DroneStatus>(prev.map((d) => [d.id, d] as [string, DroneStatus]));
            return drone_states.map((ds: any) => {
              const id = String(ds.id);
              const prevD = prevById.get(id);
              return {
                id,
                x: Number(ds.x),
                y: Number(ds.y),
                battery: Number(ds.battery ?? prevD?.battery ?? 100),
                status: String(ds.status ?? '').toUpperCase() === 'RETURNING' ? 'returning'
                  : String(ds.status ?? '').toUpperCase() === 'CHARGING' ? 'charging'
                  : String(ds.status ?? '').toUpperCase() === 'IDLE' ? 'idle'
                  : 'patrolling',
                stepsTaken: (prevD?.stepsTaken ?? 0) + 1,
              };
            });
          });

          setGrid((prevGrid) => {
            if (!prevGrid?.length) return prevGrid;
            const next = prevGrid.map(row => row.map(cell => ({ ...cell, isIlluminated: false, revealed: true })));

            for (const upd of map_updates) {
              const x = Number(upd.x);
              const y = Number(upd.y);
              if (!(x >= 0 && x < GRID_SIZE && y >= 0 && y < GRID_SIZE)) continue;
              const cell = next[y][x];
              cell.altitude = upd.altitude;
              cell.type = upd.is_obstacle ? 'obstacle' : (upd.terrain_type === 'single_story' || upd.terrain_type === 'multiple_story' ? 'building' : 'empty');
              cell.obstacleDiscovered = Boolean(upd.obstacle_discovered);
              discoveredRef.current.add(`${x},${y}`);
            }

            // Sync survivors state
            for (const s of survivors) {
              const x = Number(s.x);
              const y = Number(s.y);
              if (!(x >= 0 && x < GRID_SIZE && y >= 0 && y < GRID_SIZE)) continue;
              const cell = next[y][x];
              cell.hasSurvivor = true;
              cell.isRescued = Boolean(s.discovered);
            }

            for (const ds of drone_states) {
              const x = Number(ds.x);
              const y = Number(ds.y);
              const coords = [
                [x, y],
                [x + 1, y],
                [x - 1, y],
                [x, y + 1],
                [x, y - 1],
              ];
              for (const [cx, cy] of coords) {
                if (cx >= 0 && cx < GRID_SIZE && cy >= 0 && cy < GRID_SIZE) {
                  next[cy][cx].isIlluminated = true;
                }
              }
            }

            const rescued = next.flat().filter(c => c.isRescued).length;
            setSurvivorsFound(rescued);
            setSurvivorsDetected(rescued);
            setRevealedCells(discoveredRef.current.size);
            return next;
          });

          for (const l of agent_logs) {
            const agent = l?.drone ? String(l.drone) : 'AGENT';
            const message = l?.message ? String(l.message) : JSON.stringify(l);
            addLog(agent, message, 'info');
          }
          return;
        }

        if (msg.type === 'mission_complete') {
          addLog('SYSTEM', msg.payload?.message ?? 'Mission complete.', 'success');
          setIsSimulationRunning(false);
          return;
        }
      } catch (e) {
        console.error("WS message error:", e);
        addLog('SYSTEM', 'WS message parse error.', 'warning');
      }
    };


    return () => {
      ws.close();
    };
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  // --- Helpers ---
  const addLog = (agent: string, message: string, type: LogEntry['type'] = 'info') => {
    const newLog: LogEntry = {
      id: Math.random().toString(36).substr(2, 9),
      timestamp: new Date().toLocaleTimeString(),
      agent,
      message,
      type,
    };
    setLogs(prev => [...prev, newLog]);
  };

  const toggleSimulation = () => {
    (async () => {
      if (!isSimulationRunning) {
        if (!isMapGenerated || !mapData) {
          alert('Warning: Please generate a map first before deploying the swarm!');
          return;
        }
        try {
          const bcfg = toBackendConfig(config);
          const r = await fetch(`${API_BASE}/api/start_mission`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              scenario: bcfg.scenario,
              num_drones: bcfg.num_drones,
              drone_battery: bcfg.drone_battery,
              num_survivors: bcfg.num_survivors,
              obstacle_difficulty: bcfg.obstacle_difficulty,
              map_data: mapData,
            }),
          });
          const json = await r.json();
          if (!r.ok || json?.status !== 'success') {
            addLog('SYSTEM', `Start mission failed: ${json?.message ?? r.status}`, 'error');
            return;
          }
          addLog('COMMAND', 'Deploying swarm from Central Base.', 'info');
          setIsSimulationRunning(true);
          setIsAborting(false);
        } catch (e: any) {
          addLog('SYSTEM', `Start mission failed: ${e?.message ?? String(e)}`, 'error');
        }
      } else {
        // ABORT MISSION LOGIC
        setIsAborting(true);
        try {
          const r = await fetch(`${API_BASE}/api/abort`, { method: 'POST' });
          if (r.ok) {
            addLog('COMMAND', 'ABORT SIGNAL SENT: Recalling all drones.', 'warning');
          } else {
            addLog('SYSTEM', 'Abort failed.', 'error');
            setIsAborting(false);
          }
        } catch (e) {
          addLog('SYSTEM', 'Abort request failed.', 'error');
          setIsAborting(false);
        }
      }
    })();
  };

  const downloadLogsAsText = () => {
    const logText = logs
      .map((log) => `[${log.timestamp}] [${log.agent}] ${log.message}`)
      .join('\n');
    const blob = new Blob([logText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'mission_log.txt';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="h-screen flex flex-col bg-[#e1fef0] text-slate-900 p-2 gap-2 overflow-hidden">
      {/* Top Bar */}
      <header className="flex items-center justify-between bg-white/80 backdrop-blur-sm px-6 py-2 rounded-xl shadow-sm border border-[#6aa7ad]/20 shrink-0 mx-2 mt-2">
        <div className="flex items-center gap-4">
          <div className="bg-azure-dark p-2 rounded-xl shadow-inner">
            <Drone className="text-white w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-black tracking-tighter text-neutral-dark">AEGIS EDGE COMMAND</h1>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-[10px] font-bold text-azure-mid uppercase tracking-widest">Autonomous Rescue Protocol v4.2</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex flex-col items-end mr-4">
            <span className="text-[10px] font-black text-azure-mid uppercase tracking-widest">Map Discovery</span>
            <div className="flex items-center gap-2">
              <span className="text-xl font-black text-emerald-500">{Math.min(100, Math.floor((revealedCells / (GRID_SIZE * GRID_SIZE)) * 100))}%</span>
              <div className="w-24 h-2 bg-mint-bg border border-azure-pale rounded-full overflow-hidden">
                <motion.div 
                  className="h-full bg-emerald-500"
                  animate={{ width: `${Math.min(100, (revealedCells / (GRID_SIZE * GRID_SIZE)) * 100)}%` }}
                />
              </div>
            </div>
          </div>
          <div className="flex flex-col items-end mr-4">
            <span className="text-[10px] font-black text-azure-mid uppercase tracking-widest">Survivors Detected</span>
            <div className="flex items-center gap-2">
              <span className="text-xl font-black text-blue-500">{survivorsDetected}/{config.survivors}</span>
              <div className="w-24 h-2 bg-mint-bg border border-azure-pale rounded-full overflow-hidden">
                <motion.div 
                  className="h-full bg-blue-500"
                  animate={{ width: `${(survivorsDetected / config.survivors) * 100}%` }}
                />
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 bg-mint-bg px-4 py-2 rounded-xl border border-azure-pale">
            <ShieldAlert size={16} className="text-alert-orange" />
            <span className="text-xs font-bold text-azure-dark uppercase">Scenario: {config.disasterType}</span>
          </div>
          <button 
            onClick={toggleSimulation}
            disabled={isAborting}
            className={`flex items-center gap-2 px-8 py-3 rounded-xl font-black transition-all transform active:scale-95 shadow-lg ${
              isSimulationRunning 
                ? 'bg-alert-red text-white hover:bg-alert-orange' 
                : 'bg-alert-yellow text-neutral-dark hover:brightness-105'
            } ${isAborting ? 'opacity-70 cursor-not-allowed' : ''}`}
          >
            {isSimulationRunning ? <Square size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" />}
            {isSimulationRunning ? (isAborting ? 'ABORTING...' : 'ABORT MISSION') : 'DEPLOY SWARM'}
          </button>
        </div>
      </header>

      {view === 'config' ? (
        <ConfigPage 
          config={config} 
          onSave={async (newConfig) => {
            setConfig(newConfig);
            resetMission(newConfig);
            await generateMapPreview(newConfig);
            setView('dashboard');
          }} 
          onCancel={() => setView('dashboard')}
        />
      ) : (
        <div className="flex-1 flex gap-2 overflow-hidden">
          {/* Left Sidebar: Config */}
          <aside className="w-64 flex flex-col gap-2 shrink-0 overflow-y-auto custom-scrollbar pr-1">
            <div className="bg-white p-5 rounded-2xl shadow-sm border border-azure-pale/50">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-2">
                  <Settings className="text-azure-dark" size={20} />
                  <h2 className="font-bold text-neutral-dark uppercase text-sm tracking-tight">Mission Configuration</h2>
                </div>
                <button 
                  onClick={() => setView('config')}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-yellow-400 hover:bg-yellow-500 text-azure-dark rounded-lg shadow-sm transition-all transform active:scale-95 border border-yellow-500/20 group"
                  title="Edit Mission Parameters"
                >
                  <Sliders size={14} className="group-hover:rotate-12 transition-transform" />
                  <span className="text-[10px] font-black uppercase tracking-tight">Edit</span>
                </button>
              </div>

              <div className="space-y-5">
                <div className="space-y-2">
                  <label className="text-[10px] font-black text-azure-mid uppercase tracking-widest">Simulation Difficulty</label>
                  <div className="w-full bg-mint-bg border border-azure-pale rounded-xl px-3 py-2 text-xs font-bold text-azure-dark uppercase">
                    {config.difficulty} - {config.difficulty === 'easy' ? 'LOW TURBULENCE' : config.difficulty === 'hard' ? 'EXTREME CONDITIONS' : 'STANDARD OPS'}
                  </div>
                </div>

                <div className="space-y-4">
                  <h3 className="text-[10px] font-black text-azure-dark/40 uppercase tracking-widest border-b border-azure-pale pb-1">Known Parameters</h3>
                  <div className="space-y-3">
                    <ConfigRow label="Survivors" icon={<Users size={14}/>} value={config.survivors} />
                    <ConfigRow label="Drone Count" icon={<Drone size={14}/>} value={config.droneCount} />
                    <ConfigRow label="Obstacles" icon={<ShieldAlert size={14}/>} value={`${config.obstacleDensity}%`} />
                    <ConfigRow label="Disaster" icon={<Waves size={14}/>} value={config.disasterType.toUpperCase()} />
                  </div>
                </div>

                {/* Environmental Unknowns Section */}
                <div className="space-y-4 pt-2">
                  <h3 className="text-[10px] font-black text-azure-dark/40 uppercase tracking-widest border-b border-azure-pale pb-1">Environmental Unknowns</h3>
                  <div className="space-y-3">
                    {config.disasterType === 'typhoon' && (
                      <>
                        <ConfigRow label="Wind Speed" icon={<Activity size={14}/>} value={`${config.windSpeed} km/h`} />
                        <ConfigRow label="Direction" icon={<Activity size={14}/>} value={config.windDirection} />
                        <ConfigRow label="Rainfall" icon={<Droplets size={14}/>} value={`${config.rainfall} mm/h`} />
                      </>
                    )}
                    {config.disasterType === 'earthquake' && (
                      <>
                        <ConfigRow label="Aftershock" icon={<Activity size={14}/>} value={`${config.aftershockProb}%`} />
                        <ConfigRow label="Collapse Risk" icon={<ShieldAlert size={14}/>} value={`${config.collapseRisk}%`} />
                      </>
                    )}
                    {config.disasterType === 'tsunami' && (
                      <>
                        <ConfigRow label="Flow Velocity" icon={<Waves size={14}/>} value={`${config.waterFlow} m/s`} />
                        <ConfigRow label="Water Level" icon={<Droplets size={14}/>} value={`${config.waterLevel} m`} />
                      </>
                    )}
                    {config.disasterType === 'fire' && (
                      <>
                        <ConfigRow label="Spread Rate" icon={<Activity size={14}/>} value={`${config.fireSpread} m/min`} />
                        <ConfigRow label="Smoke Density" icon={<Activity size={14}/>} value={`${config.smokeDensity}%`} />
                      </>
                    )}
                    {config.disasterType === 'flash_flood' && (
                      <>
                        <ConfigRow label="Rising Speed" icon={<Droplets size={14}/>} value={`${config.risingSpeed} m/h`} />
                        <ConfigRow label="Water Level" icon={<Droplets size={14}/>} value={`${config.waterLevel} m`} />
                      </>
                    )}
                    {config.disasterType === 'default' && (
                      <div className="text-[10px] font-bold text-azure-mid italic">No active unknowns</div>
                    )}
                  </div>
                </div>

                <button 
                  onClick={() => {
                    resetMission(config);
                    void generateMapPreview(config);
                  }}
                  disabled={isGenerating}
                  className={`w-full mt-4 flex items-center justify-center gap-2 bg-mint-bg hover:bg-azure-pale/30 text-azure-dark border border-azure-pale py-3 rounded-xl font-black text-xs transition-all active:scale-95 ${isGenerating ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  <MapIcon size={14} />
                  {isGenerating ? 'GENERATING...' : 'GENERATE RANDOM MAP'}
                </button>

                <button 
                  onClick={() => resetMission(config)}
                  className="w-full mt-2 flex items-center justify-center gap-2 bg-white hover:bg-red-50 text-red-600 border border-red-200 py-3 rounded-xl font-black text-xs transition-all active:scale-95"
                >
                  <Activity size={14} />
                  RESET SIMULATION
                </button>

                <button 
                  onClick={downloadLogsAsText}
                  className="w-full mt-2 flex items-center justify-center gap-2 bg-azure-dark hover:bg-azure-dark/90 text-white py-3 rounded-xl font-black text-xs transition-all active:scale-95"
                >
                  <Terminal size={14} />
                  DOWNLOAD MISSION LOG
                </button>
              </div>
            </div>
          </aside>

          {/* Main Area: Dual Maps */}
          <main className="flex-1 flex flex-col gap-4 overflow-hidden min-h-0">
            <div className="flex-1 min-h-0">
              <div className="h-full grid grid-cols-2 gap-2">
                {/* Question Plane (God View) */}
                <div className="bg-white/90 backdrop-blur-sm p-2 rounded-xl shadow-sm border border-[#6aa7ad]/20 flex flex-col items-center overflow-hidden">
                  <div className="flex items-center justify-between mb-2 w-full shrink-0">
                    <div className="flex items-center gap-2">
                      <h2 className="font-black text-slate-800 uppercase text-[10px] tracking-widest">Question Plane <span className="text-[#6aa7ad] font-bold ml-1 opacity-50">| GOD VIEW</span></h2>
                    </div>
                    <div className="text-[8px] font-black text-[#6aa7ad] bg-[#e1fef0] px-1.5 py-0.5 rounded border border-[#6aa7ad]/20">ABSOLUTE TRUTH</div>
                  </div>
                  <div className="flex-1 w-full bg-white/50 rounded-lg border border-[#6aa7ad]/10 p-0.5 flex items-center justify-center overflow-hidden min-h-0">
                    <div 
                      className="aspect-square h-full w-auto max-w-full grid gap-[1px]"
                      style={{ gridTemplateColumns: 'repeat(20, 1fr)', gridTemplateRows: 'repeat(20, 1fr)' }}
                    >
                      {grid.map((row: GridCell[], y: number) => row.map((cell: GridCell, x: number) => (
                        <GridCellComponent 
                          key={`q-${x}-${y}`} 
                          cell={cell} 
                          mode="god" 
                          isDroneHere={drones.some(d => d.x === x && d.y === y)}
                          disasterType={config.disasterType}
                        />
                      )))}
                    </div>
                  </div>
                </div>

                {/* Answer Plane (Drone View) */}
                <div className="bg-white/90 backdrop-blur-sm p-2 rounded-xl shadow-sm border border-[#6aa7ad]/20 flex flex-col items-center overflow-hidden">
                  <div className="flex items-center justify-between mb-2 w-full shrink-0">
                    <div className="flex items-center gap-2">
                      <h2 className="font-black text-slate-800 uppercase text-[10px] tracking-widest">Answer Plane <span className="text-[#6aa7ad] font-bold ml-1 opacity-50">| DRONE VIEW</span></h2>
                    </div>
                    <div className="text-[8px] font-black text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-100">DYNAMIC UPDATE</div>
                  </div>
                  <div className="flex-1 w-full bg-white/50 rounded-lg border border-[#6aa7ad]/10 p-0.5 flex items-center justify-center overflow-hidden min-h-0">
                    <div 
                      className="aspect-square h-full w-auto max-w-full grid gap-[1px]"
                      style={{ gridTemplateColumns: 'repeat(20, 1fr)', gridTemplateRows: 'repeat(20, 1fr)' }}
                    >
                      {grid.map((row: GridCell[], y: number) => row.map((cell: GridCell, x: number) => (
                        <GridCellComponent 
                          key={`a-${x}-${y}`} 
                          cell={cell} 
                          mode="drone" 
                          isDroneHere={drones.some(d => d.x === x && d.y === y)}
                          disasterType={config.disasterType}
                        />
                      )))}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="shrink-0 flex flex-col gap-4">
            {/* Legend Section */}
            <div className="bg-white/90 backdrop-blur-sm p-3 rounded-xl shadow-sm border border-[#6aa7ad]/20 flex flex-wrap items-center justify-center gap-x-6 gap-y-3 max-w-full">
              <div className="flex items-center gap-2 text-[10px] font-black text-slate-700 uppercase whitespace-nowrap">
                <div className="w-3 h-3 bg-[#ff8a8a] rounded-sm" /> Single-Story
              </div>
              <div className="flex items-center gap-2 text-[10px] font-black text-azure-dark uppercase whitespace-nowrap">
                <div className="w-3 h-3 bg-[#b30000] rounded-sm" /> Multi-Story
              </div>
              <div className="flex items-center gap-2 text-[10px] font-black text-azure-dark uppercase whitespace-nowrap">
                <div className="w-3 h-3 bg-black rounded-sm" /> Obstacle
              </div>
              <div className="flex items-center gap-2 text-[10px] font-black text-azure-dark uppercase whitespace-nowrap">
                <div className="w-3 h-3 bg-[#87bcad] rounded-sm" /> Terrain
              </div>
              <div className="flex items-center gap-2 text-[10px] font-black text-azure-dark uppercase whitespace-nowrap">
                <div className="w-3 h-3 bg-cyan-900 rounded-sm" /> Base Station
              </div>
              <div className="flex items-center gap-2 text-[10px] font-black text-azure-dark uppercase whitespace-nowrap">
                <div className="w-2 h-2 bg-yellow-400 rounded-full shadow-[0_0_5px_#f2cf4e]" /> Survivor
              </div>
              <div className="flex items-center gap-2 text-[10px] font-black text-azure-dark uppercase whitespace-nowrap">
                <div className="w-2 h-2 bg-blue-400 rounded-full shadow-[0_0_5px_#60a5fa]" /> Drone
              </div>
              <div className="flex flex-col gap-1 min-w-[80px]">
                <span className="text-[8px] font-black text-azure-mid uppercase tracking-tighter">Elevation</span>
                <div className="flex items-center gap-2 text-[9px] font-bold text-azure-mid italic">
                  <span>Lo</span>
                  <div className="w-10 h-1 bg-gradient-to-r from-[#53a560] to-[#87bcad] rounded-full" />
                  <span>Hi</span>
                </div>
              </div>
            </div>

            </div>
          </main>

          {/* Right Sidebar: Swarm Status */}
          <aside className={`transition-all duration-300 ${isSwarmPanelOpen ? 'w-64' : 'w-14'} flex flex-col gap-2 shrink-0 overflow-y-auto custom-scrollbar pr-1`}>
            <div className="bg-[#1A202C] p-4 rounded-xl shadow-xl border border-white/10 flex-1 flex flex-col min-h-0 overflow-hidden">
              <div className={`flex items-center justify-between mb-4 ${!isSwarmPanelOpen && 'flex-col gap-4'}`}>
                <div className={`flex items-center gap-2 ${!isSwarmPanelOpen && 'rotate-90 origin-center my-8'}`}>
                  <Activity className="text-yellow-400" size={18} />
                  <h2 className="font-bold text-white uppercase text-sm tracking-tight whitespace-nowrap">Swarm Status</h2>
                </div>
                <div className="flex flex-col items-center gap-3">
                   <button 
                    onClick={() => setIsSwarmPanelOpen(!isSwarmPanelOpen)}
                    className="p-1.5 hover:bg-white/5 rounded-md transition-colors text-white/30 hover:text-white"
                    title={isSwarmPanelOpen ? "Collapse Sidebar" : "Expand Sidebar"}
                  >
                    {isSwarmPanelOpen ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
                  </button>
                  {!isSwarmPanelOpen && (
                    <div className="flex flex-col items-center gap-1">
                      <span className="text-[10px] font-black text-white">{drones.length}</span>
                      <span className="text-[7px] font-black text-white/40 uppercase vertical-text tracking-widest">Active</span>
                    </div>
                  )}
                </div>
                {isSwarmPanelOpen && (
                  <span className="text-[9px] font-black text-white/40 uppercase">{drones.length} ACTIVE</span>
                )}
              </div>

              {isSwarmPanelOpen && (
                <div className="flex-1 overflow-y-auto custom-scrollbar space-y-3 pr-1">
                  {drones.map(drone => (
                    <DroneCard 
                      key={drone.id} 
                      drone={drone} 
                      isExpanded={expandedDroneId === drone.id}
                      onToggle={() => setExpandedDroneId(expandedDroneId === drone.id ? null : drone.id)}
                      logs={logs}
                    />
                  ))}
                </div>
              )}
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}

// --- Sub-components ---

function DroneCard({ 
  drone, 
  isExpanded, 
  onToggle, 
  logs 
}: { 
  drone: DroneStatus, 
  isExpanded: boolean, 
  onToggle: () => void,
  logs: LogEntry[],
  key?: string
}) {
  const droneLogs = logs.filter(l => l.agent === drone.id);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isExpanded && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [isExpanded, droneLogs.length]);

  return (
    <div 
      onClick={onToggle}
      className={`cursor-pointer transition-all duration-300 rounded-xl border ${
        isExpanded ? 'bg-white/10 border-cyan-500/50 shadow-[0_0_15px_rgba(6,182,212,0.2)]' : 'bg-white/5 border-white/5 hover:bg-white/10'
      } p-3 overflow-hidden`}
    >
      {/* Collapsed Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-black text-white">{drone.id}</span>
          {!isExpanded && (
             <div className="flex gap-0.5">
               {[1, 2, 3, 4].map(i => (
                 <div key={i} className={`w-1 h-1 rounded-full ${drone.status === 'patrolling' && i === 1 ? 'bg-emerald-400 shadow-[0_0_3px_#34d399]' : 'bg-white/20'}`} />
               ))}
             </div>
          )}
        </div>
        <span className={`text-[9px] font-bold px-2 py-0.5 rounded uppercase ${
          drone.status === 'patrolling' ? 'bg-emerald-500/20 text-emerald-400' :
          drone.status === 'returning' ? 'bg-alert-orange/20 text-alert-orange' :
          'bg-white/10 text-white/50'
        }`}>
          {drone.status}
        </span>
      </div>

      {!isExpanded && (
        <div className="flex items-center gap-3">
          <div className="flex-1">
            <div className="h-1 bg-white/10 rounded-full overflow-hidden">
              <motion.div 
                className={`h-full ${drone.battery < 20 ? 'bg-alert-red' : drone.battery < 50 ? 'bg-alert-yellow' : 'bg-emerald-500'}`}
                animate={{ width: `${drone.battery}%` }}
              />
            </div>
          </div>
          <span className="text-[9px] font-black text-white/40">{Math.floor(drone.battery)}%</span>
        </div>
      )}

      {/* Expanded Content */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="mt-4 space-y-4"
          >
            {/* Switch Style Icon & Status */}
            <div className="flex items-center gap-4 bg-black/20 p-3 rounded-lg">
              <div className="relative">
                <div className="w-12 h-12 bg-cyan-500/20 rounded-xl flex items-center justify-center border border-cyan-500/30">
                  <Drone className="text-cyan-400" size={24} />
                </div>
                {/* Player LEDs */}
                <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 flex gap-1">
                  {[1, 2, 3, 4].map(i => (
                    <div 
                      key={i} 
                      className={`w-1.5 h-1.5 rounded-full transition-all duration-300 ${
                        drone.status === 'patrolling' && i === 1 
                          ? 'bg-emerald-400 shadow-[0_0_5px_#34d399]' 
                          : 'bg-white/10'
                      }`} 
                    />
                  ))}
                </div>
              </div>
              <div className="flex-1">
                <div className="text-[10px] font-black text-white/40 uppercase mb-1">Power Level</div>
                <div className="flex items-center gap-2">
                  {/* Segmented Battery Icon */}
                  <div className="flex items-center">
                    <div className="w-8 h-4 border border-white/30 rounded-sm p-0.5 flex gap-0.5 relative">
                      {[1, 2, 3, 4].map(i => (
                        <div 
                          key={i} 
                          className={`flex-1 rounded-sm ${
                            drone.battery >= i * 25 
                              ? (drone.battery < 25 ? 'bg-red-500' : 'bg-emerald-400') 
                              : 'bg-white/5'
                          }`} 
                        />
                      ))}
                      <div className="absolute -right-1 top-1/2 -translate-y-1/2 w-1 h-2 bg-white/30 rounded-r-sm" />
                    </div>
                  </div>
                  <span className="text-xs font-black text-white">{Math.floor(drone.battery)}%</span>
                </div>
              </div>
            </div>

            {/* Telemetry Grid */}
            <div className="grid grid-cols-2 gap-2">
              <div className="bg-white/5 p-2 rounded-lg border border-white/5">
                <div className="text-[8px] font-black text-white/30 uppercase mb-1">Coordinates</div>
                <div className="text-xs font-black text-cyan-400">{drone.x}, {drone.y}</div>
              </div>
              <div className="bg-white/5 p-2 rounded-lg border border-white/5">
                <div className="text-[8px] font-black text-white/30 uppercase mb-1">Steps Taken</div>
                <div className="text-xs font-black text-emerald-400">{drone.stepsTaken}</div>
              </div>
            </div>

            {/* Mini Log */}
            <div className="space-y-1.5">
              <div className="flex items-center gap-2 px-1">
                <Terminal size={10} className="text-white/30" />
                <span className="text-[8px] font-black text-white/30 uppercase tracking-widest">Drone Brain</span>
              </div>
              <div className="h-24 bg-black/40 rounded-lg p-2 font-mono text-[9px] overflow-y-auto custom-scrollbar border border-white/5">
                {droneLogs.length === 0 ? (
                  <div className="text-white/20 italic">No telemetry data...</div>
                ) : (
                  droneLogs.map((log, idx) => (
                    <div key={idx} className="flex gap-2 mb-1">
                      <span className="text-white/20">[{log.timestamp}]</span>
                      <span className={
                        log.type === 'success' ? 'text-emerald-400' : 
                        log.type === 'warning' ? 'text-yellow-400' : 
                        log.type === 'error' ? 'text-red-400' : 'text-cyan-400'
                      }>
                        {log.message}
                      </span>
                    </div>
                  ))
                )}
                <div ref={logEndRef} />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function ConfigRow({ label, icon, value }: { label: string, icon: React.ReactNode, value: any }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <div className="flex items-center gap-2 text-azure-dark font-bold uppercase tracking-tight">
        {icon} {label}
      </div>
      <div className="font-black text-neutral-dark">{value}</div>
    </div>
  );
}

function ConfigPage({ config, onSave, onCancel }: { config: any, onSave: (c: any) => void | Promise<void>, onCancel: () => void }) {
  const [localConfig, setLocalConfig] = useState(config);

  return (
    <div className="flex-1 flex items-center justify-center bg-white/10 p-8 overflow-y-auto">
      <motion.div 
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-white w-full max-w-2xl rounded-3xl shadow-2xl border border-azure-pale/50 overflow-hidden"
      >
        <div className="bg-azure-dark p-8 text-white">
          <div className="flex items-center gap-3 mb-2">
            <Settings size={24} />
            <h2 className="text-2xl font-black tracking-tight uppercase">Mission Configuration</h2>
          </div>
          <p className="text-white/60 text-sm font-medium">Adjust parameters for the autonomous rescue protocol.</p>
        </div>

        <div className="p-8 space-y-8">
          <div className="grid grid-cols-2 gap-8">
            <div className="space-y-4">
              <label className="text-xs font-black text-azure-mid uppercase tracking-widest">Disaster Type</label>
              <div className="grid grid-cols-3 gap-2">
                {['typhoon', 'earthquake', 'tsunami', 'fire', 'flash_flood', 'default'].map((type) => (
                  <button
                    key={type}
                    onClick={() => setLocalConfig({ ...localConfig, disasterType: type })}
                    className={`px-4 py-3 rounded-xl text-[10px] font-black uppercase transition-all border ${
                      localConfig.disasterType === type 
                        ? 'bg-azure-dark text-white border-azure-dark shadow-md' 
                        : 'bg-mint-bg text-azure-dark border-azure-pale hover:border-azure-mid'
                    }`}
                  >
                    {type.replace('_', ' ')}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-4">
              <label className="text-xs font-black text-azure-mid uppercase tracking-widest">Simulation Difficulty</label>
              <select 
                value={localConfig.difficulty}
                onChange={(e) => setLocalConfig({ ...localConfig, difficulty: e.target.value })}
                className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-3 text-sm font-bold outline-none focus:ring-2 focus:ring-azure-mid"
              >
                <option value="easy">EASY - LOW TURBULENCE</option>
                <option value="normal">NORMAL - STANDARD OPS</option>
                <option value="hard">HARD - EXTREME CONDITIONS</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-6">
            <div className="space-y-2">
              <label className="text-[10px] font-black text-azure-mid uppercase tracking-widest">Survivors Amount</label>
              <input 
                type="number" 
                value={localConfig.survivors}
                onChange={(e) => setLocalConfig({ ...localConfig, survivors: parseInt(e.target.value) })}
                className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-3 text-sm font-bold outline-none"
              />
            </div>
            <div className="space-y-2">
              <label className="text-[10px] font-black text-azure-mid uppercase tracking-widest">Drone Count</label>
              <input 
                type="number" 
                value={localConfig.droneCount}
                onChange={(e) => setLocalConfig({ ...localConfig, droneCount: parseInt(e.target.value) })}
                className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-3 text-sm font-bold outline-none"
              />
            </div>
            <div className="space-y-2">
              <label className="text-[10px] font-black text-azure-mid uppercase tracking-widest">Obstacles (%)</label>
              <input 
                type="number" 
                value={localConfig.obstacleDensity}
                onChange={(e) => setLocalConfig({ ...localConfig, obstacleDensity: parseInt(e.target.value) })}
                className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-3 text-sm font-bold outline-none"
              />
            </div>
          </div>

          {/* Environmental Unknowns Section */}
          <div className="space-y-6 pt-6 border-t border-azure-pale">
            <div className="flex items-center gap-2">
              <Activity size={18} className="text-azure-dark" />
              <h3 className="text-sm font-black text-azure-dark uppercase tracking-widest">Environmental Unknowns</h3>
            </div>
            
            <div className="grid grid-cols-3 gap-6">
              {localConfig.disasterType === 'typhoon' && (
                <>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Wind Speed (km/h)</label>
                    <input type="number" value={localConfig.windSpeed} onChange={(e) => setLocalConfig({...localConfig, windSpeed: parseInt(e.target.value)})} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Wind Direction</label>
                    <select value={localConfig.windDirection} onChange={(e) => setLocalConfig({...localConfig, windDirection: e.target.value})} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none">
                      {['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'].map(d => <option key={d} value={d}>{d}</option>)}
                    </select>
                  </div>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Flying Debris Prob (%)</label>
                    <input type="number" value={localConfig.debrisProb} onChange={(e) => setLocalConfig({...localConfig, debrisProb: parseInt(e.target.value)})} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Rainfall Rate (mm/h)</label>
                    <input type="number" value={localConfig.rainfall} onChange={(e) => setLocalConfig({...localConfig, rainfall: parseInt(e.target.value)})} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none" />
                  </div>
                </>
              )}

              {localConfig.disasterType === 'earthquake' && (
                <>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Aftershock Prob (%)</label>
                    <input type="number" value={localConfig.aftershockProb} onChange={(e) => setLocalConfig({...localConfig, aftershockProb: parseInt(e.target.value)})} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Structural Collapse Risk (%)</label>
                    <input type="number" value={localConfig.collapseRisk} onChange={(e) => setLocalConfig({...localConfig, collapseRisk: parseInt(e.target.value)})} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none" />
                  </div>
                </>
              )}

              {localConfig.disasterType === 'tsunami' && (
                <>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Water Flow Velocity (m/s)</label>
                    <input type="number" value={localConfig.waterFlow} onChange={(e) => setLocalConfig({...localConfig, waterFlow: parseInt(e.target.value)})} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Secondary Wave (min)</label>
                    <input type="number" value={localConfig.secondaryWave} onChange={(e) => setLocalConfig({...localConfig, secondaryWave: parseInt(e.target.value)})} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Water Level (m)</label>
                    <input type="number" value={localConfig.waterLevel} onChange={(e) => setLocalConfig({...localConfig, waterLevel: parseInt(e.target.value)})} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none" />
                  </div>
                </>
              )}

              {localConfig.disasterType === 'fire' && (
                <>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Fire Spread Rate (m/min)</label>
                    <input type="number" value={localConfig.fireSpread} onChange={(e) => setLocalConfig({...localConfig, fireSpread: parseInt(e.target.value)})} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Smoke Density (%)</label>
                    <input type="number" value={localConfig.smokeDensity} onChange={(e) => setLocalConfig({...localConfig, smokeDensity: parseInt(e.target.value)})} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Extreme Heat Zones (%)</label>
                    <input type="number" value={localConfig.heatZones} onChange={(e) => setLocalConfig({...localConfig, heatZones: parseInt(e.target.value)})} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none" />
                  </div>
                </>
              )}

              {localConfig.disasterType === 'flash_flood' && (
                <>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Initial Water Level (m)</label>
                    <input type="number" value={localConfig.waterLevel} onChange={(e) => setLocalConfig({...localConfig, waterLevel: parseInt(e.target.value)})} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Rising Speed (m/h)</label>
                    <input type="number" step="0.1" value={localConfig.risingSpeed} onChange={(e) => setLocalConfig({...localConfig, risingSpeed: parseFloat(e.target.value)})} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none" />
                  </div>
                </>
              )}

              {localConfig.disasterType === 'default' && (
                <div className="col-span-3 text-center py-4 text-azure-mid italic text-xs">
                  No specific environmental unknowns for default scenario.
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center justify-end gap-4 pt-4 border-t border-azure-pale">
            <button 
              onClick={onCancel}
              className="px-6 py-3 rounded-xl font-bold text-azure-mid hover:text-azure-dark transition-colors"
            >
              CANCEL
            </button>
            <button 
              onClick={() => onSave(localConfig)}
              className="bg-emerald-500 text-white px-10 py-3 rounded-xl font-black shadow-lg hover:bg-emerald-600 transition-all transform active:scale-95"
            >
              DEPLOY MISSION
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

function GridCellComponent({ cell, mode, isDroneHere, disasterType }: { cell: GridCell, mode: 'god' | 'drone', isDroneHere?: boolean, disasterType: DisasterType, key?: string }) {
  const isRevealed = mode === 'god' || cell.revealed;
  const effectiveType: EntityType =
    mode === 'drone' && cell.type === 'obstacle' && !cell.obstacleDiscovered ? 'empty' : cell.type;
  
  const getBgColor = () => {
    if (!isRevealed) return '#5a8e94'; // Blended dark teal for unrevealed
    if (effectiveType === 'base') return '#164e63'; // Dark Cyan Base
    if (effectiveType === 'obstacle') return '#000000'; // High contrast black
    if (effectiveType === 'building') {
      return cell.height > 1 ? '#b30000' : '#ff8a8a'; // Restore building colors
    }
    
    // Terrain: Single base color with elevation-based opacity handled in style
    return '#87bcad';
  };

  const getOpacity = () => {
    if (!isRevealed || effectiveType === 'base' || effectiveType === 'obstacle' || effectiveType === 'building') return 1;
    // Map height (1-9) to opacity (0.2-0.8)
    return 0.2 + (cell.height / 9) * 0.6;
  };

  return (
    <div className="relative w-full h-full aspect-square overflow-hidden">
      {/* Terrain Layer */}
      <div 
        className="absolute inset-0 transition-all duration-500"
        style={{ 
          backgroundColor: getBgColor(),
          opacity: getOpacity()
        }}
      />
      
      {/* Survivor Indicator (Glowing Yellow Dot) */}
      {isRevealed && ((mode === 'god' && cell.hasSurvivor && !cell.isRescued) || (mode === 'drone' && cell.isRescued)) && (
        <div className="absolute inset-0 flex items-center justify-center z-20">
          <motion.div 
            animate={{ opacity: [0.6, 1, 0.6], scale: [0.8, 1.1, 0.8] }}
            transition={{ repeat: Infinity, duration: 1.5 }}
            className="w-2 h-2 bg-yellow-400 rounded-full shadow-[0_0_8px_#f2cf4e]"
          />
        </div>
      )}

      {/* Drone Indicator (Bright Blue Dot) */}
      {isDroneHere && (
        <div className="absolute inset-0 flex items-center justify-center z-30">
          <motion.div 
            animate={{ scale: [1, 1.3, 1] }}
            transition={{ repeat: Infinity, duration: 0.6 }}
            className="w-2 h-2 bg-blue-400 rounded-full shadow-[0_0_8px_#60a5fa]"
          />
        </div>
      )}

      {/* Fog of War Layer (Drone Mode Only) */}
      {mode === 'drone' && !cell.revealed && (
        <div className={`absolute inset-0 z-10 bg-[#4a7a7e]/80 ${cell.isIlluminated ? 'opacity-0' : 'opacity-100'}`} />
      )}
      
      {/* Base Station Highlight */}
      {cell.type === 'base' && (
        <div className="absolute inset-0 border border-white/30 animate-pulse z-40 pointer-events-none" />
      )}
    </div>
  );
}
