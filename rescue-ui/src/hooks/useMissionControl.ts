import { useState, useRef, useCallback } from 'react';
import { MissionConfig, DroneStatus, LogEntry, GridCell, EntityType } from '../types';
import { GRID_SIZE, BASE_X, BASE_Y } from '../constants';
import { resetMissionApi, generateMapApi, startMissionApi, abortMissionApi } from '../lib/api';
import { buildGridFromMapData } from '../utils/map-utils';
import { useToast } from '../components/UI/Toast';

export const useMissionControl = () => {
  const { showToast } = useToast();
  const [config, setConfig] = useState<MissionConfig>({
    scenario: 'mixed urban',
    survivors: 10,
    droneCount: 5,
    obstacleDensity: 'med',
    disasterType: 'default',
    difficulty: 'normal',
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

  const [isSimulationRunning, setIsSimulationRunning] = useState(false);
  const [isAborting, setIsAborting] = useState(false);
  const [isMapGenerated, setIsMapGenerated] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [survivorsFound, setSurvivorsFound] = useState(0);
  const [survivorsDetected, setSurvivorsDetected] = useState(0);
  const [revealedCells, setRevealedCells] = useState(0);
  const [drones, setDrones] = useState<DroneStatus[]>([]);
  const [grid, setGrid] = useState<GridCell[][]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [mapData, setMapData] = useState<any | null>(null);

  const discoveredRef = useRef<Set<string>>(new Set());
  const seenLogsRef = useRef<Set<string>>(new Set());

  const addLog = useCallback((agent: string, message: string, type: LogEntry['type'] = 'info', details?: LogEntry['details']) => {
    const newLog: LogEntry = {
      id: Math.random().toString(36).substr(2, 9),
      timestamp: new Date().toLocaleTimeString(),
      agent,
      message,
      type,
      details,
    };
    setLogs(prev => [...prev, newLog]);
  }, []);

  const resetMission = useCallback(async (newConfig = config) => {
    try {
      await resetMissionApi();
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
    seenLogsRef.current = new Set();
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
    setLogs(() => []);
    addLog('SYSTEM', `Ready. Configure mission and generate a map preview.`, 'info');
  }, [config, addLog]);

  const generateMapPreview = useCallback(async (cfg = config, customMessage?: string) => {
    setIsGenerating(true);
    addLog('SYSTEM', customMessage || 'Generating disaster zone map...', 'info');
    try {
      const data = await generateMapApi(cfg);
      setMapData(data);
      setGrid(buildGridFromMapData(data));
      discoveredRef.current = new Set();
      setRevealedCells(0);
      setSurvivorsFound(0);
      setSurvivorsDetected(0);
      setIsMapGenerated(true);
      addLog('SYSTEM', 'Generate map done. Ready to deploy.', 'success');
      showToast('Disaster zone map generated successfully.', 'success');
      return data;
    } catch (e: any) {
      const errorMsg = e?.message ?? String(e);
      addLog('SYSTEM', `Generate map failed: ${errorMsg}`, 'error');
      showToast(`Map generation failed: ${errorMsg}`, 'error');
      return null;
    } finally {
      setIsGenerating(false);
    }
  }, [config, addLog, showToast]);

  const generateRandomMap = useCallback(async () => {
    const scenarios = ['downtown', 'suburban', 'industrial', 'coastal', 'mixed urban', 'mountain outpost'];
    const randomScenario = scenarios[Math.floor(Math.random() * scenarios.length)];
    const randomSurvivors = Math.floor(Math.random() * 16) + 5; // 5-20
    const randomDroneCount = Math.floor(Math.random() * 3) + 3; // 3-5
    const densities: ('low' | 'med' | 'high')[] = ['low', 'med', 'high'];
    const randomObstacleDensity = densities[Math.floor(Math.random() * 3)];
    
    const newConfig: MissionConfig = {
      ...config,
      scenario: randomScenario,
      survivors: randomSurvivors,
      droneCount: randomDroneCount,
      obstacleDensity: randomObstacleDensity,
      disasterType: 'default',
    };
    
    setConfig(newConfig);
    await resetMission(newConfig);
    return await generateMapPreview(newConfig, `Generating Random Disaster Zone Map...`);
  }, [config, resetMission, generateMapPreview]);

  const toggleSimulation = useCallback(async () => {
    if (!isSimulationRunning) {
      if (!isMapGenerated || !mapData) {
        showToast('Please generate a map first before deploying the swarm!', 'warning');
        return;
      }
      try {
        await startMissionApi(config, mapData);
        addLog('COMMAND', 'Deploying swarm from Central Base.', 'info');
        setIsSimulationRunning(true);
        setIsAborting(false);
        showToast('Swarm deployed successfully.', 'success');
      } catch (e: any) {
        const errorMsg = e?.message ?? String(e);
        addLog('SYSTEM', `Start mission failed: ${errorMsg}`, 'error');
        showToast(`Deployment failed: ${errorMsg}`, 'error');
      }
    } else {
      setIsAborting(true);
      try {
        await abortMissionApi();
        addLog('COMMAND', 'ABORT SIGNAL SENT: Recalling all drones.', 'warning');
      } catch (e) {
        addLog('SYSTEM', 'Abort failed.', 'error');
        setIsAborting(false);
      }
    }
  }, [isSimulationRunning, isMapGenerated, mapData, config, addLog]);

  const downloadLogsAsText = useCallback(() => {
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
  }, [logs]);

  return {
    config,
    setConfig,
    isSimulationRunning,
    setIsSimulationRunning,
    isAborting,
    setIsAborting,
    isMapGenerated,
    isGenerating,
    survivorsFound,
    setSurvivorsFound,
    survivorsDetected,
    setSurvivorsDetected,
    revealedCells,
    setRevealedCells,
    drones,
    setDrones,
    grid,
    setGrid,
    logs,
    setLogs,
    mapData,
    addLog,
    resetMission,
    generateMapPreview,
    generateRandomMap,
    toggleSimulation,
    downloadLogsAsText,
    discoveredRef,
    seenLogsRef
  };
};
