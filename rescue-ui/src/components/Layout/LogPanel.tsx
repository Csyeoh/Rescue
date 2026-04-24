"use client";

import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  Terminal,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Trash2,
  Download,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Info,
  Brain,
  Wrench,
  ArrowDownToLine,
  Wifi,
  WifiOff,
  Filter,
  FilterX,
} from 'lucide-react';
import { LogEntry } from '../../types';

interface LogPanelProps {
  logs: LogEntry[];
  onClear?: () => void;
  onDownload?: () => void;
  isConnected?: boolean;
}

// ── Type config ─────────────────────────────────────────────────────────────

const TYPE_CONFIG = {
  reasoning: {
    icon: Brain,
    color: '#a78bfa',
    bg: 'rgba(167,139,250,0.08)',
    border: 'rgba(167,139,250,0.22)',
    badge: 'bg-violet-500/15 text-violet-400 border border-violet-500/25',
    label: 'THINK',
  },
  tool_call: {
    icon: Wrench,
    color: '#38bdf8',
    bg: 'rgba(56,189,248,0.08)',
    border: 'rgba(56,189,248,0.22)',
    badge: 'bg-sky-500/15 text-sky-400 border border-sky-500/25',
    label: 'CALL',
  },
  tool_response: {
    icon: ArrowDownToLine,
    color: '#36c55e',
    bg: 'rgba(54,197,94,0.06)',
    border: 'rgba(54,197,94,0.20)',
    badge: 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/25',
    label: 'RESULT',
  },
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

// ── Agent colors ────────────────────────────────────────────────────────────

const AGENT_COLORS: Record<string, string> = {
  SYSTEM: '#6aa7ad',
  COMMAND: '#e8da8d',
  AGENT: '#a78bfa',
  SWARM_DISPATCHER: '#a78bfa',
  CENTRAL_COMMANDER: '#a78bfa',
};

function agentColor(agent: string): string {
  if (AGENT_COLORS[agent.toUpperCase()]) return AGENT_COLORS[agent.toUpperCase()];
  const hash = agent.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0);
  const hues = [200, 160, 280, 40, 320, 60, 180, 240];
  return `hsl(${hues[hash % hues.length]}, 70%, 65%)`;
}

function formatAgent(agent: string): string {
  if (agent.startsWith('drone_')) return `Drone #${agent.split('_')[1]}`;
  if (agent === 'SWARM_DISPATCHER') return 'Central Commander';
  return agent;
}

// ── Tick Separator ──────────────────────────────────────────────────────────
const TickSeparator: React.FC<{ tick: number }> = ({ tick }) => (
  <motion.div
    initial={{ opacity: 0, scaleY: 0 }}
    animate={{ opacity: 1, scaleY: 1 }}
    className="flex items-center gap-3 my-2 px-1"
  >
    <div className="h-px flex-1 bg-gradient-to-r from-transparent via-azure-mid/30 to-transparent" />
    <span className="text-[10px] font-mono font-bold text-azure-mid uppercase tracking-[0.2em] whitespace-nowrap bg-neutral-dark/40 px-2 py-0.5 rounded border border-azure-mid/20">
      Mission Tick {tick < 10 ? `00${tick}` : tick < 100 ? `0${tick}` : tick}
    </span>
    <div className="h-px flex-1 bg-gradient-to-r from-azure-mid/30 via-azure-mid/30 to-transparent" />
  </motion.div>
);

// ── Log Row ─────────────────────────────────────────────────────────────────

const LogRow: React.FC<{ log: LogEntry; index: number }> = ({ log, index }) => {
  const [expanded, setExpanded] = useState(false);
  const cfg = TYPE_CONFIG[log.type] ?? TYPE_CONFIG.info;
  const Icon = cfg.icon;

  // Determine if this row has expandable content
  const hasExpandable =
    (log.type === 'reasoning' && !!log.details?.thought) ||
    (log.type === 'tool_call' && log.details?.tool_args && Object.keys(log.details.tool_args).length > 0) ||
    (log.type === 'tool_response' && !!log.details?.result_message);

  return (
    <motion.div
      initial={{ opacity: 0, x: -12, y: 4 }}
      animate={{ opacity: 1, x: 0, y: 0 }}
      transition={{ duration: 0.22, ease: 'easeOut', delay: Math.min(index * 0.02, 0.3) }}
      className="group"
    >
      <div
        className={`relative rounded-lg border transition-all duration-150 ${hasExpandable ? 'cursor-pointer' : ''}`}
        style={{ background: cfg.bg, borderColor: cfg.border }}
        onClick={() => hasExpandable && setExpanded((p) => !p)}
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
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-mono font-bold ${cfg.badge}`}>
                {cfg.label}
              </span>
              <div className="flex items-center gap-2 ml-auto shrink-0">
                <span className="text-[11px] text-white/25 font-mono">
                  {log.timestamp}
                </span>
              </div>
            </div>

            {/* Message — type-specific rendering */}
            {log.type === 'reasoning' && (
              <p className="text-[13px] text-white/75 mt-1.5 leading-relaxed break-words">
                {log.message}
              </p>
            )}

            {log.type === 'tool_call' && (
              <p className="text-[13px] text-sky-300/80 mt-1.5 leading-relaxed break-words font-mono">
                {log.message}
              </p>
            )}

            {log.type === 'tool_response' && (
              <p className="text-[13px] text-emerald-300/70 mt-1.5 leading-relaxed break-words">
                {log.message.length > 120 ? log.message.slice(0, 120) + '…' : log.message}
              </p>
            )}

            {!['reasoning', 'tool_call', 'tool_response'].includes(log.type) && (
              <p className="text-[13px] text-white/60 mt-1 leading-relaxed break-words whitespace-pre-wrap font-mono">
                {log.message}
              </p>
            )}

            {/* Expandable details */}
            <AnimatePresence>
              {expanded && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="overflow-hidden"
                >
                  {/* Reasoning → show thought */}
                  {log.type === 'reasoning' && log.details?.thought && (
                    <div
                      className="mt-2 rounded-lg px-3 py-2.5 text-[13px] text-violet-300/80 leading-relaxed border-l-2 italic"
                      style={{
                        background: 'rgba(167,139,250,0.06)',
                        borderColor: 'rgba(167,139,250,0.30)',
                      }}
                    >
                      {log.details.thought}
                    </div>
                  )}

                  {/* Tool call → show args as key=value rows */}
                  {log.type === 'tool_call' && log.details?.tool_args && (
                    <div
                      className="mt-2 rounded-lg px-3 py-2 text-[12px] font-mono leading-relaxed space-y-0.5"
                      style={{ background: 'rgba(56,189,248,0.06)' }}
                    >
                      {Object.entries(log.details.tool_args).map(([k, v]) => (
                        <div key={k} className="flex gap-2">
                          <span className="text-sky-400/60">{k}:</span>
                          <span className="text-sky-300/90">{JSON.stringify(v)}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Tool response → show full result message */}
                  {log.type === 'tool_response' && log.details?.result_message && (
                    <pre
                      className="mt-2 rounded-lg px-3 py-2 text-[12px] font-mono text-emerald-300/70 leading-relaxed whitespace-pre-wrap break-all"
                      style={{ background: 'rgba(54,197,94,0.06)' }}
                    >
                      {log.details.result_message}
                    </pre>
                  )}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Expand hint */}
            {hasExpandable && (
              <div className="flex items-center gap-1 mt-1 text-[11px] text-white/25">
                {expanded ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
                <span>{expanded ? 'collapse' : 'show details'}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
};

// ── Panel ───────────────────────────────────────────────────────────────────

export const LogPanel: React.FC<LogPanelProps> = ({
  logs,
  onClear,
  onDownload,
  isConnected = true,
}) => {
  const [isOpen, setIsOpen] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [selectedAgents, setSelectedAgents] = useState<Set<string>>(new Set());

  // Dynamic agent discovery
  const allAgents = Array.from(new Set(logs.map(l => l.agent)))
    .sort((a, b) => {
      if (a === 'SYSTEM' || a === 'SWARM_DISPATCHER') return -1;
      if (b === 'SYSTEM' || b === 'SWARM_DISPATCHER') return 1;
      return a.localeCompare(b);
    });

  const toggleAgent = (agent: string) => {
    setSelectedAgents(prev => {
      const next = new Set(prev);
      if (next.has(agent)) next.delete(agent);
      else next.add(agent);
      return next;
    });
  };

  const filteredLogs = selectedAgents.size === 0 
    ? logs 
    : logs.filter(l => selectedAgents.has(l.agent));

  useEffect(() => {
    if (autoScroll && isOpen) {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
    }
  }, [filteredLogs, autoScroll, isOpen]);

  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 40);
  };

  const errorCount = logs.filter((l) => l.type === 'error').length;
  const warnCount = logs.filter((l) => l.type === 'warning').length;

  return (
    <div className="absolute left-4 bottom-6 top-24 z-20 flex items-end pointer-events-none">
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

                {/* ── Filtering Area ── */}
                {allAgents.length > 0 && (
                  <div 
                    className="px-3 py-2 border-b flex items-center gap-2 overflow-x-auto no-scrollbar shrink-0"
                    style={{ borderColor: 'rgba(65,110,111,0.15)', background: 'rgba(0,0,0,0.1)' }}
                  >
                    <button
                      onClick={() => setSelectedAgents(new Set())}
                      className={`px-2 py-0.5 rounded-md text-[10px] font-bold tracking-wider transition-all border shrink-0 ${
                        selectedAgents.size === 0 
                          ? 'bg-azure-dark/40 text-mint-bg border-azure-mid/50' 
                          : 'text-white/20 border-white/5 hover:border-white/10 hover:text-white/40'
                      }`}
                    >
                      ALL
                    </button>
                    <div className="w-px h-3 bg-white/10 shrink-0" />
                    <div className="flex gap-2 overflow-x-auto no-scrollbar">
                      {allAgents.map(agent => {
                        const isSelected = selectedAgents.has(agent);
                        const color = agentColor(agent);
                        return (
                          <button
                            key={agent}
                            onClick={() => toggleAgent(agent)}
                            className={`px-2 py-0.5 rounded-md text-[10px] font-bold tracking-wider transition-all border whitespace-nowrap ${
                              isSelected 
                                ? 'text-white border-opacity-100' 
                                : 'text-white/30 border-transparent hover:text-white/50'
                            }`}
                            style={{ 
                              backgroundColor: isSelected ? `${color}33` : 'transparent',
                              borderColor: isSelected ? `${color}60` : 'rgba(255,255,255,0.05)'
                            }}
                          >
                            {formatAgent(agent).toUpperCase()}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

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
                  {filteredLogs.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full gap-3 opacity-30">
                      {selectedAgents.size > 0 ? (
                        <>
                          <FilterX size={28} className="text-azure-mid" />
                          <span className="text-sm text-white/50 font-mono text-center px-4">
                            No events from selected agents
                          </span>
                        </>
                      ) : (
                        <>
                          <Terminal size={28} className="text-azure-mid" />
                          <span className="text-sm text-white/50 font-mono">Awaiting telemetry…</span>
                        </>
                      )}
                    </div>
                  ) : (
                    filteredLogs.reduce((acc: React.ReactNode[], log, i) => {
                      const prevLog = filteredLogs[i - 1];
                      if (log.tick !== undefined && (!prevLog || prevLog.tick !== log.tick)) {
                        acc.push(<TickSeparator key={`tick-${log.tick}-${i}`} tick={log.tick} />);
                      }
                      acc.push(<LogRow key={log.id} log={log} index={i} />);
                      return acc;
                    }, [])
                  )}
                </div>
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

          <span
            className="text-[9px] font-bold tracking-[0.2em] text-azure-mid/80"
            style={{ writingMode: 'vertical-rl', textOrientation: 'mixed' }}
          >
            LOG
          </span>

          <span
            className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'}`}
          />
        </motion.button>
      </div>
    </div>
  );
};
