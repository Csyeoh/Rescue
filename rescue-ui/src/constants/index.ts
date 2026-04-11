import { DisasterType } from "../types";

export const GRID_SIZE = 20;
export const BASE_X = 9;
export const BASE_Y = 9;

export const API_BASE: string = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
export const WS_BASE = API_BASE.startsWith('https://')
  ? API_BASE.replace('https://', 'wss://')
  : API_BASE.replace('http://', 'ws://');
export const WS_URL = `${WS_BASE}/ws`;

// Terrain Colors
export const TERRAIN_COLORS: Record<DisasterType, Record<number, string>> = {
  default: {
    1: '#53a560', 2: '#53a560', 3: '#53a560',
    4: '#53a560', 5: '#53a560', 6: '#53a560',
    7: '#53a560', 8: '#53a560', 9: '#53a560',
  },
  typhoon: {
    1: '#53a560', 2: '#53a560', 3: '#53a560',
    4: '#53a560', 5: '#53a560', 6: '#53a560',
    7: '#53a560', 8: '#53a560', 9: '#53a560',
  },
  earthquake: {
    1: '#53a560', 2: '#53a560', 3: '#53a560',
    4: '#53a560', 5: '#53a560', 6: '#53a560',
    7: '#53a560', 8: '#53a560', 9: '#53a560',
  },
  tsunami: {
    1: '#53a560', 2: '#53a560', 3: '#53a560',
    4: '#53a560', 5: '#53a560', 6: '#53a560',
    7: '#53a560', 8: '#53a560', 9: '#53a560',
  },
  fire: {
    1: '#53a560', 2: '#53a560', 3: '#53a560',
    4: '#53a560', 5: '#53a560', 6: '#53a560',
    7: '#53a560', 8: '#53a560', 9: '#53a560',
  },
  flash_flood: {
    1: '#53a560', 2: '#53a560', 3: '#53a560',
    4: '#53a560', 5: '#53a560', 6: '#53a560',
    7: '#53a560', 8: '#53a560', 9: '#53a560',
  }
};

export const BUILDING_COLORS = {
  light: '#ff8a8a',
};
