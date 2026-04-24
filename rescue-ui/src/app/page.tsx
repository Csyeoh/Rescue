"use client";

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { useMissionControl } from '../hooks/useMissionControl';
import { useWebSocket } from '../hooks/useWebSocket';
import { Header } from '../components/Layout/Header';
import { LogPanel } from '../components/Layout/LogPanel';
import { SwarmStatusPanel } from '../components/Layout/SwarmStatusPanel';
import DeckGLContainer from '../components/Map/DeckGLContainer';
import { MissionReportModal } from '../components/Report/MissionReportModal'; // Import it
import SurvivorMic from '../components/UI/SurvivorMic';



export default function DeckApp() {

  const [showCoords, setShowCoords] = useState(false);
  const [isNightMode, setIsNightMode] = useState(false);
  const [showXRay, setShowXRay] = useState(false);
  

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
    tickCount,
    setTickCount,
    coverage,
    setCoverage,
    drones,
    setDrones,
    environmentState,
    setEnvironmentState,
    logs,
    setLogs,
    addLog,
    activeTriage,
    setActiveTriage,
    resetMission,
    generateMapPreview,
    toggleSimulation,
    downloadLogsAsText,
    mapData,
    discoveredRef,
    seenLogsRef,
    missionReport,
    setMissionReport
  } = useMissionControl();

  const clearLogs = () => setLogs([]);

  useWebSocket({
    shouldConnect: isSimulationRunning,
    isSimulationRunning,
    revealedCells,
    setIsSimulationRunning,
    setDrones,
    setEnvironmentState,
    setSurvivorsFound,
    setSurvivorsDetected,
    setRevealedCells,
    setTickCount,
    setMissionReport,
    setActiveTriage,
    setCoverage,
    addLog,
    discoveredRef,
    seenLogsRef
  });

  useEffect(() => {
    resetMission();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="h-screen w-screen overflow-hidden relative bg-[#0f1f1f]">
      {/* ── 3D MAP BACKGROUND (always rendered under dashboard) ── */}
      <div className="absolute inset-0 z-0">
        <DeckGLContainer 
          environmentState={environmentState} 
          drones={drones} 
          coverage={coverage}
          mode="god" 
          showCoords={showCoords}
          isNightMode={isNightMode}
          showXRay={showXRay}
        />
      </div>

      <motion.div
        key="dashboard"
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 1.02 }}
        transition={{ duration: 0.4, ease: "circOut" }}
        className="absolute inset-0 z-10 p-4 flex flex-col gap-4 pointer-events-none"
      >
        <div className="pointer-events-auto flex justify-center relative">
          <Header
            revealedCells={revealedCells}
            survivorsDetected={survivorsDetected}
            totalSurvivors={mapData?.survivors?.length || 0}
            isSimulationRunning={isSimulationRunning}
            isAborting={isAborting}
            isMapGenerated={isMapGenerated}
            onToggleSimulation={toggleSimulation}
            tickCount={tickCount}
          />

          {/* ── Tactical Control Panel (Top Right - Lifted to Interactive Layer) ── */}
          <div className="absolute top-0 right-0 z-20 flex flex-col gap-2 bg-neutral-dark/80 backdrop-blur-md p-3 rounded-xl border border-azure-dark/30 shadow-2xl pointer-events-auto">
            <label className="flex items-center gap-3 cursor-pointer group">
              <div className="relative">
                <input 
                  type="checkbox" 
                  className="sr-only" 
                  checked={isNightMode}
                  onChange={(e) => setIsNightMode(e.target.checked)}
                />
                <div className={`block w-10 h-6 rounded-full transition-colors ${isNightMode ? 'bg-azure-mid' : 'bg-neutral-dark border border-azure-dark/50'}`}></div>
                <div className={`absolute left-1 top-1 bg-mint-bg w-4 h-4 rounded-full transition-transform ${isNightMode ? 'translate-x-4' : ''}`}></div>
              </div>
              <span className="text-[11px] font-bold text-mint-bg uppercase tracking-wider group-hover:text-azure-mid transition-colors">Night Ops</span>
            </label>

            <label className="flex items-center gap-3 cursor-pointer group">
              <div className="relative">
                <input 
                  type="checkbox" 
                  className="sr-only" 
                  checked={showCoords}
                  onChange={(e) => setShowCoords(e.target.checked)}
                />
                <div className={`block w-10 h-6 rounded-full transition-colors ${showCoords ? 'bg-azure-mid' : 'bg-neutral-dark border border-azure-dark/50'}`}></div>
                <div className={`absolute left-1 top-1 bg-mint-bg w-4 h-4 rounded-full transition-transform ${showCoords ? 'translate-x-4' : ''}`}></div>
              </div>
              <span className="text-[11px] font-bold text-mint-bg uppercase tracking-wider group-hover:text-azure-mid transition-colors">Show Coords</span>
            </label>


            <label className="flex items-center gap-3 cursor-pointer group">
              <div className="relative">
                <input 
                  type="checkbox" 
                  className="sr-only" 
                  checked={showXRay}
                  onChange={(e) => setShowXRay(e.target.checked)}
                />
                <div className={`block w-10 h-6 rounded-full transition-colors ${showXRay ? 'bg-alert-orange' : 'bg-neutral-dark border border-azure-dark/50'}`}></div>
                <div className={`absolute left-1 top-1 bg-mint-bg w-4 h-4 rounded-full transition-transform ${showXRay ? 'translate-x-4' : ''}`}></div>
              </div>
              <span className="text-[11px] font-bold text-mint-bg uppercase tracking-wider group-hover:text-azure-mid transition-colors">View Through</span>
            </label>
          </div>
        </div>

        {/* ── Collapsible Log Panel (Left Edge) ── */}
        <LogPanel
          logs={logs}
          onClear={clearLogs}
          onDownload={downloadLogsAsText}
          isConnected={isSimulationRunning}
        />

        {/* ── Tactical Legend (Bottom Left) ── */}
        <div className="absolute bottom-6 left-16 pointer-events-auto bg-neutral-dark/80 backdrop-blur-md p-3 rounded-xl border border-azure-dark/30 shadow-2xl min-w-[160px]">
          <h3 className="text-[10px] font-bold text-azure-mid uppercase tracking-[0.2em] mb-3 border-b border-azure-dark/20 pb-1">Tactical Legend</h3>
          
          <div className="flex flex-col gap-2.5">
            <div className="flex items-center gap-3">
              <div className={`w-3.5 h-3.5 rounded-sm border ${isNightMode ? 'bg-[#e8da8d] border-[#e8da8d]/50' : 'bg-[#41ab5d] border-[#238b45]/50'}`}></div>
              <span className="text-[11px] font-medium text-mint-bg/90">Building</span>
            </div>
            
            <div className="flex items-center gap-3">
              <div className={`w-3.5 h-3.5 rounded-sm border ${isNightMode ? 'bg-[#ff3030] border-[#ff3030]/50' : 'bg-[#ef4444] border-[#b91c1c]/50'}`}></div>
              <span className="text-[11px] font-medium text-mint-bg/90">Obstacle</span>
            </div>

            <div className="flex items-center gap-3 mt-1 pt-2 border-t border-azure-dark/10">
              <div className="w-3.5 h-3.5 rounded-full bg-[#36c55e] shadow-[0_0_8px_#36c55e]"></div>
              <span className="text-[11px] font-medium text-mint-bg/90">Survivor (Found)</span>
            </div>

            <div className="flex items-center gap-3">
              <div className="w-3.5 h-3.5 rounded-full bg-[#ff7e00] shadow-[0_0_8px_#ff7e00]"></div>
              <span className="text-[11px] font-medium text-mint-bg/90">Survivor (Searching)</span>
            </div>
          </div>
        </div>

        {/* ── Active Triage Panel (Pops up when drone finds survivor) ── */}
        {activeTriage && (
          <SurvivorMic 
            droneId={activeTriage.droneId}
            survivorId={activeTriage.survivorId}
            onIntelReceived={(data) => {
              const intel = data.intel;
              const details = `Med Needs: ${intel.medical_needs?.join(', ') || 'None'}\nSupplies: ${intel.requested_supplies?.join(', ') || 'None'}`;
              
              addLog(
                'SYSTEM', 
                `Intel logged for survivor ${activeTriage.survivorId}. Urgency: ${intel.urgency_level}`, 
                'success', 
                { type: 'info', details }
              );
            }}
            onResolve={() => setActiveTriage(null)} 
          />
        )}

        {/* ── Swarm Status Panel (Right Edge) ── */}
        <SwarmStatusPanel
          drones={drones}
          isConnected={isSimulationRunning}
        />

        {/* ── Compile Map Data Button (Bottom Center) ── */}
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 pointer-events-auto">
          <button
            onClick={() => generateMapPreview()}
            disabled={isGenerating || isSimulationRunning}
            className={`bg-azure-dark hover:bg-azure-mid text-white text-sm font-medium px-4 py-2.5 rounded-xl shadow-[0_4px_12px_#164e6366] transition-all border border-azure-pale/20 disabled:opacity-50 flex items-center gap-2`}
          >

            {isGenerating ? (
               <>
                 <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                 Generating...
               </>
            ) : "Compile Map Data"}
          </button>

          {/* Add this somewhere visible, like next to your 'Compile Map Data' button */}
          <button 
            onClick={() => setActiveTriage({ droneId: 'drone_1', survivorId: 's_99' })}
            className="bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium px-4 py-2.5 rounded-xl absolute bottom-20 left-1/2 -translate-x-1/2 z-50"
          >
            [DEBUG] Force Triage Panel
          </button>
        </div>
      </motion.div>
      
      <AnimatePresence>
          {missionReport && (
            <MissionReportModal 
              report={missionReport} 
              onClose={() => setMissionReport(null)} 
            />
          )}
        </AnimatePresence>

    </div>
  );
}
