"use client";

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  ChevronLeft,
  ChevronRight,
  Cpu,
  Battery,
  Navigation,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { DroneStatus, SurvivorNode } from '../../types';

interface SwarmStatusPanelProps {
  drones: DroneStatus[];
  survivors?: SurvivorNode[];
  selectedSurvivorId?: string | null;
  onSelectSurvivor?: (id: string | null) => void;
  isConnected?: boolean;
}

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string; border: string }> = {
  searching: {
    label: 'Searching',
    color: '#36c55e',
    bg: 'rgba(54,197,94,0.12)',
    border: 'rgba(54,197,94,0.30)',
  },
  returning: {
    label: 'Returning',
    color: '#d96627',
    bg: 'rgba(217,102,39,0.12)',
    border: 'rgba(217,102,39,0.30)',
  },
  charging: {
    label: 'Charging',
    color: '#e8da8d',
    bg: 'rgba(232,218,141,0.12)',
    border: 'rgba(232,218,141,0.30)',
  },
  idle: {
    label: 'Idle',
    color: '#6aa7ad',
    bg: 'rgba(106,167,173,0.10)',
    border: 'rgba(106,167,173,0.25)',
  },
};

const DRONE_COLORS: Record<string, string> = {
  drone_1: '#38bdf8',
  drone_2: '#f472b6',
  drone_3: '#facc15',
  drone_4: '#a78bfa',
  drone_5: '#fb923c',
};

function droneAccent(id: string): string {
  return DRONE_COLORS[id] ?? '#6aa7ad';
}

function formatId(id: string): string {
  if (id.startsWith('drone_')) return `Drone #${id.split('_')[1]}`;
  return id;
}

// ── Compact Drone Card ──────────────────────────────────────────────────────

const DroneStatusCard: React.FC<{
  drone: DroneStatus;
}> = ({ drone }) => {
  const cfg = STATUS_CONFIG[drone.status] ?? STATUS_CONFIG.idle;
  const accent = droneAccent(drone.id);
  const batteryColor =
    drone.battery < 20 ? '#d65b34' : drone.battery < 50 ? '#e8da8d' : '#36c55e';

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.25, ease: 'easeOut' }}
      className="rounded-xl border transition-all"
      style={{ background: 'rgba(15,31,31,0.5)', borderColor: 'rgba(65,110,111,0.25)' }}
    >
      <div className="px-4 py-3 space-y-2.5">
        {/* Row 1: ID + Status badge */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div
              className="w-2 h-2 rounded-full shrink-0"
              style={{ background: accent, boxShadow: `0 0 6px ${accent}` }}
            />
            <span className="text-sm font-bold text-white tracking-tight">
              {formatId(drone.id)}
            </span>
          </div>
          <span
            className="text-xs font-bold px-2.5 py-0.5 rounded-full border capitalize"
            style={{ color: cfg.color, background: cfg.bg, borderColor: cfg.border }}
          >
            {cfg.label}
          </span>
        </div>

        {/* Row 2: Battery bar */}
        <div className="flex items-center gap-2.5">
          <Battery size={13} className="text-white/30 shrink-0" />
          <div className="flex-1 h-2 bg-white/5 rounded-full overflow-hidden">
            <motion.div
              className="h-full rounded-full"
              style={{ background: batteryColor }}
              animate={{ width: `${drone.battery}%` }}
              transition={{ duration: 0.4 }}
            />
          </div>
          <span
            className="text-xs font-bold font-mono min-w-[32px] text-right"
            style={{ color: batteryColor }}
          >
            {Math.floor(drone.battery)}%
          </span>
        </div>

        {/* Row 3: Position */}
        <div className="flex items-center justify-between text-xs text-white/40">
          <div className="flex items-center gap-1.5 font-mono">
            <Navigation size={11} className="text-white/20" />
            <span>
              {drone.x.toFixed(1)}, {drone.y.toFixed(1)}
            </span>
          </div>
        </div>
      </div>
    </motion.div>
  );
};

// ── Panel ───────────────────────────────────────────────────────────────────

export const SwarmStatusPanel: React.FC<SwarmStatusPanelProps> = ({
  drones,
  survivors = [],
  selectedSurvivorId = null,
  onSelectSurvivor,
  isConnected = false,
}) => {
  const [isOpen, setIsOpen] = useState(true);
  const [activeTab, setActiveTab] = useState<'DRONES' | 'SURVIVORS'>('DRONES');

  const activeDrones = drones.filter((d) => d.status === 'searching' || d.status === 'returning');
  const idleDrones = drones.filter((d) => d.status === 'idle');
  const foundSurvivors = survivors.filter((s) => s.isRescued);

  const getMockCondition = (id: string) => {
    const severities = ['CRITICAL', 'MODERATE', 'MINOR'] as const;
    const categories = ['Trauma', 'Burns', 'Exposure', 'Unknown'] as const;
    let hash = 0;
    for (let i = 0; i < id.length; i += 1) hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
    const severity = severities[hash % severities.length];
    const category = categories[(hash >>> 8) % categories.length];
    const aid_suggestion =
      severity === 'CRITICAL'
        ? 'Dispatch advanced medical team; prioritize evacuation route.'
        : severity === 'MODERATE'
          ? 'Dispatch ground team with first-aid kit and stretcher readiness.'
          : 'Dispatch support team with water, blankets, and basic assessment.';
    return { severity, category, aid_suggestion };
  };

  return (
    <div className="absolute right-4 bottom-6 top-24 z-20 flex items-end justify-end pointer-events-none">
      <div className="flex items-end h-full pointer-events-auto">

        {/* ── Toggle Tab (Left of Panel) ── */}
        <motion.button
          onClick={() => setIsOpen((p) => !p)}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          title={isOpen ? 'Collapse status panel' : 'Expand status panel'}
          className="relative mr-1.5 mb-4 flex flex-col items-center gap-1.5 px-1.5 py-4 rounded-xl border shadow-xl transition-colors"
          style={{
            background: isOpen ? 'rgba(65,110,111,0.35)' : 'rgba(15,31,31,0.82)',
            backdropFilter: 'blur(14px)',
            WebkitBackdropFilter: 'blur(14px)',
            borderColor: isOpen ? 'rgba(106,167,173,0.45)' : 'rgba(65,110,111,0.28)',
            boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
          }}
        >
          {isOpen ? (
            <ChevronRight size={13} className="text-azure-mid" />
          ) : (
            <ChevronLeft size={13} className="text-azure-mid" />
          )}

          <span
            className="text-[9px] font-bold tracking-[0.2em] text-azure-mid/80"
            style={{ writingMode: 'vertical-rl', textOrientation: 'mixed' }}
          >
            SWARM
          </span>

          <span
            className={`w-1.5 h-1.5 rounded-full ${
              isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'
            }`}
          />
        </motion.button>

        {/* ── Slide-in Panel ── */}
        <AnimatePresence initial={false}>
          {isOpen && (
            <motion.div
              key="swarm-panel"
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 360, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ type: 'spring', stiffness: 280, damping: 30 }}
              className="h-full overflow-hidden"
              style={{ pointerEvents: 'auto' }}
            >
              <div
                className="h-full w-[360px] flex flex-col rounded-2xl border shadow-2xl"
                style={{
                  background: 'rgba(15,31,31,0.88)',
                  backdropFilter: 'blur(18px)',
                  WebkitBackdropFilter: 'blur(18px)',
                  borderColor: 'rgba(65,110,111,0.35)',
                  boxShadow:
                    '0 8px 40px rgba(0,0,0,0.6), inset 0 1px 0 rgba(106,167,173,0.08)',
                }}
              >
                {/* ── Header ── */}
                <div
                  className="flex items-center gap-3 px-4 py-3 border-b shrink-0"
                  style={{ borderColor: 'rgba(65,110,111,0.25)' }}
                >
                  <div className="relative">
                    <Cpu size={18} className="text-azure-mid" />
                    <span
                      className={`absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full ${
                        isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'
                      }`}
                    />
                  </div>

                  <div className="flex-1 min-w-0">
                    <span className="text-[15px] font-semibold text-mint-bg/90 tracking-wide">
                      {activeTab === 'DRONES' ? 'Swarm Status' : 'Survivor Triage'}
                    </span>
                    <div className="flex items-center gap-2 mt-0.5">
                      {isConnected ? (
                        <span className="flex items-center gap-1 text-[13px] text-emerald-400">
                          <Wifi size={11} /> Live
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-[13px] text-red-400">
                          <WifiOff size={11} /> Offline
                        </span>
                      )}
                      <span className="text-[13px] text-white/30">·</span>
                      <span className="text-[13px] text-white/40 font-mono">
                        {activeTab === 'DRONES'
                          ? `${drones.length} drone${drones.length !== 1 ? 's' : ''}`
                          : `${foundSurvivors.length} found`}
                      </span>
                      {activeDrones.length > 0 && (
                        <>
                          <span className="text-[13px] text-white/30">·</span>
                          <span className="text-[13px] font-bold text-emerald-400 font-mono">
                            {activeDrones.length} active
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                <div className="px-3 pt-3">
                  <div className="flex gap-2 p-1 rounded-xl border" style={{ borderColor: 'rgba(65,110,111,0.25)', background: 'rgba(0,0,0,0.15)' }}>
                    <button
                      type="button"
                      onClick={() => setActiveTab('DRONES')}
                      className={`flex-1 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-colors ${
                        activeTab === 'DRONES' ? 'bg-azure-mid text-white' : 'text-white/50 hover:text-white'
                      }`}
                    >
                      Swarm
                    </button>
                    <button
                      type="button"
                      onClick={() => setActiveTab('SURVIVORS')}
                      className={`flex-1 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-colors ${
                        activeTab === 'SURVIVORS' ? 'bg-red-600 text-white' : 'text-white/50 hover:text-white'
                      }`}
                    >
                      Survivors
                    </button>
                  </div>
                </div>

                <div
                  className="flex-1 overflow-y-auto px-3 py-3 flex flex-col gap-2.5 min-h-0"
                  style={{
                    scrollbarWidth: 'thin',
                    scrollbarColor: 'rgba(65,110,111,0.4) transparent',
                  }}
                >
                  {activeTab === 'DRONES' ? (
                    drones.length === 0 ? (
                      <div className="flex flex-col items-center justify-center h-full gap-3 opacity-30">
                        <Cpu size={28} className="text-azure-mid" />
                        <span className="text-sm text-white/50 font-mono">
                          No drones deployed
                        </span>
                      </div>
                    ) : (
                      drones.map((drone) => (
                        <DroneStatusCard
                          key={drone.id}
                          drone={drone}
                        />
                      ))
                    )
                  ) : (
                    foundSurvivors.length === 0 ? (
                      <div className="flex flex-col items-center justify-center h-full gap-3 opacity-30">
                        <span className="text-sm text-white/50 font-mono">
                          No survivors located
                        </span>
                      </div>
                    ) : (
                      foundSurvivors
                        .slice()
                        .sort((a, b) => (a.foundTick ?? Number.MAX_SAFE_INTEGER) - (b.foundTick ?? Number.MAX_SAFE_INTEGER))
                        .map((s) => {
                          const isSelected = selectedSurvivorId === s.id;
                          const condition = getMockCondition(s.id);
                          return (
                            <div
                              key={s.id}
                              className={`group rounded-xl border transition-all cursor-pointer ${
                                isSelected ? 'border-yellow-400/70' : 'border-azure-dark/30'
                              }`}
                              style={{ background: isSelected ? 'rgba(255,255,255,0.06)' : 'rgba(15,31,31,0.5)' }}
                              onClick={() => onSelectSurvivor?.(isSelected ? null : s.id)}
                            >
                              <div className="px-4 py-3 space-y-2">
                                <div className="flex items-center justify-between">
                                  <span className="text-sm font-bold text-white tracking-tight">
                                    Target {s.id}
                                  </span>
                                  <span className="text-[11px] text-white/40 font-mono">
                                    Found @ Tick {s.foundTick ?? '—'}
                                  </span>
                                </div>
                                <div className="text-xs text-white/60 font-mono">
                                  Coords: [{s.x.toFixed(1)}, {s.y.toFixed(1)}]
                                </div>
                                <div className={`mt-2 rounded-lg border px-3 py-2 text-xs ${
                                  isSelected ? 'block' : 'hidden group-hover:block'
                                }`}
                                style={{ borderColor: 'rgba(255,255,255,0.08)', background: 'rgba(0,0,0,0.25)' }}
                                >
                                  <div className="flex items-center justify-between">
                                    <span className="font-bold text-red-300">Severity: {condition.severity}</span>
                                    <span className="text-white/50">Injury: {condition.category}</span>
                                  </div>
                                  <div className="mt-1 text-white/60 italic">
                                    Action: {condition.aid_suggestion}
                                  </div>
                                </div>
                              </div>
                            </div>
                          );
                        })
                    )
                  )}
                </div>

                {/* Empty strip space */}
                <div className="px-4 py-2.5 border-t shrink-0 flex items-center justify-end" style={{ borderColor: 'rgba(65,110,111,0.25)' }}>
                    <span className="text-xs text-white/25 font-mono">
                      {activeTab === 'DRONES' ? `${idleDrones.length} idle` : 'Hover for triage details'}
                    </span>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};
