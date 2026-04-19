import { SolidPolygonLayer, LineLayer } from '@deck.gl/layers';
import { COORDINATE_SYSTEM } from '@deck.gl/core';

/**
 * createGroundLayer
 *
 * Renders a large flat plane below the simulation grid as a floor
 * spanning from -2 to 22 (encompassing the 20x20 area).
 * Also renders a Blueprint/CAD style subtle grid on top of it.
 */
export function createGroundLayer(theme: { ground: number[], grid: number[] }) {
  const gridLineData = [];
  // Grid lines from -2 to 22.
  for (let i = -2; i <= 22; i++) {
    // vertical
    gridLineData.push({ start: [i, -2, 0.01], end: [i, 22, 0.01] });
    // horizontal
    gridLineData.push({ start: [-2, i, 0.01], end: [22, i, 0.01] });
  }

  const plane = new SolidPolygonLayer({
    id: 'ground-plane',
    coordinateSystem: COORDINATE_SYSTEM.CARTESIAN,
    data: [{
      polygon: [
        [-2, -2],
        [22, -2],
        [22, 22],
        [-2, 22]
      ]
    }],
    getPolygon: (d: any) => d.polygon,
    // Darker backdrop so the grid pops
    getFillColor: theme.ground as any, 
    extruded: false,                      // Flat plane
    stroked: false,
    material: {
      ambient: 0.2,
      diffuse: 0.5,
      shininess: 12,
    },
  });

  const grid = new LineLayer({
    id: 'ground-grid',
    coordinateSystem: COORDINATE_SYSTEM.CARTESIAN,
    data: gridLineData,
    getSourcePosition: (d: any) => d.start,
    getTargetPosition: (d: any) => d.end,
    getColor: theme.grid as any, // Azure dark faintly glowing
    getWidth: 1.5,
    widthUnits: 'pixels',
  });

  return [plane, grid];
}
