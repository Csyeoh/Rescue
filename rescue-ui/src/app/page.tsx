"use client";

import React, { useState, useEffect, useRef } from 'react';
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
  }, [resetMission]);

  useEffect(() => {
    if (isLogOpen) {
      logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, isLogOpen]);

  if (view === 'config') {
    return (
      <ConfigPage
        config={config}
        onSave={async (newConfig) => {
          setConfig(newConfig);
          await resetMission(newConfig);
          await generateMapPreview(newConfig);
          setView('dashboard');
        }}
        onCancel={() => setView('dashboard')}
      />
    );
  }

  return (
    <div className="h-screen flex flex-col bg-[#e1fef0] text-slate-900 p-2 gap-2 overflow-hidden">
      <Header
        revealedCells={revealedCells}
        survivorsDetected={survivorsDetected}
        totalSurvivors={config.survivors}
        disasterType={config.disasterType}
        isSimulationRunning={isSimulationRunning}
        isAborting={isAborting}
        onToggleSimulation={toggleSimulation}
      />

      <div className="flex-1 flex gap-2 overflow-hidden">
        <SidebarConfig
          config={config}
          isGenerating={isGenerating}
          onEditConfig={() => setView('config')}
          onGenerateMap={() => {
            void resetMission(config);
            void generateMapPreview(config);
          }}
          onResetSimulation={() => resetMission(config)}
          onDownloadLogs={downloadLogsAsText}
        />

        <div className="flex-1 flex flex-col gap-4 overflow-hidden min-h-0">
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
    </div>
  );
}
