import { useEffect, useRef } from 'react';
import { WS_URL, GRID_SIZE, BASE_X, BASE_Y } from '../constants';
import { DroneStatus, GridCell, LogEntry } from '../types';
import { buildGridFromMapData } from '../utils/map-utils';

interface WebSocketHookProps {
  isSimulationRunning: boolean;
  revealedCells: number;
  setIsSimulationRunning: (val: boolean) => void;
  setDrones: (update: (prev: DroneStatus[]) => DroneStatus[]) => void;
  setGrid: (update: (prev: GridCell[][]) => GridCell[][]) => void;
  setSurvivorsFound: (val: number) => void;
  setSurvivorsDetected: (val: number) => void;
  setRevealedCells: (val: number) => void;
  addLog: (agent: string, message: string, type?: LogEntry['type'], details?: LogEntry['details']) => void;
  discoveredRef: React.MutableRefObject<Set<string>>;
  seenLogsRef: React.MutableRefObject<Set<string>>;
}

export const useWebSocket = ({
  isSimulationRunning,
  revealedCells,
  setIsSimulationRunning,
  setDrones,
  setGrid,
  setSurvivorsFound,
  setSurvivorsDetected,
  setRevealedCells,
  addLog,
  discoveredRef,
  seenLogsRef
}: WebSocketHookProps) => {
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      addLog('SYSTEM', 'WebSocket connected.', 'success');
    };
    ws.onerror = () => {
      addLog('SYSTEM', 'WebSocket error.', 'error');
    };
    ws.onclose = () => {
      addLog('SYSTEM', 'WebSocket closed.', 'warning');
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'partitioning_start') {
          addLog('SYSTEM', msg.payload?.message ?? 'Partitioning started.', 'info');
          return;
        }

        if (msg.type === 'partitioning_complete') {
          const payload = msg.payload ?? {};
          if (payload?.terrain) {
            const map_data = { cells: payload.terrain, survivors: payload.survivors ?? [] };
            setGrid(() => buildGridFromMapData(map_data));
          }
          if (Array.isArray(payload?.drones)) {
            setDrones(() => payload.drones.map((d: any) => ({
              id: String(d.id),
              x: Number(d.x),
              y: Number(d.y),
              battery: Number(d.battery ?? 100),
              status: String(d.status ?? '').toUpperCase() === 'RETURNING' ? 'returning'
                : String(d.status ?? '').toUpperCase() === 'CHARGING' ? 'charging'
                  : String(d.status ?? '').toUpperCase() === 'IDLE' ? 'idle'
                    : 'patrolling',
              stepsTaken: 0,
            })));
          }
          addLog('SYSTEM', 'Partitioning complete. Mission running.', 'success');
          return;
        }

        if (msg.type === 'agent_reasoning_completed') {
          const payload = msg.payload ?? {};
          addLog(payload.agent_role || 'AGENT', `Created a plan:`, 'info', {
            type: 'reasoning',
            plan: payload.plan,
            task_id: payload.task_id,
            ready: payload.ready
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
            execution_duration_ms: payload.execution_duration_ms
          });
          return;
        }

        if (msg.type === 'tick_update') {
          const payload = msg.payload ?? {};
          const drone_states = Array.isArray(payload.drones) ? payload.drones : [];
          const map_updates = Array.isArray(payload.terrain) ? payload.terrain : [];
          const agent_logs = Array.isArray(payload.logs) ? payload.logs : [];
          const survivors = Array.isArray(payload.survivors) ? payload.survivors : [];

          if (isSimulationRunning && drone_states.length === 0 && revealedCells > 10) {
            setIsSimulationRunning(false);
          }

          setDrones((prev) => {
            const prevById = new Map<string, DroneStatus>(prev.map((d) => [d.id, d] as [string, DroneStatus]));
            return drone_states.map((ds: any) => {
              const id = String(ds.id);
              const prevD = prevById.get(id);
              return {
                id,
                x: Number(ds.x),
                y: Number(ds.y),
                battery: Number(ds.battery ?? prevD?.battery ?? 100),
                status: String(ds.status ?? '').toUpperCase() === 'RETURNING' ? 'returning'
                  : String(ds.status ?? '').toUpperCase() === 'CHARGING' ? 'charging'
                    : String(ds.status ?? '').toUpperCase() === 'IDLE' ? 'idle'
                      : 'patrolling',
                stepsTaken: (prevD?.stepsTaken ?? 0) + 1,
              };
            });
          });

          setGrid((prevGrid) => {
            if (!prevGrid?.length) return prevGrid;
            const next = prevGrid.map(row => row.map(cell => ({ ...cell, isIlluminated: false, isThermalScanned: false })));

            for (const upd of map_updates) {
              const x = Number(upd.x);
              const y = Number(upd.y);
              if (!(x >= 0 && x < GRID_SIZE && y >= 0 && y < GRID_SIZE)) continue;
              const cell = next[y][x];
              
              // Preserve 'base' type for the base station coordinate
              if (x === BASE_X && y === BASE_Y) {
                cell.type = 'base';
              } else {
                cell.type = upd.is_obstacle ? 'obstacle' : (upd.terrain_type === 'building' ? 'building' : 'empty');
              }
              
              cell.obstacleDiscovered = Boolean(upd.obstacle_discovered);
              cell.revealed = Boolean(upd.revealed);
              
              if (cell.revealed) {
                discoveredRef.current.add(`${x},${y}`);
              }
            }

            const thermalScans = Array.isArray(payload.thermal_scans) ? payload.thermal_scans : [];
            for (const scanXY of thermalScans) {
              const x = Number(scanXY.x);
              const y = Number(scanXY.y);
              if (x >= 0 && x < GRID_SIZE && y >= 0 && y < GRID_SIZE) {
                next[y][x].isThermalScanned = true;
              }
            }

            for (const s of survivors) {
              const x = Number(s.x);
              const y = Number(s.y);
              if (!(x >= 0 && x < GRID_SIZE && y >= 0 && y < GRID_SIZE)) continue;
              const cell = next[y][x];
              cell.hasSurvivor = true;
              cell.isRescued = Boolean(s.discovered);
            }

            for (const ds of drone_states) {
              const x = Number(ds.x);
              const y = Number(ds.y);
              const coords = [[x, y], [x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]];
              for (const [cx, cy] of coords) {
                if (cx >= 0 && cx < GRID_SIZE && cy >= 0 && cy < GRID_SIZE) {
                  next[cy][cx].isIlluminated = true;
                }
              }
            }

            const rescued = next.flat().filter(c => c.isRescued).length;
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
             content += `[Action]\n`;
             content += `Tool: ${tool}\n`;
             content += `Tool Input: ${typeof tool_input === 'object' ? JSON.stringify(tool_input, null, 2) : tool_input}\n`;
             content += `Log: ${log}\n`;
          } else if (log) {
             content += `[Action]\n${log}\n`;
          }

          if (observation) {
            content += `\n[Observation]\n`;
            if (typeof observation === 'string') {
              const obsLines = observation.split('\n');
              obsLines.forEach((line: string) => {
                if (line.startsWith('Title: ')) content += `Title: ${line.slice(7)}\n`;
                else if (line.startsWith('Link: ')) content += `Link: ${line.slice(6)}\n`;
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
        console.error("WS message error:", e);
        addLog('SYSTEM', 'WS message parse error.', 'warning');
      }
    };

    return () => {
      ws.close();
    };
  }, [isSimulationRunning, revealedCells, setIsSimulationRunning, setDrones, setGrid, setSurvivorsFound, setSurvivorsDetected, setRevealedCells, addLog, discoveredRef, seenLogsRef]);

  return wsRef;
};
