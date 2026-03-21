import React, { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Drone, Terminal } from 'lucide-react';
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

  return (
    <div
      onClick={onToggle}
      className={`cursor-pointer transition-all duration-300 rounded-xl border ${isExpanded ? 'bg-white/10 border-cyan-500/50 shadow-[0_0_15px_rgba(6,182,212,0.2)]' : 'bg-white/5 border-white/5 hover:bg-white/10'
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
        <span className={`text-[9px] font-bold px-2 py-0.5 rounded uppercase ${drone.status === 'patrolling' ? 'bg-emerald-500/20 text-emerald-400' :
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
                      className={`w-1.5 h-1.5 rounded-full transition-all duration-300 ${drone.status === 'patrolling' && i === 1
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
                          className={`flex-1 rounded-sm ${drone.battery >= i * 25
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
};
