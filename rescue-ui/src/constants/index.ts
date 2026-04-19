export const GRID_SIZE = 20;
export const BASE_X = 9;
export const BASE_Y = 9;

export const API_BASE: string = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
export const WS_BASE = API_BASE.startsWith('https://')
  ? API_BASE.replace('https://', 'wss://')
  : API_BASE.replace('http://', 'ws://');
export const WS_URL = `${WS_BASE}/ws`;