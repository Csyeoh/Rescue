'use client';

import { SolidPolygonLayer } from '@deck.gl/layers';
import { COORDINATE_SYSTEM } from '@deck.gl/core';
import { CoverageCell } from '../../types';

/**
 * createCoverageLayer
 * 
 * Renders the "Revealed" ground areas where drones have explored.
 * Uses a grid of 0.5-unit tiles tinted with azure-mid.
 */
export function createCoverageLayer(cells: CoverageCell[] = []) {
  return new SolidPolygonLayer({
    id: 'coverage-grid',
    coordinateSystem: COORDINATE_SYSTEM.CARTESIAN,
    data: cells,
    getPolygon: (d: CoverageCell) => {
      const x1 = d.x * 0.5;
      const y1 = d.y * 0.5;
      const x2 = x1 + 0.5;
      const y2 = y1 + 0.5;
      const z = 0.01; // Slightly above ground plane
      return [
        [x1, y1, z],
        [x2, y1, z],
        [x2, y2, z],
        [x1, y2, z]
      ];
    },
    getFillColor: [106, 167, 173, 40], // azure-mid with 40/255 transparency (~15%)
    extruded: false,
    pickable: false,
    updateTriggers: {
      getPolygon: [cells.length]
    }
  });
}
