import { ScatterplotLayer } from '@deck.gl/layers';
import { COORDINATE_SYSTEM } from '@deck.gl/core';

interface ThermalPoint {
  position: [number, number, number];
}

/**
 * createThermalLayer
 *
 * Translucent red blobs where drones have recently scanned.
 * Clears every tick — gives the impression of active scanning pulses.
 */
export function createThermalLayer(data: ThermalPoint[]) {
  return new ScatterplotLayer({
    id: 'thermal',
    coordinateSystem: COORDINATE_SYSTEM.CARTESIAN,
    data,
    getPosition: (d: ThermalPoint) => d.position,
    getFillColor: [239, 68, 68, 60] as [number, number, number, number],
    getRadius: 0.9,
    radiusUnits: 'common',
    opacity: 0.6,
  });
}
