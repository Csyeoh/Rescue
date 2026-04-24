import { SolidPolygonLayer } from '@deck.gl/layers';
import { COORDINATE_SYSTEM } from '@deck.gl/core';

/**
 * createBaseLayer
 * Renders the central drone base station as an extruded 3D solid landing pad.
 */
export function createBaseLayer({ 
  color, 
  line, 
  bases = [{ x: 9, y: 9 }] // Default location if none provided
}: { 
  color: number[], 
  line: number[], 
  bases?: { x: number, y: number }[] 
}) {
  const segments = 32;
  const radius = 0.6; // Slightly larger for better visibility
  
  const baseData = bases.map((b, idx) => {
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
  });

  return new SolidPolygonLayer({
    id: 'base-station',
    pickable: true,
    coordinateSystem: COORDINATE_SYSTEM.CARTESIAN,
    data: baseData,
    getPolygon: (d: any) => d.polygon,
    getFillColor: color as any,
    getElevation: 0.2,
    extruded: true,
    stroked: true,
    getLineColor: line as any,
    lineWidthMinPixels: 2,
  });
}