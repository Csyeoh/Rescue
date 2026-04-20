import { SolidPolygonLayer } from '@deck.gl/layers';
import { COORDINATE_SYSTEM } from '@deck.gl/core';
import { ThermalZone } from '../../types';


/**
 * createThermalLayer
 *
 * Radial radar-sweep fan where drones have recently scanned.
 * Fades out over 4s and oscillates vertically ("Up-Down" scanning).
 */
export function createThermalLayer(data: ThermalZone[], time: number) {
  const now = Date.now();
  
  return new SolidPolygonLayer({
    id: 'thermal',
    coordinateSystem: COORDINATE_SYSTEM.CARTESIAN,
    data,
    // Up-down vertical "slicing" oscillation
    getPolygon: (d: ThermalZone) => {
      const zOffset = Math.cos(time * 0.08) * 0.15; 
      return d.polygon.map(p => [p[0], p[1], p[2] + zOffset]) as any;
    },
    // Transparency and Lifecycle Fading
    getFillColor: (d: ThermalZone) => {
      const ageMs = now - d.createdAt;
      const lifeSpan = 5000; 
      
      // Stay opaque for the first 2.5 seconds, then fade rapidly in the last 1.5s
      const holdTime = 2500;
      const fadeOut = ageMs < holdTime 
        ? 1 
        : Math.max(0, 1 - (ageMs - holdTime) / (lifeSpan - holdTime));
      
      // Subtle pulsing after creation
      const pulse = 0.85 + Math.sin(time * 0.1) * 0.15;
      const alpha = Math.floor(100 * fadeOut * pulse); // Increased from 60 to 100
      
      return [239, 68, 68, alpha] as [number, number, number, number];
    },
    // Ensure deck.gl re-renders the properties when 'time' changes
    updateTriggers: {
      getPolygon: [time],
      getFillColor: [time, now]
    },
    transitions: {
      getFillColor: 600 // Smooth appearance
    },
    extruded: false,
    pickable: false,
  });
}
