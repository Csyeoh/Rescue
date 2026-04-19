"use client";

import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  Terminal,
  ChevronLeft,
  ChevronRight,
  Trash2,
  Download,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Info,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { LogEntry } from '../../types';

interface LogPanelProps {
  logs: LogEntry[];
  onClear?: () => void;
  onDownload?: () => void;
  isConnected?: boolean;
}

const TYPE_CONFIG = {
  success: {
    icon: CheckCircle2,
    color: '#36c55e',
    bg: 'rgba(54,197,94,0.08)',
    border: 'rgba(54,197,94,0.25)',
    badge: 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30',
    label: 'OK',
  },
  warning: {
    icon: AlertTriangle,
    color: '#d96627',
    bg: 'rgba(217,102,39,0.08)',
    border: 'rgba(217,102,39,0.25)',
    badge: 'bg-orange-500/20 text-orange-400 border border-orange-500/30',
    label: 'WARN',
  },
  error: {
    icon: XCircle,
    color: '#d65b34',
    bg: 'rgba(214,91,52,0.08)',
    border: 'rgba(214,91,52,0.25)',
    badge: 'bg-red-500/20 text-red-400 border border-red-500/30',
    label: 'ERR',
  },
  info: {
    icon: Info,
    color: '#6aa7ad',
    bg: 'rgba(106,167,173,0.05)',
    border: 'rgba(106,167,173,0.15)',
    badge: 'bg-sky-500/10 text-sky-400 border border-sky-500/20',
    label: 'INFO',
  },
};

const AGENT_COLORS: Record<string, string> = {
  SYSTEM: '#6aa7ad',
  COMMAND: '#e8da8d',
  AGENT: '#a78bfa',
};

function agentColor(agent: string): string {
  if (AGENT_COLORS[agent.toUpperCase()]) return AGENT_COLORS[agent.toUpperCase()];
  // Drone IDs get a consistent hue derived from their index
  const hash = agent.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0);
  const hues = [200, 160, 280, 40, 320, 60, 180, 240];
  return `hsl(${hues[hash % hues.length]}, 70%, 65%)`;
}

function formatAgent(agent: string): string {
  if (agent.startsWith('drone_')) return `Drone #${agent.split('_')[1]}`;
  return agent;
}

const LogRow: React.FC<{ log: LogEntry; index: number }> = ({ log, index }) => {
  const [expanded, setExpanded] = useState(false);
  const cfg = TYPE_CONFIG[log.type] ?? TYPE_CONFIG.info;
  const Icon = cfg.icon;
  const hasDetails = !!log.details;

  return (
    <motion.div
      initial={{ opacity: 0, x: -12, y: 4 }}
      animate={{ opacity: 1, x: 0, y: 0 }}
      transition={{ duration: 0.22, ease: 'easeOut', delay: Math.min(index * 0.02, 0.3) }}
      className="group"
    >
      <div
        className={`relative rounded-lg border transition-all duration-150 ${hasDetails ? 'cursor-pointer' : ''}`}
        style={{ background: cfg.bg, borderColor: cfg.border }}
        onClick={() => hasDetails && setExpanded((p) => !p)}
      >
        {/* Left accent line */}
        <div
          className="absolute left-0 top-2 bottom-2 w-0.5 rounded-full"
          style={{ background: cfg.color }}
        />

        <div className="flex items-start gap-3 px-4 py-2.5 pl-5">
          {/* Icon */}
          <Icon size={16} className="mt-0.5 shrink-0" style={{ color: cfg.color }} />

          {/* Body */}
          <div className="flex-1 min-w-0">
            {/* Header row */}
            <div className="flex items-center gap-2 flex-wrap">
              <span
                className="text-sm font-semibold tracking-wide shrink-0"
                style={{ color: agentColor(log.agent) }}
              >
                {formatAgent(log.agent)}
              </span>
              <span className={`text-xs px-1.5 py-0.5 rounded-full font-mono font-bold ${cfg.badge}`}>
                {cfg.label}
              </span>
              <span className="text-xs text-white/25 font-mono ml-auto shrink-0">
                {log.timestamp}
              </span>
            </div>

            {/* Message */}
            <p className="text-sm text-white/70 mt-1 leading-relaxed break-words whitespace-pre-wrap font-mono">
              {log.message}
            </p>

            {/* Details (expandable) */}
            <AnimatePresence>
              {expanded && log.details && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="overflow-hidden"
                >
                  <pre className="mt-2 text-[13px] text-white/50 font-mono bg-black/30 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all border border-white/5">
                    {JSON.stringify(log.details, null, 2)}
                  </pre>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Expand hint */}
            {hasDetails && (
              <span className="text-xs text-white/25 mt-0.5 block">
                {expanded ? '▲ collapse' : '▼ show details'}
              </span>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export const LogPanel: React.FC<LogPanelProps> = ({
  logs,
  onClear,
  onDownload,
  isConnected = true,
}) => {
  const [isOpen, setIsOpen] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  // Auto-scroll to bottom when new logs arrive (if auto-scroll is on)
  useEffect(() => {
    if (autoScroll && isOpen) {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
    }
  }, [logs, autoScroll, isOpen]);

  // Detect manual scroll-up to pause auto-scroll
  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 40);
  };

  const errorCount  = logs.filter((l) => l.type === 'error').length;
  const warnCount   = logs.filter((l) => l.type === 'warning').length;

  return (
    <div className="absolute left-4 bottom-6 top-24 z-20 flex items-end pointer-events-none">
      {/* Panel + toggle wrapper — always positioned on left edge */}
      <div className="flex items-end h-full pointer-events-auto">

        {/* ── Slide-in Panel ── */}
        <AnimatePresence initial={false}>
          {isOpen && (
            <motion.div
              key="log-panel"
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 440, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ type: 'spring', stiffness: 280, damping: 30 }}
              className="h-full overflow-hidden"
              style={{ pointerEvents: 'auto' }}
            >
              <div
                className="h-full w-[440px] flex flex-col rounded-2xl border shadow-2xl"
                style={{
                  background: 'rgba(15,31,31,0.88)',
                  backdropFilter: 'blur(18px)',
                  WebkitBackdropFilter: 'blur(18px)',
                  borderColor: 'rgba(65,110,111,0.35)',
                  boxShadow: '0 8px 40px rgba(0,0,0,0.6), inset 0 1px 0 rgba(106,167,173,0.08)',
                }}
              >
                {/* ── Header ── */}
                <div
                  className="flex items-center gap-3 px-4 py-3 border-b shrink-0"
                  style={{ borderColor: 'rgba(65,110,111,0.25)' }}
                >
                  <div className="relative">
                    <Terminal size={18} className="text-azure-mid" />
                    {/* Connection dot */}
                    <span
                      className={`absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full ${
                        isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'
                      }`}
                    />
                  </div>

                  <div className="flex-1 min-w-0">
                    <span className="text-[15px] font-semibold text-mint-bg/90 tracking-wide">
                      Mission Log
                    </span>
                    <div className="flex items-center gap-2 mt-0.5">
                      {isConnected ? (
                        <span className="flex items-center gap-1 text-[13px] text-emerald-400">
                          <Wifi size={11} /> Live feed
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-[13px] text-red-400">
                          <WifiOff size={11} /> Disconnected
                        </span>
                      )}
                      <span className="text-[13px] text-white/30">·</span>
                      <span className="text-[13px] text-white/40 font-mono">{logs.length} events</span>
                      {errorCount > 0 && (
                        <span className="text-[13px] font-bold text-red-400 font-mono">{errorCount}err</span>
                      )}
                      {warnCount > 0 && (
                        <span className="text-[13px] font-bold text-orange-400 font-mono">{warnCount}warn</span>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1.5 shrink-0">
                    {onDownload && (
                      <button
                        title="Download logs"
                        onClick={onDownload}
                        className="p-1.5 rounded-lg text-white/30 hover:text-azure-mid hover:bg-azure-dark/20 transition-all"
                      >
                        <Download size={14} />
                      </button>
                    )}
                    {onClear && (
                      <button
                        title="Clear logs"
                        onClick={onClear}
                        className="p-1.5 rounded-lg text-white/30 hover:text-alert-red hover:bg-red-500/10 transition-all"
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                </div>

                {/* ── Auto-scroll indicator ── */}
                {!autoScroll && (
                  <div className="px-3 py-1.5 bg-azure-dark/20 border-b border-azure-dark/20 flex items-center justify-between shrink-0">
                    <span className="text-[13px] text-azure-mid">Scrolled up — paused</span>
                    <button
                      onClick={() => {
                        setAutoScroll(true);
                        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
                      }}
                      className="text-[13px] text-azure-mid underline hover:text-mint-bg transition-colors"
                    >
                      Resume ↓
                    </button>
                  </div>
                )}

                {/* ── Log list ── */}
                <div
                  ref={scrollRef}
                  onScroll={handleScroll}
                  className="flex-1 overflow-y-auto px-3 py-3 flex flex-col gap-2 min-h-0"
                  style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(65,110,111,0.4) transparent' }}
                >
                  {logs.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full gap-3 opacity-30">
                      <Terminal size={28} className="text-azure-mid" />
                      <span className="text-sm text-white/50 font-mono">Awaiting telemetry…</span>
                    </div>
                  ) : (
                    logs.map((log, i) => <LogRow key={log.id} log={log} index={i} />)
                  )}
                </div>

                {/* ── Footer removed ── */}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Toggle Tab ── */}
        <motion.button
          onClick={() => setIsOpen((p) => !p)}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          title={isOpen ? 'Collapse log panel' : 'Expand log panel'}
          className="relative ml-1.5 mb-4 flex flex-col items-center gap-1.5 px-1.5 py-4 rounded-xl border shadow-xl transition-colors"
          style={{
            background: isOpen ? 'rgba(65,110,111,0.35)' : 'rgba(15,31,31,0.82)',
            backdropFilter: 'blur(14px)',
            WebkitBackdropFilter: 'blur(14px)',
            borderColor: isOpen ? 'rgba(106,167,173,0.45)' : 'rgba(65,110,111,0.28)',
            boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
          }}
        >
          {/* Unread badge */}
          {!isOpen && logs.length > 0 && (
            <span
              className="absolute -top-1.5 -right-1.5 min-w-[16px] h-4 px-1 rounded-full text-[8px] font-bold text-white flex items-center justify-center"
              style={{ background: errorCount > 0 ? '#d65b34' : '#416e6f' }}
            >
              {logs.length > 99 ? '99+' : logs.length}
            </span>
          )}

          {isOpen ? (
            <ChevronLeft size={13} className="text-azure-mid" />
          ) : (
            <ChevronRight size={13} className="text-azure-mid" />
          )}

          {/* Vertical label */}
          <span
            className="text-[9px] font-bold tracking-[0.2em] text-azure-mid/80"
            style={{ writingMode: 'vertical-rl', textOrientation: 'mixed' }}
          >
            LOG
          </span>

          {/* Live pulse dot */}
          <span
            className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'}`}
          />
        </motion.button>
      </div>
    </div>
  );
};
