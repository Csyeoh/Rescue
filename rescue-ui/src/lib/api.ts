import { API_BASE } from "../constants";
import { MissionConfig } from "../types";
import { toBackendConfig } from "../utils/map-utils";

export const resetMissionApi = async () => {
  const response = await fetch(`${API_BASE}/api/reset`, { method: 'POST' });
  if (!response.ok) throw new Error('Failed to reset backend');
  return response.json();
};

export const generateMapApi = async (config: MissionConfig) => {
  const bcfg = toBackendConfig(config);
  const response = await fetch(`${API_BASE}/api/generate_map`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scenario: bcfg.scenario,
      drone_battery: bcfg.drone_battery,
      num_survivors: bcfg.num_survivors,
      obstacle_difficulty: bcfg.obstacle_difficulty,
    }),
  });
  const json = await response.json();
  if (!response.ok || json?.status !== 'success') {
    throw new Error(json?.message || 'Generate map failed');
  }
  return json.map_data;
};

export const startMissionApi = async (config: MissionConfig, mapData: any) => {
  const bcfg = toBackendConfig(config);
  const response = await fetch(`${API_BASE}/api/start_mission`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scenario: bcfg.scenario,
      num_drones: bcfg.num_drones,
      drone_battery: bcfg.drone_battery,
      num_survivors: bcfg.num_survivors,
      obstacle_difficulty: bcfg.obstacle_difficulty,
      map_data: mapData,
    }),
  });
  const json = await response.json();
  if (!response.ok || json?.status !== 'success') {
    throw new Error(json?.message || 'Start mission failed');
  }
  return json;
};

export const abortMissionApi = async () => {
  const response = await fetch(`${API_BASE}/api/abort`, { method: 'POST' });
  if (!response.ok) throw new Error('Abort failed');
  return response.json();
};
