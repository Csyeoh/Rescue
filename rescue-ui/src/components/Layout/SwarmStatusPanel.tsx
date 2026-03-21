import React from 'react';
import { Activity, ChevronRight, ChevronLeft } from 'lucide-react';
import { DroneStatus, LogEntry } from '../../types';
import { DroneCard } from '../Drone/DroneCard';

interface SwarmStatusPanelProps {
  drones: DroneStatus[];
  isSwarmPanelOpen: boolean;
  onToggleSwarmPanel: () => void;
  expandedDroneId: string | null;
  onToggleDrone: (id: string) => void;
  logs: LogEntry[];
}

export const SwarmStatusPanel: React.FC<SwarmStatusPanelProps> = ({
  drones,
  isSwarmPanelOpen,
  onToggleSwarmPanel,
  expandedDroneId,
  onToggleDrone,
  logs
}) => {
  return (
    <aside className={`transition-all duration-300 ${isSwarmPanelOpen ? 'w-64' : 'w-14'} flex flex-col gap-2 shrink-0 overflow-y-auto custom-scrollbar pr-1`}>
      <div className="bg-[#1A202C] p-4 rounded-xl shadow-xl border border-white/10 flex-1 flex flex-col min-h-0 overflow-hidden">
        <div className={`flex items-center justify-between mb-4 ${!isSwarmPanelOpen && 'flex-col gap-4'}`}>
          <div className={`flex items-center gap-2 ${!isSwarmPanelOpen && 'rotate-90 origin-center my-8'}`}>
            <Activity className="text-yellow-400" size={18} />
            <h2 className="font-bold text-white uppercase text-sm tracking-tight whitespace-nowrap">Swarm Status</h2>
          </div>
          <div className="flex flex-col items-center gap-3">
            <button
              onClick={onToggleSwarmPanel}
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
                onToggle={() => onToggleDrone(drone.id)}
                logs={logs}
              />
            ))}
          </div>
        )}
      </div>
    </aside>
  );
};
