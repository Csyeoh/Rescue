import { useState, useRef, useCallback, useEffect } from 'react';
import { MissionConfig, DroneStatus, LogEntry, EnvironmentState } from '../types';
import { BASE_X, BASE_Y } from '../constants';
import { resetMissionApi, generateMapApi, startMissionApi, abortMissionApi } from '../lib/api';
import { initializeEnvironmentState } from '../utils/map-utils';
import { useToast } from '../components/UI/Toast';

export const useMissionControl = () => {
  const { showToast } = useToast();
  const [config, setConfig] = useState<MissionConfig>({
    droneCount: 5,
  });

  const [isSimulationRunning, setIsSimulationRunning] = useState(false);
  const [isAborting, setIsAborting] = useState(false);
  const [isMapGenerated, setIsMapGenerated] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [survivorsFound, setSurvivorsFound] = useState(0);
  const [survivorsDetected, setSurvivorsDetected] = useState(0);
  const [revealedCells, setRevealedCells] = useState(0);
  const [coverage, setCoverage] = useState<{x: number, y: number}[]>([]);
  const [drones, setDrones] = useState<DroneStatus[]>([]);
  const [environmentState, setEnvironmentState] = useState<EnvironmentState>({
    buildings: [],
    obstacles: [],
    survivors: [],
    thermalScans: [],
    sectors: []
  });
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

    setEnvironmentState({ buildings: [], obstacles: [], survivors: [], thermalScans: [], sectors: [] });
    setSurvivorsFound(0);
    setSurvivorsDetected(0);
    discoveredRef.current = new Set();
    seenLogsRef.current = new Set();
    setRevealedCells(0);
    setCoverage([]);
    setIsSimulationRunning(false);
    setMapData(null);
    setIsMapGenerated(false);
    setIsGenerating(false);

    setDrones([]);
    setLogs(() => []);

  }, [addLog]);

  // Global cleanup: ensure all scans disappear after 4 seconds
  useEffect(() => {
    const cleanupInterval = setInterval(() => {
      const now = Date.now();
      setEnvironmentState(prev => {
        const freshScans = prev.thermalScans.filter(s => {
          const createdAt = s.createdAt || now;
          return now - createdAt < 4000;
        });
        if (freshScans.length === prev.thermalScans.length) return prev;
        return { ...prev, thermalScans: freshScans };
      });
    }, 500); 
    return () => clearInterval(cleanupInterval);
  }, []);

  const generateMapPreview = useCallback(async () => {
    setIsGenerating(true);
    try {
      const data = await generateMapApi();
      setMapData(data.map_data);
      const envState = initializeEnvironmentState(data.map_data);
      
      setEnvironmentState(envState);

      // Spaced-out drone initialization at base (9.5, 9.5)
      const droneCount = data.num_drones || 3;
      const initialDrones: DroneStatus[] = Array.from({ length: droneCount }).map((_, i) => {
        const angle = (i * 2 * Math.PI) / droneCount;
        const radius = 0.3;
        return {
          id: `drone_${i + 1}`,
          battery: 100,
          status: 'idle',
          x: BASE_X + 0.5 + Math.cos(angle) * radius,
          y: BASE_Y + 0.5 + Math.sin(angle) * radius,
          stepsTaken: 0
        };
      });
      setDrones(initialDrones);

      discoveredRef.current = new Set();
      setRevealedCells(0);
      setSurvivorsFound(0);
      setSurvivorsDetected(0);
      setIsMapGenerated(true);
      showToast('Disaster zone map generated successfully.', 'success');
      return data;
    } catch (e: any) {
      const errorMsg = e?.message ?? String(e);
      showToast(`Map generation failed: ${errorMsg}`, 'error');
      return null;
    } finally {
      setIsGenerating(false);
    }
  }, [config, showToast]);



  const toggleSimulation = useCallback(async () => {
    if (!isSimulationRunning) {
      if (!isMapGenerated || !mapData) {
        showToast('Please generate a map first before deploying the swarm!', 'warning');
        return;
      }
      try {
        // Open the WebSocket first so we're ready to receive telemetry
        addLog('COMMAND', 'Establishing telemetry link…', 'info');
        setIsSimulationRunning(true);
        setIsAborting(false);

        // Brief pause to let the WS handshake complete before kicking off the sim
        await new Promise((r) => setTimeout(r, 600));

        await startMissionApi();
        addLog('COMMAND', 'Swarm deployed.', 'info');
        showToast('Swarm deployed successfully.', 'success');
      } catch (e: any) {
        const errorMsg = e?.message ?? String(e);
        addLog('SYSTEM', `Start mission failed: ${errorMsg}`, 'error');
        showToast(`Deployment failed: ${errorMsg}`, 'error');
        setIsSimulationRunning(false);       // close WS on failure
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
    coverage,
    setCoverage,
    drones,
    setDrones,
    environmentState,
    setEnvironmentState,
    logs,
    setLogs,
    mapData,
    addLog,
    resetMission,
    generateMapPreview,
    toggleSimulation,
    downloadLogsAsText,
    discoveredRef,
    seenLogsRef
  };
};
