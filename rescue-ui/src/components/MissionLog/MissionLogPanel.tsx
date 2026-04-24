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
              <div className="flex flex-col gap-1 w-full overflow-hidden">
                <div className="flex gap-2 items-baseline">
                  <span className={`font-bold shrink-0 capitalize ${log.type === 'success' ? 'text-emerald-400' :
                      log.type === 'warning' ? 'text-alert-orange' :
                        log.type === 'error' ? 'text-alert-red' : 'text-azure-light'
                    }`}>
                    {log.agent}
                  </span>
                  <p className="text-gray-200 leading-relaxed font-medium whitespace-pre-wrap">{log.message}</p>
                </div>
                {log.details && log.details.type === 'reasoning' && (
                  <div className="mt-1 bg-white/5 rounded-md p-3 text-[12px] text-white/80 border border-white/10 overflow-x-auto">
                    <p className="font-semibold text-azure-light mb-1">
                      Plan (Task: {String(log.details.task_id ?? '')}) - Ready: {Boolean(log.details.ready) ? 'Yes' : 'No'}
                    </p>
                    <pre className="whitespace-pre-wrap font-mono">
                      {typeof log.details.plan === 'string' ? log.details.plan : JSON.stringify(log.details.plan, null, 2)}
                    </pre>
                  </div>
                )}
                {log.details && log.details.type === 'tool_execution' && (
                  <div className="mt-1 bg-white/5 rounded-md p-3 text-[12px] text-white/80 border border-white/10 overflow-x-auto">
                    <div className="flex justify-between items-center mb-1">
                      <p className="font-semibold text-emerald-400">Tool Executed: {String(log.details.tool_name ?? '')}</p>
                      {typeof log.details.execution_duration_ms === 'number' && (
                        <span className="text-white/40">{Math.round(log.details.execution_duration_ms)}ms</span>
                      )}
                    </div>
                    {log.details.tool_args && (
                      <div className="mb-2">
                        <span className="text-white/40 font-semibold text-[10px] uppercase">Arguments</span>
                        <pre className="text-white/70 whitespace-pre-wrap">{JSON.stringify(log.details.tool_args, null, 2)}</pre>
                      </div>
                    )}
                    {log.details.result != null && (
                      <div>
                        <span className="text-white/40 font-semibold text-[10px] uppercase">Result</span>
                        <pre className="text-white/70 whitespace-pre-wrap">{typeof log.details.result === 'string' ? log.details.result : JSON.stringify(log.details.result as unknown, null, 2)}</pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        <div ref={logEndRef} />
      </div>
    </div>
  );
};

