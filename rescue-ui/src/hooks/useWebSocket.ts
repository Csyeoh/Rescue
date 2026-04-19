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
  setRevealedCells: (val: number) => void;
  addLog: (agent: string, message: string, type?: LogEntry['type'], details?: LogEntry['details']) => void;
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

          if (msg.type === 'agent_reasoning_completed') {
            const payload = msg.payload ?? {};
            addLog(payload.agent_role || 'AGENT', `Created a plan:`, 'info', {
              type: 'reasoning',
              plan: payload.plan,
              task_id: payload.task_id,
              ready: payload.ready,
            });
            return;
          }

          if (msg.type === 'mcp_tool_execution_completed') {
            const payload = msg.payload ?? {};
            addLog('SYSTEM', `Tool execution completed: ${payload.tool_name}`, 'success', {
              type: 'tool_execution',
              tool_name: payload.tool_name,
              tool_args: payload.tool_args,
              result: payload.result,
              execution_duration_ms: payload.execution_duration_ms,
            });
            return;
          }

          // ── Dispatcher-only update (statuses + sectors) ───────────────────
          if (msg.type === 'dispatcher_update') {
            const payload = msg.payload ?? {};
            const drone_states = Array.isArray(payload.drones) ? payload.drones : [];
            const sectorData  = Array.isArray(payload.sectors) ? payload.sectors : [];

            // Update drone statuses ONLY (not positions/battery — those come from tick_update)
            if (drone_states.length > 0) {
              setDrones((prev) =>
                prev.map((d) => {
                  const update = drone_states.find((ds: any) => String(ds.id) === d.id);
                  if (update) {
                    const rawStatus = String(update.status ?? '').toUpperCase();
                    const status: typeof d.status =
                      rawStatus === 'RETURNING'  ? 'returning'
                      : rawStatus === 'CHARGING' ? 'charging'
                      : rawStatus === 'IDLE'     ? 'idle'
                      : 'searching'; // SEARCHING maps to patrolling
                    return { ...d, status };
                  }
                  return d;
                })
              );
            }

            // Update sectors (overwrites the whole array — sectors are transient)
            setEnvironmentState((prev) => ({
              ...prev,
              sectors: sectorData.map((s: any) => ({
                drone_id: String(s.drone_id),
                cx: Number(s.cx),
                cy: Number(s.cy),
                radius: Number(s.radius),
              })),
            }));

            addLog('SYSTEM', `Dispatcher update: ${sectorData.length} sector(s) assigned.`, 'info');
            return;
          }

          if (msg.type === 'tick_update') {
            const payload = msg.payload ?? {};
            const drone_states  = Array.isArray(payload.drones)        ? payload.drones        : [];
            const obstacle_upds = Array.isArray(payload.obstacles)     ? payload.obstacles     : [];
            const building_upds = Array.isArray(payload.buildings)     ? payload.buildings     : [];
            const agent_logs    = Array.isArray(payload.logs)          ? payload.logs          : [];
            const survivors     = Array.isArray(payload.survivors)     ? payload.survivors     : [];
            const thermalScans  = Array.isArray(payload.thermal_scans) ? payload.thermal_scans : [];

            if (isSimulationRunning && drone_states.length === 0 && revealedCells > 10) {
              setIsSimulationRunning(false);
            }

            setDrones((prev) => {
              const prevById = new Map<string, DroneStatus>(
                prev.map((d) => [d.id, d] as [string, DroneStatus])
              );
              return drone_states.map((ds: any) => {
                const id = String(ds.id);
                const prevD = prevById.get(id);

                const newX = Number(ds.x);
                const newY = Number(ds.y);
                const prevX = prevD?.x ?? newX;
                const prevY = prevD?.y ?? newY;

                const dx = newX - prevX;
                const dy = newY - prevY;
                const heading = Math.atan2(dy, dx) * (180 / Math.PI);
                const velocityMag = Math.sqrt(dx * dx + dy * dy);

                const prevTrail: [number, number, number][] = prevD?.trail ?? [];
                const trail: [number, number, number][] = [
                  ...prevTrail.slice(-19),
                  [prevX, prevY, 1.5],
                ];

                const status: DroneStatus['status'] =
                  String(ds.status ?? '').toUpperCase() === 'RETURNING' ? 'returning'
                  : String(ds.status ?? '').toUpperCase() === 'CHARGING' ? 'charging'
                  : String(ds.status ?? '').toUpperCase() === 'IDLE'     ? 'idle'
                  : 'patrolling';

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
                const x = Math.floor(Number(s.x));
                const y = Math.floor(Number(s.y));
                const idx = newSurvivors.findIndex(surv => surv.x === x && surv.y === y);
                if (idx >= 0) newSurvivors[idx] = { ...newSurvivors[idx], isRescued: Boolean(s.discovered) };
                else newSurvivors.push({ x, y, isRescued: Boolean(s.discovered) });
              }
              next.survivors = newSurvivors;

              next.thermalScans = thermalScans.map((scanXY: any) => ({
                x: Number(scanXY.x),
                y: Number(scanXY.y),
              }));

              next.sectors = payload.sectors
                ? payload.sectors.map((s: any) => ({
                    drone_id: String(s.drone_id),
                    cx: Number(s.cx),
                    cy: Number(s.cy),
                    radius: Number(s.radius),
                  }))
                : [];

              const rescued = next.survivors.filter(c => c.isRescued).length;
              setSurvivorsFound(rescued);
              setSurvivorsDetected(rescued);
              setRevealedCells(discoveredRef.current.size);
              return next;
            });

            for (const l of agent_logs) {
              const agent = l?.drone_id ? String(l.drone_id) : 'AGENT';
              const message = l?.message ? String(l.message) : JSON.stringify(l);
              const time = l?.timestamp ? String(l.timestamp) : '';
              const logKey = `${agent}|${time}|${message}`;
              if (!seenLogsRef.current.has(logKey)) {
                seenLogsRef.current.add(logKey);
                addLog(agent, message, 'info');
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
        } catch (e) {
          console.error('WS message error:', e);
          addLog('SYSTEM', 'WS message parse error.', 'warning');
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
