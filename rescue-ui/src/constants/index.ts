import { DisasterType } from "../types";

export const GRID_SIZE = 20;
export const BASE_X = 9;
export const BASE_Y = 9;

export const API_BASE: string = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
export const WS_BASE = API_BASE.startsWith('https://')
  ? API_BASE.replace('https://', 'wss://')
  : API_BASE.replace('http://', 'ws://');
export const WS_URL = `${WS_BASE}/ws`;

// Elevation Color Maps (Darker = Lower, Lighter = Higher)
export const TERRAIN_COLORS: Record<DisasterType, Record<number, string>> = {
  default: {
    1: '#53a560', 2: '#59bc66', 3: '#5fc36d',
    4: '#65ca73', 5: '#6bd17a', 6: '#71d880',
    7: '#77df87', 8: '#7de68d', 9: '#7fff94',
  },
  typhoon: {
    1: '#53a560', 2: '#59bc66', 3: '#5fc36d',
    4: '#65ca73', 5: '#6bd17a', 6: '#71d880',
    7: '#77df87', 8: '#7de68d', 9: '#7fff94',
  },
  earthquake: {
    1: '#53a560', 2: '#59bc66', 3: '#5fc36d',
    4: '#65ca73', 5: '#6bd17a', 6: '#71d880',
    7: '#77df87', 8: '#7de68d', 9: '#7fff94',
  },
  tsunami: {
    1: '#53a560', 2: '#59bc66', 3: '#5fc36d',
    4: '#65ca73', 5: '#6bd17a', 6: '#71d880',
    7: '#77df87', 8: '#7de68d', 9: '#7fff94',
  },
  fire: {
    1: '#53a560', 2: '#59bc66', 3: '#5fc36d',
    4: '#65ca73', 5: '#6bd17a', 6: '#71d880',
    7: '#77df87', 8: '#7de68d', 9: '#7fff94',
  },
  flash_flood: {
    1: '#53a560', 2: '#59bc66', 3: '#5fc36d',
    4: '#65ca73', 5: '#6bd17a', 6: '#71d880',
    7: '#77df87', 8: '#7de68d', 9: '#7fff94',
  }
};

export const BUILDING_COLORS = {
  light: '#ff8a8a', // Single-story
  dark: '#b30000',  // Multi-story
};
