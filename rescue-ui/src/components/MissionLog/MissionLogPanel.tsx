import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Terminal, ChevronDown, ChevronUp } from 'lucide-react';
import { LogEntry } from '../../types';

interface MissionLogPanelProps {
  logs: LogEntry[];
  isLogOpen: boolean;
  onToggleLog: () => void;
  logEndRef: React.RefObject<HTMLDivElement | null>;
}

export const MissionLogPanel: React.FC<MissionLogPanelProps> = ({
  logs,
  isLogOpen,
  onToggleLog,
  logEndRef
}) => {
  return (
    <div className={`transition-all duration-300 flex flex-col ${isLogOpen ? 'h-32' : 'h-10'} bg-[#1A202C] rounded-xl shadow-xl border border-white/10 overflow-hidden`}>
      <div className="flex items-center justify-between px-4 py-2 border-b border-white/5 shrink-0">
        <div className="flex items-center gap-2">
          <Terminal size={14} className="text-cyan-400" />
          <span className="text-[10px] font-black text-white/50 uppercase tracking-widest">Mission Log</span>
        </div>
        <button
          onClick={onToggleLog}
          className="p-1 hover:bg-white/5 rounded-md transition-colors text-white/30 hover:text-white"
        >
          {isLogOpen ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
        </button>
      </div>

      <div className={`flex-1 overflow-y-auto custom-scrollbar font-mono text-[10px] space-y-1.5 p-4 pr-2 ${!isLogOpen && 'hidden'}`}>
        <AnimatePresence initial={false}>
          {logs.map((log) => (
            <motion.div
              key={log.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex gap-3 border-l border-white/10 pl-3"
            >
              <span className="text-white/20 shrink-0">{log.timestamp}</span>
              <span className={`font-bold shrink-0 ${log.type === 'success' ? 'text-emerald-400' :
                  log.type === 'warning' ? 'text-yellow-400' :
                    log.type === 'error' ? 'text-red-400' : 'text-cyan-400'
                }`}>
                [{log.agent}]
              </span>
              <p className="text-gray-300 leading-tight">{log.message}</p>
            </motion.div>
          ))}
        </AnimatePresence>
        <div ref={logEndRef} />
      </div>
    </div>
  );
};
