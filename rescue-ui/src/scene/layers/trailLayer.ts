import { PathLayer } from '@deck.gl/layers';
import { COORDINATE_SYSTEM } from '@deck.gl/core';
import { DroneStatus } from '../../types';

/**
 * createTrailLayer
 *
 * Draws fading flight trails behind each drone using a ring-buffered history
 * of positions stored on the DroneStatus object (populated in useWebSocket).
 *
 * Aesthetics: low-opacity glowing cyan line at constant 1.5-unit altitude.
 */
export function createTrailLayer(drones: DroneStatus[]) {
  const dronesWithTrails = drones.filter(
    d => d.trail && d.trail.length >= 2,
  );

  return new PathLayer({
    id: 'trails',
    coordinateSystem: COORDINATE_SYSTEM.CARTESIAN,
    data: dronesWithTrails,
    getPath: (d: DroneStatus) => d.trail!,
    getColor: (d: DroneStatus) => {
      // Match trail color to drone status
      if (d.status === 'charging')  return [34, 211, 238, 70]  as [number, number, number, number];
      if (d.status === 'returning') return [245, 158, 11, 70]  as [number, number, number, number];
      return [100, 200, 255, 70] as [number, number, number, number];
    },
    getWidth: 0.06,
    widthUnits: 'common',
    capRounded: true,
    jointRounded: true,
    billboard: false,
  });
}
