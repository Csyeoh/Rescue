/**
 * sceneDataAdapters.ts
 *
 * Pure transformation functions: raw app state → deck.gl layer data DTOs.
 * No deck.gl imports here — this is plain business logic so it stays testable
 * and decoupled from the rendering engine.
 */

import { EnvironmentState, SurvivorPoint, ThermalZone } from '../types';
import { clusterTiles, traceBoundaryPaths } from '../utils/polygon-utils';

// ---------------------------------------------------------------------------
// Shared polygon builder
// ---------------------------------------------------------------------------

interface TileCoord { x: number; y: number }
interface ElevatedTileCoord extends TileCoord { elevation: number }

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
  const tiles: ElevatedTileCoord[] = (env?.obstacles || [])
    .filter(o => isGodMode || o.discovered)
    .map(o => ({ x: Math.floor(o.x), y: Math.floor(o.y), elevation: typeof o.height === 'number' ? o.height : 1.2 }));
  return tilesToSmoothedPolygonsByElevation(tiles, false, env?.survivors || []);
}

// ---------------------------------------------------------------------------
// Survivors
// ---------------------------------------------------------------------------

export function envToSurvivors(env: EnvironmentState): SurvivorPoint[] {
  return (env?.survivors || []).map(s => {
    const z = 0.05;
    return {
      id: s.id,
      position: [s.x + 0.5, s.y + 0.5, z] as [number, number, number],
      rescued: Boolean(s.isRescued),
      foundTick: s.foundTick ?? null,
    };
  });
}

// ---------------------------------------------------------------------------
// Thermal scans
// ---------------------------------------------------------------------------

export function envToThermalPolygons(env: EnvironmentState): ThermalZone[] {
  return (env?.thermalScans || []).map((t, idx) => {
    const coords: number[][] = [[t.cx, t.cy, 1.1]];
    const startAngle = t.angle - t.arc / 2;
    const endAngle = t.angle + t.arc / 2;
    const segments = 16; 
    
    for (let i = 0; i <= segments; i++) {
        const rayAngle = startAngle + (i / segments) * t.arc;
        const rad = (rayAngle * Math.PI) / 180;
        const x = t.cx + Math.sin(rad) * t.radius;
        const y = t.cy + Math.cos(rad) * t.radius;
        coords.push([x, y, 1.1]);
    }
    
    coords.push([t.cx, t.cy, 1.1]);
    return {
      id: `thermal-${idx}`,
      polygon: coords,
      createdAt: t.createdAt || Date.now()
    };
  });
}

export type { BuildingPoly };
function tilesToSmoothedPolygonsByElevation(
  tiles: ElevatedTileCoord[],
  isSolid: boolean,
  survivors: { x: number, y: number, isRescued: boolean }[] = []
): BuildingPoly[] {
  if (tiles.length === 0) return [];
  const buckets = new Map<number, TileCoord[]>();
  for (const t of tiles) {
    const key = Math.round(t.elevation * 10) / 10;
    const list = buckets.get(key) ?? [];
    list.push({ x: t.x, y: t.y });
    buckets.set(key, list);
  }

  const polys: BuildingPoly[] = [];
  for (const [elevation, bucketTiles] of buckets.entries()) {
    const clusters = clusterTiles(bucketTiles);
    for (let i = 0; i < clusters.length; i += 1) {
      const cluster = clusters[i];
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

      polys.push({ 
        id: `poly-${isSolid ? 'b' : 'o'}-${elevation}-${i}`, 
        polygon: loops, 
        elevation, 
        isSolid,
        survivorCount: clusterSurvivors.length,
        foundCount: clusterSurvivors.filter(s => s.isRescued).length,
        center: [cx + 0.5, cy + 0.5]
      });
    }
  }
  return polys;
}

// ---------------------------------------------------------------------------
// Buildings
// ---------------------------------------------------------------------------

export function envToBuildings(env: EnvironmentState): BuildingPoly[] {
  const tiles: ElevatedTileCoord[] = (env?.buildings || []).map(b => ({
    x: Math.floor(b.x),
    y: Math.floor(b.y),
    elevation: typeof b.height === 'number' ? b.height : 1.5,
  }));
  return tilesToSmoothedPolygonsByElevation(tiles, true, env?.survivors || []);
}
