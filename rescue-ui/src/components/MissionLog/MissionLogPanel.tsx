import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Terminal, ChevronDown, ChevronUp, GripHorizontal } from 'lucide-react';
import { LogEntry } from '../../types';

interface MissionLogPanelProps {
  logs: LogEntry[];
  isLogOpen: boolean;
  onToggleLog: () => void;
  logEndRef: React.RefObject<HTMLDivElement | null>;
  height: number;
  setHeight: (h: number) => void;
}

export const MissionLogPanel: React.FC<MissionLogPanelProps> = ({
  logs,
  isLogOpen,
  onToggleLog,
  logEndRef,
  height,
  setHeight
}) => {
  const [isResizing, setIsResizing] = useState(false);

  const startResizing = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  const stopResizing = useCallback(() => {
    setIsResizing(false);
  }, []);

  const resize = useCallback((e: MouseEvent) => {
    if (isResizing) {
      const newHeight = window.innerHeight - e.clientY - 20; // Adjust for padding
      if (newHeight > 40 && newHeight < 600) {
        setHeight(newHeight);
      }
    }
  }, [isResizing, setHeight]);

  useEffect(() => {
    window.addEventListener('mousemove', resize);
    window.addEventListener('mouseup', stopResizing);
    return () => {
      window.removeEventListener('mousemove', resize);
      window.removeEventListener('mouseup', stopResizing);
    };
  }, [resize, stopResizing]);

  return (
    <div 
      className={`transition-[height] duration-300 flex flex-col bg-neutral-dark rounded-2xl shadow-2xl border border-white/5 overflow-hidden relative ${isLogOpen ? '' : 'h-12!'}`}
      style={{ height: isLogOpen ? `${height}px` : '48px' }}
    >
      {/* Resize Handle */}
      {isLogOpen && (
        <div 
          onMouseDown={startResizing}
          className="absolute top-0 left-0 w-full h-1.5 cursor-row-resize hover:bg-azure-mid/40 transition-colors z-20 flex items-center justify-center"
        >
          <div className="w-8 h-0.5 bg-white/10 rounded-full" />
        </div>
      )}

      <div className="flex items-center justify-between px-5 py-3 border-b border-white/5 shrink-0 select-none">
        <div className="flex items-center gap-2">
          <Terminal size={18} className="text-azure-light" />
          <span className="text-sm font-bold text-white/60 capitalize tracking-tight">Mission Log</span>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-[12px] font-medium text-white/40">Real-time Feed</span>
          </div>
          <button
            onClick={onToggleLog}
            className="p-1.5 hover:bg-white/5 rounded-lg transition-colors text-white/30 hover:text-white"
          >
            {isLogOpen ? <ChevronDown size={20} /> : <ChevronUp size={20} />}
          </button>
        </div>
      </div>

      <div className={`flex-1 overflow-y-auto custom-scrollbar font-mono text-[13px] space-y-2.5 p-5 pr-2 ${!isLogOpen && 'hidden'}`}>
        <AnimatePresence initial={false}>
          {logs.map((log) => (
            <motion.div
              key={log.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex gap-4 border-l border-white/5 pl-4 group"
            >
              <span className="text-white/20 shrink-0 font-medium">{log.timestamp}</span>
              <span className={`font-bold shrink-0 capitalize ${log.type === 'success' ? 'text-emerald-400' :
                  log.type === 'warning' ? 'text-alert-orange' :
                    log.type === 'error' ? 'text-alert-red' : 'text-azure-light'
                }`}>
                {log.agent}
              </span>
              <p className="text-gray-200 leading-relaxed font-medium">{log.message}</p>
            </motion.div>
          ))}
        </AnimatePresence>
        <div ref={logEndRef} />
      </div>
    </div>
  );
};

