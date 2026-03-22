import React from 'react';
import { motion } from 'motion/react';
import { Activity, ChevronRight, ChevronLeft, Radio } from 'lucide-react';
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
    <aside className={`transition-all duration-400 ease-in-out h-full shrink-0 ${isSwarmPanelOpen ? 'w-72' : 'w-16'}`}>
      <div className="bg-neutral-dark h-full rounded-2xl shadow-2xl border border-white/5 flex flex-col min-h-0 overflow-hidden relative">
        <div className={`flex items-center justify-between p-5 border-b border-white/5 shrink-0 ${!isSwarmPanelOpen && 'flex-col gap-6'}`}>
          <div className={`flex items-center gap-2 ${!isSwarmPanelOpen && 'rotate-90 origin-center my-8'}`}>
            <Radio className="text-alert-yellow" size={20} />
            <h2 className="font-bold text-white capitalize text-base tracking-tight whitespace-nowrap">Swarm status</h2>
          </div>
          
          <div className="flex flex-col items-center gap-4">
            <motion.button
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.9 }}
              onClick={onToggleSwarmPanel}
              className="p-2 hover:bg-white/5 rounded-lg transition-colors text-white/30 hover:text-white"
              title={isSwarmPanelOpen ? "Collapse Sidebar" : "Expand Sidebar"}
            >
              {isSwarmPanelOpen ? <ChevronRight size={24} /> : <ChevronLeft size={24} />}
            </motion.button>
            
            {!isSwarmPanelOpen && (
              <div className="flex flex-col items-center gap-2">
                <span className="text-base font-bold text-white">{drones.length}</span>
                <span className="text-[10px] font-bold text-white/30 uppercase vertical-text tracking-widest">Units active</span>
              </div>
            )}
          </div>
        </div>

        <div className={`flex-1 overflow-y-auto custom-scrollbar p-3 space-y-3 ${!isSwarmPanelOpen && 'hidden'}`}>
          {drones.map(drone => (
            <DroneCard
              key={drone.id}
              drone={drone}
              isExpanded={expandedDroneId === drone.id}
              onToggle={() => onToggleDrone(drone.id)}
              logs={logs}
            />
          ))}
          {drones.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-4">
              <div className="w-14 h-14 bg-white/5 rounded-2xl flex items-center justify-center">
                <Activity size={28} className="text-white/20" />
              </div>
              <p className="text-sm text-white/30 font-medium">Waiting for swarm deployment...</p>
            </div>
          )}
        </div>

        {isSwarmPanelOpen && drones.length > 0 && (
          <div className="p-4 border-t border-white/5 bg-black/20 text-center">
            <span className="text-[12px] font-bold text-white/30 uppercase tracking-widest">{drones.length} active units</span>
          </div>
        )}
      </div>
    </aside>
  );
};

