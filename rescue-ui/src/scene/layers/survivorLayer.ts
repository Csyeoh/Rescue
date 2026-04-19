import { ScenegraphLayer } from '@deck.gl/mesh-layers';
import { COORDINATE_SYSTEM } from '@deck.gl/core';
import { SurvivorPoint } from '../../types';

/**
 * createSurvivorLayer
 *
 * Renders survivors using the 3D model placed at public/models/survivor.glb.
 * Differentiates states with color (orange for waiting, cyan for rescued).
 */
export function createSurvivorLayer(data: SurvivorPoint[], theme: { rescued: number[], waiting: number[] }) {
  return new ScenegraphLayer({
    id: 'survivors',
    pickable: true,
    coordinateSystem: COORDINATE_SYSTEM.CARTESIAN,
    data,
    scenegraph: '/models/survivor.glb',
    getPosition: (d: SurvivorPoint) => d.position,
    // Adjust base orientation of survivor model if needed:
    getOrientation: [0, 90, 180],
    getColor: (d: SurvivorPoint) =>
      d.rescued
        ? theme.rescued as any   // Rescued: Grass Green
        : theme.waiting as any,  // Waiting: Neon Orange
    sizeScale: 1.2,
    _lighting: 'pbr',
    _animations: {
    '*': { speed: 1.0, playing: true } // Plays all animations in the GLB at 1x speed
    }
  });
}
