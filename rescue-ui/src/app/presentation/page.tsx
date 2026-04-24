"use client";

import React, { useCallback, useMemo, useState } from "react";
import { motion } from "motion/react";
import DeckGLContainer from "../../components/Map/DeckGLContainer";
import SurvivorMic from "../../components/UI/SurvivorMic";
import { usePlaybackViewer } from "../../hooks/usePlaybackViewer";
import { Header } from "../../components/Layout/Header";
import { LogPanel } from "../../components/Layout/LogPanel";
import { SwarmStatusPanel } from "../../components/Layout/SwarmStatusPanel";
import { DroneStatus, EnvironmentState, LogEntry } from "../../types";

function normalizeDroneStatus(status: string): DroneStatus["status"] {
  const s = String(status || "").toUpperCase();
  if (s === "RETURNING") return "returning";
  if (s === "CHARGING") return "charging";
  if (s === "IDLE") return "idle";
  if (s === "TRIAGE_HOLD") return "idle";
  return "searching";
}

export default function PresentationPage() {
  const [showCoords, setShowCoords] = useState(false);
  const [isNightMode, setIsNightMode] = useState(false);
  const [showXRay, setShowXRay] = useState(false);
  const [selectedSurvivorId, setSelectedSurvivorId] = useState<string | null>(null);
  const [survivorIntel, setSurvivorIntel] = useState<Record<string, any>>({});
  const [logStartIndex, setLogStartIndex] = useState(0);

  const {
    playbackData,
    currentIndex,
    isPlaying,
    triageDroneId,
    setIsPlaying,
    setCurrentIndex,
    resolveTriage,
  } = usePlaybackViewer();

  const current = playbackData[currentIndex];
  const terrainSource = useMemo(() => playbackData.find((t) => t?.buildings || t?.obstacles || t?.bases), [playbackData]);
  const totalSurvivors = useMemo(() => {
    const first = playbackData[0];
    return first?.survivors?.length ?? 0;
  }, [playbackData]);

  const environmentState: EnvironmentState = useMemo(() => {
    const buildings = (terrainSource?.buildings ?? []).map((b) => ({
      x: Number(b.x),
      y: Number(b.y),
      revealed: false,
      height: b.height !== undefined && b.height !== null ? Number(b.height) : undefined,
    }));
    const obstacles = (terrainSource?.obstacles ?? []).map((o) => ({
      x: Number(o.x),
      y: Number(o.y),
      discovered: false,
      height: o.height !== undefined && o.height !== null ? Number(o.height) : undefined,
    }));
    const bases = (terrainSource?.bases ?? [{ x: 9, y: 9 }]).map((b) => ({ x: Number(b.x), y: Number(b.y) }));
    const survivors = (current?.survivors ?? []).map((s) => ({
      id: String(s.id),
      x: Number(s.x),
      y: Number(s.y),
      isRescued: Boolean(s.found),
      foundTick: null,
    }));

    return {
      buildings,
      obstacles,
      survivors,
      thermalScans: [],
      bases,
      sectors: [],
    };
  }, [current?.survivors, terrainSource?.bases, terrainSource?.buildings, terrainSource?.obstacles]);

  const drones: DroneStatus[] = useMemo(() => {
    const ds = current?.drones ?? [];
    return ds.map((d) => ({
      id: String(d.id),
      x: Number(d.x),
      y: Number(d.y),
      z: 0.5,
      battery: Number(d.battery),
      status: normalizeDroneStatus(d.status),
      stepsTaken: 0,
      trail: [],
    }));
  }, [current?.drones]);

  const coverage = useMemo(() => {
    const cells = current?.coverage ?? [];
    return cells.map((c) => ({ x: Number(c[0]), y: Number(c[1]) }));
  }, [current?.coverage]);

  const triageDrone = useMemo(() => {
    if (!triageDroneId || !current) return null;
    return current.drones.find((d) => d.id === triageDroneId) ?? null;
  }, [current, triageDroneId]);

  const triageSurvivorId = useMemo(() => {
    if (!triageDrone || !current) return null;
    const found = current.survivors.filter((s) => s.found);
    if (found.length === 0) return null;
    let best: { id: string; dist: number } | null = null;
    for (const s of found) {
      const dx = Number(s.x) - Number(triageDrone.x);
      const dy = Number(s.y) - Number(triageDrone.y);
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (!best || dist < best.dist) best = { id: String(s.id), dist };
    }
    return best ? String(best.id) : null;
  }, [current, triageDrone]);

  const canScrubForward = triageDroneId === null;
  const maxIndex = Math.max(0, playbackData.length - 1);

  const isConnected = playbackData.length > 0;
  const revealedCells = coverage.length;
  const survivorsDetected = environmentState.survivors.filter((s) => s.isRescued).length;

  const logs: LogEntry[] = useMemo(() => {
    if (!playbackData.length) return [];
    const start = Math.max(0, Math.min(logStartIndex, currentIndex));
    const slice = playbackData.slice(start, currentIndex + 1);
    const out: LogEntry[] = [];
    for (const tickObj of slice) {
      const t = tickObj.tick;
      const items = tickObj.logs ?? [];
      for (let i = 0; i < items.length; i += 1) {
        const raw = String(items[i] ?? "");
        const after = raw.includes("] ") ? raw.split("] ").slice(1).join("] ") : raw;
        const firstWord = after.trim().split(/\s+/)[0] ?? "";
        const agent = firstWord.startsWith("drone_") ? firstWord : "SYSTEM";
        out.push({
          id: `t${t}-${i}`,
          timestamp: `T+${t}`,
          tick: t,
          agent,
          message: raw,
          type: "info",
        });
      }
    }
    return out;
  }, [currentIndex, logStartIndex, playbackData]);

  const clearLogs = useCallback(() => {
    setLogStartIndex(currentIndex);
  }, [currentIndex]);

  const downloadLogsAsText = useCallback(() => {
    const lines = logs.map((l) => `[${l.timestamp}] [tick ${l.tick ?? "?"}] ${l.agent}: ${l.message}`);
    const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "presentation_logs.txt";
    a.click();
    URL.revokeObjectURL(url);
  }, [logs]);

  return (
    <div className="h-screen w-screen overflow-hidden relative bg-[#0f1f1f]">
      <div className="absolute inset-0 z-0">
        <DeckGLContainer
          environmentState={environmentState}
          drones={drones}
          coverage={coverage}
          mode="god"
          showCoords={showCoords}
          isNightMode={isNightMode}
          showXRay={showXRay}
          showSectors={false}
          selectedSurvivorId={selectedSurvivorId}
        />
      </div>

      <motion.div
        key="dashboard"
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 1.02 }}
        transition={{ duration: 0.4, ease: "circOut" }}
        className="absolute inset-0 z-10 p-4 flex flex-col gap-4 pointer-events-none"
      >
        <div className="pointer-events-auto flex justify-center relative">
          <Header
            revealedCells={revealedCells}
            survivorsDetected={survivorsDetected}
            totalSurvivors={totalSurvivors}
            isSimulationRunning={isPlaying}
            isAborting={false}
            isMapGenerated={playbackData.length > 0}
            onToggleSimulation={() => setIsPlaying(!isPlaying)}
            tickCount={current?.tick ?? 0}
          />

          <div className="absolute top-0 right-0 z-20 flex flex-col gap-2 bg-neutral-dark/80 backdrop-blur-md p-3 rounded-xl border border-azure-dark/30 shadow-2xl pointer-events-auto">
            <label className="flex items-center gap-3 cursor-pointer group">
              <div className="relative">
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={isNightMode}
                  onChange={(e) => setIsNightMode(e.target.checked)}
                />
                <div
                  className={`block w-10 h-6 rounded-full transition-colors ${
                    isNightMode ? "bg-azure-mid" : "bg-neutral-dark border border-azure-dark/50"
                  }`}
                />
                <div
                  className={`absolute left-1 top-1 bg-mint-bg w-4 h-4 rounded-full transition-transform ${
                    isNightMode ? "translate-x-4" : ""
                  }`}
                />
              </div>
              <span className="text-[11px] font-bold text-mint-bg uppercase tracking-wider group-hover:text-azure-mid transition-colors">
                Night Ops
              </span>
            </label>

            <label className="flex items-center gap-3 cursor-pointer group">
              <div className="relative">
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={showCoords}
                  onChange={(e) => setShowCoords(e.target.checked)}
                />
                <div
                  className={`block w-10 h-6 rounded-full transition-colors ${
                    showCoords ? "bg-azure-mid" : "bg-neutral-dark border border-azure-dark/50"
                  }`}
                />
                <div
                  className={`absolute left-1 top-1 bg-mint-bg w-4 h-4 rounded-full transition-transform ${
                    showCoords ? "translate-x-4" : ""
                  }`}
                />
              </div>
              <span className="text-[11px] font-bold text-mint-bg uppercase tracking-wider group-hover:text-azure-mid transition-colors">
                Show Coords
              </span>
            </label>

            <label className="flex items-center gap-3 cursor-pointer group">
              <div className="relative">
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={showXRay}
                  onChange={(e) => setShowXRay(e.target.checked)}
                />
                <div
                  className={`block w-10 h-6 rounded-full transition-colors ${
                    showXRay ? "bg-alert-orange" : "bg-neutral-dark border border-azure-dark/50"
                  }`}
                />
                <div
                  className={`absolute left-1 top-1 bg-mint-bg w-4 h-4 rounded-full transition-transform ${
                    showXRay ? "translate-x-4" : ""
                  }`}
                />
              </div>
              <span className="text-[11px] font-bold text-mint-bg uppercase tracking-wider group-hover:text-azure-mid transition-colors">
                View Through
              </span>
            </label>
          </div>
        </div>

        <LogPanel logs={logs} onClear={clearLogs} onDownload={downloadLogsAsText} isConnected={isConnected} />

        <div className="absolute bottom-6 left-16 pointer-events-auto bg-neutral-dark/80 backdrop-blur-md p-3 rounded-xl border border-azure-dark/30 shadow-2xl min-w-[160px]">
          <h3 className="text-[10px] font-bold text-azure-mid uppercase tracking-[0.2em] mb-3 border-b border-azure-dark/20 pb-1">
            Tactical Legend
          </h3>

          <div className="flex flex-col gap-2.5">
            <div className="flex items-center gap-3">
              <div
                className={`w-3.5 h-3.5 rounded-sm border ${
                  isNightMode ? "bg-[#e8da8d] border-[#e8da8d]/50" : "bg-[#41ab5d] border-[#238b45]/50"
                }`}
              />
              <span className="text-[11px] font-medium text-mint-bg/90">Building</span>
            </div>

            <div className="flex items-center gap-3">
              <div
                className={`w-3.5 h-3.5 rounded-sm border ${
                  isNightMode ? "bg-[#ff3030] border-[#ff3030]/50" : "bg-[#ef4444] border-[#b91c1c]/50"
                }`}
              />
              <span className="text-[11px] font-medium text-mint-bg/90">Obstacle</span>
            </div>

            <div className="flex items-center gap-3 mt-1 pt-2 border-t border-azure-dark/10">
              <div className="w-3.5 h-3.5 rounded-full bg-[#36c55e] shadow-[0_0_8px_#36c55e]" />
              <span className="text-[11px] font-medium text-mint-bg/90">Survivor (Found)</span>
            </div>

            <div className="flex items-center gap-3">
              <div className="w-3.5 h-3.5 rounded-full bg-[#ff7e00] shadow-[0_0_8px_#ff7e00]" />
              <span className="text-[11px] font-medium text-mint-bg/90">Survivor (Searching)</span>
            </div>
          </div>
        </div>

        {triageDroneId && triageSurvivorId !== null && (
          <SurvivorMic
            droneId={triageDroneId}
            survivorId={triageSurvivorId}
            onIntelReceived={(data) => {
              const intel = data?.intel;
              setSurvivorIntel((prev) => ({
                ...prev,
                [String(triageSurvivorId)]: intel,
              }));
            }}
            onResolve={resolveTriage}
          />
        )}

        <SwarmStatusPanel
          drones={drones}
          survivors={environmentState.survivors}
          selectedSurvivorId={selectedSurvivorId}
          onSelectSurvivor={setSelectedSurvivorId}
          isConnected={isConnected}
          survivorIntel={survivorIntel}
        />

        <div className="absolute left-0 right-0 bottom-0 z-20 pointer-events-auto p-4">
          <div className="mx-auto max-w-4xl rounded-2xl border border-slate-800 bg-slate-950/70 backdrop-blur-md px-4 py-3">
            <div className="flex items-center gap-4">
              <button
                type="button"
                onClick={() => setIsPlaying(!isPlaying)}
                disabled={triageDroneId !== null || playbackData.length === 0}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-white text-sm font-semibold disabled:opacity-50"
              >
                {isPlaying ? "Pause" : "Play"}
              </button>

              <div className="text-sm text-slate-200 font-mono">
                Tick: {current?.tick ?? 0}
                {triageDroneId ? ` | TRIAGE HOLD: ${triageDroneId}` : ""}
              </div>

              <input
                type="range"
                min={0}
                max={maxIndex}
                value={currentIndex}
                onChange={(e) => {
                  const next = Number(e.target.value);
                  if (!canScrubForward && next > currentIndex) return;
                  setCurrentIndex(next);
                }}
                className="flex-1"
                disabled={playbackData.length === 0}
              />

              <div className="text-xs text-slate-400 font-mono w-[70px] text-right">
                {currentIndex}/{maxIndex}
              </div>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
