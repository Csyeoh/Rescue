import { ScatterplotLayer } from '@deck.gl/layers';
import { COORDINATE_SYSTEM } from '@deck.gl/core';
import { DroneStatus } from '../../types';

/**
 * createDroneFallbackLayer
 *
 * Renders drones as bright status-colored dots. Always active as a fallback
 * so drone positions are visible even when the GLB model isn't loaded yet.
 * The ScenegraphLayer will render on top of these once the model loads.
 */
export function createDroneFallbackLayer(drones: DroneStatus[]) {
  return new ScatterplotLayer({
    id: 'drones-fallback',
    coordinateSystem: COORDINATE_SYSTEM.CARTESIAN,
    data: drones,
    getPosition: (d: DroneStatus) => [d.x, d.y, 1.5] as [number, number, number],
    getFillColor: (d: DroneStatus) => {
      if (d.status === 'charging')  return [34, 211, 238, 230]  as [number, number, number, number];
      if (d.status === 'returning') return [245, 158, 11, 230]  as [number, number, number, number];
      if (d.status === 'idle')      return [148, 163, 184, 180] as [number, number, number, number];
      return [96, 165, 250, 255] as [number, number, number, number]; // patrolling: blue
    },
    getRadius: 0.7,
    radiusUnits: 'common',
    stroked: true,
    getLineColor: [255, 255, 255, 60] as [number, number, number, number],
    lineWidthMinPixels: 1,
    pickable: true,
    transitions: {
      getPosition: { duration: 1000 },
    },
  });
}
