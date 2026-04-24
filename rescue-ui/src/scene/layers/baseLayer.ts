import { SolidPolygonLayer } from '@deck.gl/layers';
import { COORDINATE_SYSTEM } from '@deck.gl/core';

/**
 * createBaseLayer
 *
 * Renders the central drone base station as an extruded 3D solid landing pad.
 * Located at the center of the 20×20 world (9,9 to 10,10 coordinates).
 */
export function createBaseLayer(bases: {x: number, y: number}[], theme: { color: number[], line: number[] }) {
  // Generate a circular polygon with 32 segments for smoothness
  const segments = 32;
  const radius = 0.5;
  
  const baseData = bases && bases.length > 0 ? bases.map((b, idx) => {
    const circlePoints = [];
    const centerX = b.x + 0.5;
    const centerY = b.y + 0.5;
    for (let i = 0; i < segments; i++) {
        const angle = (i / segments) * Math.PI * 2;
        circlePoints.push([
        centerX + Math.cos(angle) * radius,
        centerY + Math.sin(angle) * radius
        ]);
    }
    return { id: `base-${idx}`, polygon: circlePoints, x: centerX, y: centerY };
  }) : [];

  return new SolidPolygonLayer({
    id: 'base-station',
    pickable: true,
    coordinateSystem: COORDINATE_SYSTEM.CARTESIAN,
    data: baseData,
    getPolygon: (d: any) => d.polygon,
    getFillColor: theme.color as any, // Cyan/Blue futuristic pad
    getElevation: 0.2,                 // Slightly raised above ground
    extruded: true,
    stroked: true,
    getLineColor: theme.line as any, // Bright border ring
    lineWidthMinPixels: 2,
    material: {
      ambient: 0.5,
      diffuse: 0.8,
      shininess: 64,
    },
  });
}
