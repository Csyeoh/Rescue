import React, { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Drone as DroneIcon, Terminal, Battery, Cpu, Navigation, Activity } from 'lucide-react';
import { DroneStatus, LogEntry } from '../../types';

interface DroneCardProps {
  drone: DroneStatus;
  isExpanded: boolean;
  onToggle: () => void;
  logs: LogEntry[];
}

export const DroneCard: React.FC<DroneCardProps> = ({
  drone,
  isExpanded,
  onToggle,
  logs
}) => {
  const droneLogs = logs.filter(l => l.agent === drone.id);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isExpanded && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [isExpanded, droneLogs.length]);

  const getStatusColor = () => {
    switch (drone.status) {
      case 'searching': return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
      case 'returning': return 'text-alert-orange bg-alert-orange/10 border-alert-orange/20';
      case 'charging': return 'text-alert-yellow bg-alert-yellow/10 border-alert-yellow/20';
      default: return 'text-white/40 bg-white/5 border-white/10';
    }
  };

  return (
    <motion.div
      layout
      onClick={onToggle}
      className={`cursor-pointer transition-all duration-300 rounded-2xl border ${isExpanded 
        ? 'bg-white/10 border-azure-mid/30 shadow-[0_8px_24px_rgba(0,0,0,0.2)]' 
        : 'bg-white/5 border-white/5 hover:bg-white/10 hover:border-white/10'
        } p-4 overflow-hidden select-none`}
    >
      {/* Collapsed Header */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className={`p-2.5 rounded-xl transition-colors ${isExpanded ? 'bg-azure-dark/40 text-white' : 'bg-white/5 text-white/40'}`}>
            <DroneIcon size={18} />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white tracking-tight capitalize">{drone.id.replace('_', ' ')}</h3>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className={`text-[11px] font-bold px-2 py-0.5 rounded capitalize border ${getStatusColor()}`}>
                {drone.status}
              </span>
            </div>
          </div>
        </div>

        {!isExpanded && (
          <div className="flex flex-col items-end gap-1.5">
            <span className={`text-[12px] font-bold ${drone.battery < 20 ? 'text-alert-red' : 'text-white/60'}`}>
              {Math.floor(drone.battery)}%
            </span>
            <div className="w-20 h-1.5 bg-white/5 rounded-full overflow-hidden">
              <motion.div
                className={`h-full ${drone.battery < 20 ? 'bg-alert-red' : drone.battery < 50 ? 'bg-alert-yellow' : 'bg-emerald-500'}`}
                animate={{ width: `${drone.battery}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Expanded Content */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: "circOut" }}
            className="mt-6 space-y-5"
          >
            {/* Core Telemetry */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-black/20 p-3 rounded-xl border border-white/5 flex flex-col gap-1.5">
                <div className="flex items-center gap-2 text-[11px] font-bold text-white/30 capitalize">
                  <Battery size={12} />
                  <span>Battery system</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-base font-bold text-white">{Math.floor(drone.battery)}%</span>
                  <div className="flex-1 h-2 bg-white/5 rounded-full overflow-hidden">
                    <motion.div 
                      className={`h-full rounded-full ${drone.battery < 20 ? 'bg-alert-red' : 'bg-emerald-400'}`}
                      animate={{ width: `${drone.battery}%` }}
                    />
                  </div>
                </div>
              </div>

              <div className="bg-black/20 p-3 rounded-xl border border-white/5 flex flex-col gap-1.5">
                <div className="flex items-center gap-2 text-[11px] font-bold text-white/30 capitalize">
                  <Navigation size={12} />
                  <span>GPS Coordinates</span>
                </div>
                <div className="text-base font-bold text-azure-light font-mono">
                  {drone.x.toString().padStart(2, '0')}, {drone.y.toString().padStart(2, '0')}
                </div>
              </div>
            </div>

            {/* Performance Stats */}
            <div className="bg-black/20 p-3 rounded-xl border border-white/5">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2 text-[11px] font-bold text-white/30 capitalize">
                  <Activity size={12} />
                  <span>Real-time telemetry</span>
                </div>
                <div className="text-[11px] font-bold text-emerald-400 font-mono">
                  {drone.stepsTaken} steps
                </div>
              </div>
              
              <div className="space-y-1.5">
                <div className="flex items-center gap-2 px-1">
                  <Terminal size={12} className="text-white/20" />
                  <span className="text-[11px] font-bold text-white/20 capitalize">Agent logs</span>
                </div>
                <div className="h-32 bg-black/40 rounded-xl p-3 font-mono text-[12px] overflow-y-auto custom-scrollbar border border-white/5 space-y-1.5">
                  {droneLogs.length === 0 ? (
                    <div className="text-white/10 italic py-2">No active telemetry...</div>
                  ) : (
                    droneLogs.map((log, idx) => (
                      <div key={idx} className="flex gap-2">
                        <span className="text-white/10 shrink-0">[{log.timestamp.split(' ')[0]}]</span>
                        <span className={`font-medium ${
                          log.type === 'success' ? 'text-emerald-400' :
                            log.type === 'warning' ? 'text-alert-yellow' :
                              log.type === 'error' ? 'text-alert-red' : 'text-azure-light'
                        }`}>
                          {log.message}
                        </span>
                      </div>
                    ))
                  )}
                  <div ref={logEndRef} />
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

