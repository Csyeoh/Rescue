"use client";

import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { useMissionControl } from '../hooks/useMissionControl';
import { useWebSocket } from '../hooks/useWebSocket';
import { Header } from '../components/Layout/Header';
import { SidebarConfig } from '../components/Layout/SidebarConfig';
import { SwarmStatusPanel } from '../components/Layout/SwarmStatusPanel';
import { MissionLogPanel } from '../components/MissionLog/MissionLogPanel';
import { MapContainer } from '../components/Map/MapContainer';
import { ConfigPage } from '../components/Config/ConfigPage';

export default function App() {
  // --- UI State ---
  const [view, setView] = useState<'dashboard' | 'config'>('dashboard');
  const [isLogOpen, setIsLogOpen] = useState(true);
  const [logHeight, setLogHeight] = useState(200);
  const [isSwarmPanelOpen, setIsSwarmPanelOpen] = useState(true);
  const [expandedDroneId, setExpandedDroneId] = useState<string | null>(null);
  
  const logEndRef = useRef<HTMLDivElement>(null);

  // --- Mission Logic & State ---
  const {
    config,
    setConfig,
    isSimulationRunning,
    setIsSimulationRunning,
    isAborting,
    isMapGenerated,
    isGenerating,
    survivorsFound,
    survivorsDetected,
    setSurvivorsDetected,
    setSurvivorsFound,
    revealedCells,
    setRevealedCells,
    drones,
    setDrones,
    grid,
    setGrid,
    logs,
    addLog,
    resetMission,
    generateMapPreview,
    generateRandomMap,
    toggleSimulation,
    downloadLogsAsText,
    mapData,
    discoveredRef,
    seenLogsRef
  } = useMissionControl();

  // --- Real-time Updates ---
  useWebSocket({
    isSimulationRunning,
    revealedCells,
    setIsSimulationRunning,
    setDrones,
    setGrid,
    setSurvivorsFound,
    setSurvivorsDetected,
    setRevealedCells,
    addLog,
    discoveredRef,
    seenLogsRef
  });

  // --- Effects ---
  useEffect(() => {
    resetMission();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (isLogOpen) {
      logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, isLogOpen]);

  return (
    <div className="h-screen w-screen bg-[#e1fef0] text-slate-900 overflow-hidden relative">
      <AnimatePresence mode="wait">
        {view === 'config' ? (
          <motion.div
            key="config"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.4, ease: "circOut" }}
            className="absolute inset-0 z-50 bg-[#e1fef0]"
          >
            <ConfigPage
              config={config}
              onSave={async (newConfig) => {
                setView('dashboard');
                addLog('SYSTEM', `New configuration applied: ${newConfig.scenario}, ${newConfig.survivors} survivors.`, 'info');
                setConfig(newConfig);
                await resetMission(newConfig);
                await generateMapPreview(newConfig);
              }}
              onCancel={() => setView('dashboard')}
            />
          </motion.div>
        ) : (
          <motion.div
            key="dashboard"
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 1.02 }}
            transition={{ duration: 0.4, ease: "circOut" }}
            className="h-full flex flex-col p-2 gap-2"
          >
            <Header
              revealedCells={revealedCells}
              survivorsDetected={survivorsDetected}
              totalSurvivors={config.survivors}
              disasterType={config.disasterType}
              isSimulationRunning={isSimulationRunning}
              isAborting={isAborting}
              isMapGenerated={isMapGenerated}
              onToggleSimulation={toggleSimulation}
            />

            <div className="flex-1 flex gap-2 min-h-0 overflow-hidden">
              <SidebarConfig
                config={config}
                isGenerating={isGenerating}
                onEditConfig={() => setView('config')}
                onGenerateMap={generateRandomMap}
                onResetSimulation={() => resetMission(config)}
                onDownloadLogs={downloadLogsAsText}
              />

              <div className="flex-1 flex flex-col gap-2 min-h-0 overflow-hidden">
                <MapContainer
                  grid={grid}
                  drones={drones}
                  disasterType={config.disasterType}
                />

                <MissionLogPanel
                  logs={logs}
                  isLogOpen={isLogOpen}
                  onToggleLog={() => setIsLogOpen(!isLogOpen)}
                  logEndRef={logEndRef}
                  height={logHeight}
                  setHeight={setLogHeight}
                />
              </div>

              <SwarmStatusPanel
                drones={drones}
                isSwarmPanelOpen={isSwarmPanelOpen}
                onToggleSwarmPanel={() => setIsSwarmPanelOpen(!isSwarmPanelOpen)}
                expandedDroneId={expandedDroneId}
                onToggleDrone={(id) => setExpandedDroneId(expandedDroneId === id ? null : id)}
                logs={logs}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

