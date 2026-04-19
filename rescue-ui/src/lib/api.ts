import { API_BASE } from "../constants";
import { MissionConfig } from "../types";

export const resetMissionApi = async () => {
  const response = await fetch(`${API_BASE}/api/reset`, { method: 'POST' });
  if (!response.ok) throw new Error('Failed to reset backend');
  return response.json();
};

export const generateMapApi = async () => {
  const response = await fetch(`${API_BASE}/api/generate_map`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  const json = await response.json();
  if (!response.ok || json?.status !== 'success') {
    throw new Error(json?.message || 'Generate map failed');
  }
  return json;
};

export const startMissionApi = async () => {
  const response = await fetch(`${API_BASE}/api/start_mission`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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
