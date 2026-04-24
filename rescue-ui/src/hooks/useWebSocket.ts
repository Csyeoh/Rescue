import { useEffect, useRef, useCallback } from 'react';
import { WS_URL } from '../constants';
import { DroneStatus, EnvironmentState, LogEntry } from '../types';

interface WebSocketHookProps {
  /** When true the hook opens the WS; when it flips false the connection is closed. */
  shouldConnect: boolean;
  isSimulationRunning: boolean;
  revealedCells: number;
  setIsSimulationRunning: (val: boolean) => void;
  setDrones: (update: (prev: DroneStatus[]) => DroneStatus[]) => void;
  setEnvironmentState: React.Dispatch<React.SetStateAction<EnvironmentState>>;
  setSurvivorsFound: (val: number) => void;
  setSurvivorsDetected: (val: number) => void;
  setRevealedCells: (val: number | ((prev: number) => number)) => void;
  setTickCount: (val: number) => void;
  setMissionReport: (report: any | null) => void;
  setCoverage: (val: {x: number, y: number}[] | ((prev: {x: number, y: number}[]) => {x: number, y: number}[])) => void;
  addLog: (agent: string, message: string, type?: LogEntry['type'], details?: LogEntry['details'], tick?: number) => void;
  discoveredRef: React.MutableRefObject<Set<string>>;
  seenLogsRef: React.MutableRefObject<Set<string>>;
}

export const useWebSocket = (props: WebSocketHookProps) => {
  const wsRef = useRef<WebSocket | null>(null);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const propsRef = useRef(props);
  useEffect(() => {
    propsRef.current = props;
  }, [props]);

  // ── Stable connect function stored in a ref ───────────────────────────────
  const connectRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    // When the connect signal flips off, tear down everything and bail.
    if (!props.shouldConnect) {
      // Clear any pending retry
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }
      const existing = wsRef.current;
      if (
        existing &&
        (existing.readyState === WebSocket.OPEN ||
          existing.readyState === WebSocket.CONNECTING)
      ) {
        existing.onclose = null;
        existing.close();
      }
      wsRef.current = null;
      connectRef.current = null;
      return;
    }

    // ── Build the connect function ──────────────────────────────────────────
    let isMounted = true;

    const connect = () => {
      // Guard: don't open a second socket if one is already live
      if (
        wsRef.current &&
        (wsRef.current.readyState === WebSocket.OPEN ||
          wsRef.current.readyState === WebSocket.CONNECTING)
      ) {
        return;
      }

      console.log('[WS] Connecting to', WS_URL);
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMounted) return;
        console.log('[WS] Connected');
        propsRef.current.addLog('SYSTEM', 'WebSocket connected — live telemetry active.', 'success');
      };

      ws.onerror = () => {
        // onerror is always followed by onclose — we handle retry there.
        if (!isMounted) return;
        console.error('[WS] Connection error');
      };

      ws.onclose = (event) => {
        if (!isMounted) return;
        wsRef.current = null;

        // Only log + retry if we're still supposed to be connected
        if (propsRef.current.shouldConnect) {
          const reason = event.wasClean
            ? `Connection closed (code ${event.code}).`
            : 'Connection lost — retrying…';
          propsRef.current.addLog('SYSTEM', reason, 'warning');

          // Retry after a short delay
          retryTimerRef.current = setTimeout(() => {
            if (isMounted && propsRef.current.shouldConnect) {
              console.log('[WS] Retrying connection…');
              connect();
            }
          }, 1500);
        }
      };

      ws.onmessage = (event) => {
        if (!isMounted) return;
        const {
          isSimulationRunning,
          revealedCells,
          setIsSimulationRunning,
          setDrones,
          setEnvironmentState,
          setSurvivorsFound,
          setSurvivorsDetected,
          setRevealedCells,
          setTickCount,
          setCoverage,
          addLog,
          discoveredRef,
          seenLogsRef,
        } = propsRef.current;

        try {
          const msg = JSON.parse(event.data);

          if (msg.type === 'ping') return;

          if (msg.type === 'partitioning_start') {
            addLog('SYSTEM', msg.payload?.message ?? 'Partitioning started.', 'info');
            return;
          }

          // ── Agent Reasoning ──────────────────────────────────────────────
          if (msg.type === 'agent_reasoning') {
            const payload = msg.payload ?? {};
            addLog(payload.agent || 'AGENT', payload.summary || 'Reasoning…', 'reasoning', {
              type: 'reasoning',
              thought: payload.thought || '',
            });
            return;
          }

          // ── Tool Call ──────────────────────────────────────────────────────
          if (msg.type === 'tool_call') {
            const payload = msg.payload ?? {};
            const args = payload.tool_args ?? {};
            const hasArgs = Object.keys(args).length > 0;
            const argsDisplay = hasArgs
              ? Object.entries(args).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(', ')
              : 'no arguments needed';
            addLog(payload.agent || 'AGENT', `${payload.tool_name}`, 'tool_call', {
              type: 'tool_call',
              tool_name: payload.tool_name,
              tool_args: args,
            });
            return;
          }

          // ── Tool Response ──────────────────────────────────────────────────
          if (msg.type === 'tool_response') {
            const payload = msg.payload ?? {};
            addLog(payload.agent || 'AGENT', payload.tool_name || 'Done.', 'tool_response', {
              type: 'tool_response',
              tool_name: payload.tool_name,
              result_message: payload.result_message,
            });
            return;
          }

          // ── Dispatcher-only update (statuses + sectors) ───────────────────
          if (msg.type === 'dispatcher_update') {
            const payload = msg.payload ?? {};
            const drone_states = Array.isArray(payload.drones) ? payload.drones : [];

            // Update drone statuses ONLY (not positions/battery — those come from tick_update)
            if (drone_states.length > 0) {
              setDrones((prev) => {
                const updated = prev.map((d) => {
                  const update = drone_states.find((ds: any) => String(ds.id) === d.id);
                  if (update) {
                    const rawStatus = String(update.status ?? '').toUpperCase();
                    const status: typeof d.status =
                      rawStatus === 'RETURNING'  ? 'returning'
                      : rawStatus === 'IDLE'     ? 'idle'
                      : 'searching';
                    return { ...d, status };
                  }
                  return d;
                });
                return updated.sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true }));
              });
            }

            addLog('SYSTEM', `Dispatcher push received.`, 'info');
            return;
          }

          if (msg.type === 'thermal_scan_event') {
            const payload = msg.payload ?? {};
            setEnvironmentState((prev) => ({
              ...prev,
              thermalScans: [
                ...prev.thermalScans,
                { 
                  cx: Number(payload.cx),
                  cy: Number(payload.cy),
                  angle: Number(payload.angle),
                  arc: Number(payload.arc),
                  radius: Number(payload.radius),
                  createdAt: Date.now() 
                }
              ],
            }));
            return;
          }

          if (msg.type === 'coverage_update') {
            const payload = msg.payload ?? {};
            const cellPairs = Array.isArray(payload.cells) ? payload.cells : [];
            if (cellPairs.length > 0) {
              const formattedCells = cellPairs.map((c: any) => ({ x: c[0], y: c[1] }));
              setCoverage(formattedCells);
              setRevealedCells(formattedCells.length);
            }
            return;
          }

          if (msg.type === 'tick_update') {
            const payload = msg.payload ?? {};
            const tick = Number(payload.tick ?? 0);
            if (tick > 0) setTickCount(tick);
            
            const drone_states  = Array.isArray(payload.drones)        ? payload.drones        : [];
            const obstacle_upds = Array.isArray(payload.obstacles)     ? payload.obstacles     : [];
            const building_upds = Array.isArray(payload.buildings)     ? payload.buildings     : [];
            const agent_logs    = Array.isArray(payload.logs)          ? payload.logs          : [];
            const survivors     = Array.isArray(payload.survivors)     ? payload.survivors     : [];

            if (isSimulationRunning && drone_states.length === 0 && revealedCells > 10) {
              setIsSimulationRunning(false);
            }

            setDrones((prev) => {
              const prevById = new Map<string, DroneStatus>(
                prev.map((d) => [d.id, d] as [string, DroneStatus])
              );
              
              const sortedStates = [...drone_states].sort((a: any, b: any) => 
                String(a.id).localeCompare(String(b.id), undefined, { numeric: true })
              );

              return sortedStates.map((ds: any) => {
                const id = String(ds.id);
                const prevD = prevById.get(id);

                const newX = Number(ds.x);

                const newY = Number(ds.y);
                const prevX = prevD?.x ?? newX;
                const prevY = prevD?.y ?? newY;

                const dx = newX - prevX;
                const dy = newY - prevY;
                const dist = Math.sqrt(dx * dx + dy * dy);

                // Fix velocity and heading logic for continuous space
                // Velocity is fixed to 1.0 if the drone moved, to ensure consistent visual tilt
                const velocityMag = dist > 0.01 ? 1.0 : 0.0;
                // Preserve the previous heading if the drone is stationary
                const heading = dist > 0.01 ? Math.atan2(dy, dx) * (180 / Math.PI) : (prevD?.heading ?? 0);

                const prevTrail: [number, number, number][] = prevD?.trail ?? [];
                const trail: [number, number, number][] = [
                  ...prevTrail.slice(-19),
                  [prevX, prevY, 1.5],
                ];

                const status: DroneStatus['status'] =
                  String(ds.status ?? '').toUpperCase() === 'RETURNING' ? 'returning'
                  : String(ds.status ?? '').toUpperCase() === 'IDLE'     ? 'idle'
                  : 'searching';

                return {
                  id,
                  x: newX,
                  y: newY,
                  battery: Number(ds.battery ?? prevD?.battery ?? 100),
                  status,
                  stepsTaken: (prevD?.stepsTaken ?? 0) + 1,
                  heading,
                  velocityMag,
                  trail,
                };
              });
            });

            setEnvironmentState((prevState) => {
              if (!prevState) return prevState;
              const next: EnvironmentState = { ...prevState };

              const newObstacles = [...prevState.obstacles];
              for (const upd of obstacle_upds) {
                const x = Math.floor(Number(upd.x));
                const y = Math.floor(Number(upd.y));
                const idx = newObstacles.findIndex(o => o.x === x && o.y === y);
                if (idx >= 0) newObstacles[idx] = { ...newObstacles[idx], discovered: Boolean(upd.discovered) };
                else newObstacles.push({ x, y, discovered: Boolean(upd.discovered) });
              }
              next.obstacles = newObstacles;

              const newBuildings = [...prevState.buildings];
              for (const upd of building_upds) {
                const x = Math.floor(Number(upd.x));
                const y = Math.floor(Number(upd.y));
                const idx = newBuildings.findIndex(b => b.x === x && b.y === y);
                if (idx >= 0) newBuildings[idx] = { ...newBuildings[idx], revealed: Boolean(upd.revealed) };
                else newBuildings.push({ x, y, revealed: Boolean(upd.revealed) });
                if (upd.revealed) discoveredRef.current.add(`${x},${y}`);
              }
              next.buildings = newBuildings;

              const newSurvivors = [...prevState.survivors];
              for (const s of survivors) {
                const id = String(s.id ?? '');
                const x = Math.floor(Number(s.x));
                const y = Math.floor(Number(s.y));
                const foundTick = s.found_tick !== undefined && s.found_tick !== null ? Number(s.found_tick) : null;
                const resolvedId = id || `survivor_${x}_${y}`;
                const idx = newSurvivors.findIndex(surv => surv.id === resolvedId);
                if (idx >= 0) newSurvivors[idx] = { ...newSurvivors[idx], x, y, isRescued: Boolean(s.discovered), foundTick };
                else newSurvivors.push({ id: resolvedId, x, y, isRescued: Boolean(s.discovered), foundTick });
              }
              next.survivors = newSurvivors;

              const rescued = next.survivors.filter(c => c.isRescued).length;
              setSurvivorsFound(rescued);
              setSurvivorsDetected(rescued);
              setRevealedCells(discoveredRef.current.size);
              return next;
            });

            for (const l of agent_logs) {
              const agent = l?.drone_id ? String(l.drone_id) : 'AGENT';
              const message = l?.message ? String(l.message) : JSON.stringify(l);
              const tick = l?.tick !== undefined ? Number(l.tick) : undefined;
              const time = l?.timestamp ? String(l.timestamp) : '';
              const logKey = `${agent}|${tick}|${time}|${message}`;
              if (!seenLogsRef.current.has(logKey)) {
                seenLogsRef.current.add(logKey);
                addLog(agent, message, 'info', undefined, tick);
              }
            }
            return;
          }

          if (msg.type === 'agent_step') {
            const { agent, tool, tool_input, log, observation } = msg.payload ?? {};
            let content = '';

            if (tool && tool_input && log) {
              content += `[Action]\nTool: ${tool}\nTool Input: ${
                typeof tool_input === 'object' ? JSON.stringify(tool_input, null, 2) : tool_input
              }\nLog: ${log}\n`;
            } else if (log) {
              content += `[Action]\n${log}\n`;
            }

            if (observation) {
              content += `\n[Observation]\n`;
              if (typeof observation === 'string') {
                observation.split('\n').forEach((line: string) => {
                  if (line.startsWith('Title: '))    content += `Title: ${line.slice(7)}\n`;
                  else if (line.startsWith('Link: '))    content += `Link: ${line.slice(6)}\n`;
                  else if (line.startsWith('Snippet: ')) content += `Snippet: ${line.slice(9)}\n`;
                  else content += `${line}\n`;
                });
              } else {
                content += `${observation}\n`;
              }
            }

            addLog(agent || 'AGENT', content.trim(), 'info');
            return;
          }

          if (msg.type === 'mission_complete') {
            addLog('SYSTEM', msg.payload?.message ?? 'Mission complete.', 'success');
            setIsSimulationRunning(false);
            return;
          }
          
          if (msg.type === 'mission_failed') {
            addLog('SYSTEM', msg.payload?.message ?? 'Mission failed.', 'error');
            setIsSimulationRunning(false);
            return;
          }

          if (msg.type === 'MISSION_REPORT') {
          addLog('SYSTEM', 'Post-Mission Telemetry Report generated.', 'success');
          propsRef.current.setMissionReport(msg.payload);
          return;
        }
        
        } catch (e: any) {
          console.error('WS message error:', e);
          addLog('SYSTEM', `WS Error: ${e.message || 'Unknown error'}`, 'warning');
        }
      };
    };

    connectRef.current = connect;

    // Kick off the first connection attempt
    connect();

    // Cleanup: runs when shouldConnect flips false OR on unmount
    return () => {
      isMounted = false;
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }
      const ws = wsRef.current;
      if (
        ws &&
        (ws.readyState === WebSocket.OPEN ||
          ws.readyState === WebSocket.CONNECTING)
      ) {
        ws.onclose = null;
        ws.close();
      }
      wsRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.shouldConnect]);

  return wsRef;
};
