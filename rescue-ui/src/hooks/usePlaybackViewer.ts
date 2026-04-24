"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export type PlaybackDrone = {
  id: string;
  x: number;
  y: number;
  battery: number;
  status: string;
  thermal_memory: unknown[];
  task_queue: unknown[];
};

export type PlaybackSurvivor = {
  id: string;
  x: number;
  y: number;
  found: boolean;
};

export type PlaybackTick = {
  tick: number;
  drones: PlaybackDrone[];
  survivors: PlaybackSurvivor[];
  coverage: [number, number][];
  logs: string[];
  buildings?: { x: number; y: number; height?: number }[];
  obstacles?: { x: number; y: number; height?: number }[];
  bases?: { x: number; y: number }[];
};

type HookState = {
  playbackData: PlaybackTick[];
  currentIndex: number;
  isPlaying: boolean;
  triageDroneId: string | null;
  setIsPlaying: (v: boolean) => void;
  setCurrentIndex: (idx: number) => void;
  nextTick: () => void;
  prevTick: () => void;
  resolveTriage: () => void;
};

export function usePlaybackViewer(): HookState {
  const [playbackData, setPlaybackData] = useState<PlaybackTick[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [triageDroneId, setTriageDroneId] = useState<string | null>(null);

  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    let isMounted = true;
    fetch("/playback_data.json", { cache: "no-store" })
      .then((r) => r.json())
      .then((data) => {
        if (!isMounted) return;
        if (Array.isArray(data)) setPlaybackData(data as PlaybackTick[]);
      })
      .catch(() => {
        if (!isMounted) return;
        setPlaybackData([]);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const maxIndex = useMemo(() => Math.max(0, playbackData.length - 1), [playbackData.length]);

  const canAdvance = useMemo(() => triageDroneId === null, [triageDroneId]);

  const findTriageTransition = useCallback(
    (fromIdx: number, toIdx: number) => {
      if (toIdx <= fromIdx) return null;
      for (let i = fromIdx + 1; i <= toIdx; i += 1) {
        const prev = playbackData[i - 1];
        const next = playbackData[i];
        if (!next) continue;
        const held = next.drones.find((d) => String(d.status).toUpperCase() === "TRIAGE_HOLD");
        if (!held) continue;
        const prevDrone = prev?.drones?.find((d) => d.id === held.id);
        const prevHeld = prevDrone ? String(prevDrone.status).toUpperCase() === "TRIAGE_HOLD" : false;
        if (!prevHeld) return { idx: i, droneId: held.id };
      }
      return null;
    },
    [playbackData],
  );

  const nextTick = useCallback(() => {
    if (!canAdvance) return;
    setCurrentIndex((prev) => {
      const nextIdx = Math.min(maxIndex, prev + 1);
      if (nextIdx === prev) return prev;
      const triage = findTriageTransition(prev, nextIdx);
      if (triage) {
        setIsPlaying(false);
        setTriageDroneId(triage.droneId);
        return triage.idx;
      }
      return nextIdx;
    });
  }, [canAdvance, findTriageTransition, maxIndex]);

  const prevTick = useCallback(() => {
    setCurrentIndex((prev) => Math.max(0, prev - 1));
  }, []);

  const resolveTriage = useCallback(() => {
    setTriageDroneId(null);
    setIsPlaying(true);
  }, []);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") {
        e.preventDefault();
        nextTick();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        prevTick();
      } else if (e.key === " ") {
        e.preventDefault();
        setIsPlaying((p) => !p);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [nextTick, prevTick]);

  useEffect(() => {
    if (intervalRef.current) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (!isPlaying) return;
    intervalRef.current = window.setInterval(() => {
      nextTick();
    }, 500);
    return () => {
      if (intervalRef.current) window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    };
  }, [isPlaying, nextTick]);

  const setCurrentIndexSafe = useCallback(
    (idx: number) => {
      const clamped = Math.max(0, Math.min(maxIndex, idx));
      if (!canAdvance && clamped > currentIndex) return;
      if (clamped > currentIndex) {
        const triage = findTriageTransition(currentIndex, clamped);
        if (triage) {
          setIsPlaying(false);
          setTriageDroneId(triage.droneId);
          setCurrentIndex(triage.idx);
          return;
        }
      }
      setCurrentIndex(clamped);
    },
    [canAdvance, currentIndex, findTriageTransition, maxIndex],
  );

  const setIsPlayingSafe = useCallback(
    (v: boolean) => {
      if (triageDroneId && v) return;
      setIsPlaying(v);
    },
    [triageDroneId],
  );

  return {
    playbackData,
    currentIndex,
    isPlaying,
    triageDroneId,
    setIsPlaying: setIsPlayingSafe,
    setCurrentIndex: setCurrentIndexSafe,
    nextTick,
    prevTick,
    resolveTriage,
  };
}
