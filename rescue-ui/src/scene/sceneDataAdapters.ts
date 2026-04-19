/**
 * sceneDataAdapters.ts
 *
 * Pure transformation functions: raw app state → deck.gl layer data DTOs.
 * No deck.gl imports here — this is plain business logic so it stays testable
 * and decoupled from the rendering engine.
 */

import { EnvironmentState, SurvivorPoint } from '../types';
import { clusterTiles, traceBoundaryPaths } from '../utils/polygon-utils';

// ---------------------------------------------------------------------------
// Shared polygon builder
// ---------------------------------------------------------------------------

interface TileCoord { x: number; y: number }

interface BuildingPoly {
  id: string;
  polygon: number[][][];
  elevation: number;
  isSolid: boolean; // true = building, false = obstacle
  survivorCount: number;
  foundCount: number;
  center: [number, number]; // for location display
}



// ---------------------------------------------------------------------------
// Obstacles
// ---------------------------------------------------------------------------

export function envToObstacles(env: EnvironmentState, isGodMode: boolean): BuildingPoly[] {
  const tiles = (env?.obstacles || [])
    .filter(o => isGodMode || o.discovered)
    .map(o => ({ x: Math.floor(o.x), y: Math.floor(o.y) }));
  return tilesToSmoothedPolygons(tiles, 1.2, false, env?.survivors || []);
}

// ---------------------------------------------------------------------------
// Survivors
// ---------------------------------------------------------------------------

export function envToSurvivors(env: EnvironmentState): SurvivorPoint[] {
  return (env?.survivors || []).map(s => {
    const z = 0.05;
    return {
      position: [s.x + 0.5, s.y + 0.5, z] as [number, number, number],
      rescued: Boolean(s.isRescued),
    };
  });
}

// ---------------------------------------------------------------------------
// Thermal scans
// ---------------------------------------------------------------------------

export function envToThermalPoints(env: EnvironmentState): { position: [number, number, number] }[] {
  return (env?.thermalScans || []).map(t => ({
    position: [Math.floor(t.x) + 0.5, Math.floor(t.y) + 0.5, 0.05] as [number, number, number],
  }));
}

export type { BuildingPoly };
function tilesToSmoothedPolygons(
  tiles: TileCoord[],
  elevation: number,
  isSolid: boolean,
  survivors: { x: number, y: number, isRescued: boolean }[] = []
): BuildingPoly[] {
  if (tiles.length === 0) return [];
  const clusters = clusterTiles(tiles);
  return clusters.map((cluster: TileCoord[], i: number) => {
    const loops: number[][][] = traceBoundaryPaths(cluster).map((loop: TileCoord[]) =>
      loop.map((p: TileCoord) => [p.x, p.y]),
    );

    // Calculate metadata for tooltips
    const clusterTilesSet = new Set(cluster.map(t => `${Math.floor(t.x)},${Math.floor(t.y)}`));
    const clusterSurvivors = survivors.filter(s => 
      clusterTilesSet.has(`${Math.floor(s.x)},${Math.floor(s.y)}`)
    );
    
    // Centroid for tooltip location
    const cx = cluster.reduce((sum, t) => sum + t.x, 0) / cluster.length;
    const cy = cluster.reduce((sum, t) => sum + t.y, 0) / cluster.length;

    return { 
      id: `poly-${isSolid ? 'b' : 'o'}-${i}`, 
      polygon: loops, 
      elevation, 
      isSolid,
      survivorCount: clusterSurvivors.length,
      foundCount: clusterSurvivors.filter(s => s.isRescued).length,
      center: [cx + 0.5, cy + 0.5]
    };
  });
}

// ---------------------------------------------------------------------------
// Buildings
// ---------------------------------------------------------------------------

export function envToBuildings(env: EnvironmentState): BuildingPoly[] {
  const tiles = (env?.buildings || []).map(b => ({ x: Math.floor(b.x), y: Math.floor(b.y) }));
  return tilesToSmoothedPolygons(tiles, 1.5, true, env?.survivors || []);
}