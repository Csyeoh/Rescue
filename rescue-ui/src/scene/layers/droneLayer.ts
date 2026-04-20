'use client';

import { ScenegraphLayer } from '@deck.gl/mesh-layers';
import { COORDINATE_SYSTEM } from '@deck.gl/core';
import { DroneStatus } from '../../types';
import { easeLinear } from 'd3-ease';

// ---------------------------------------------------------------------------
// Orientation math
// ---------------------------------------------------------------------------

/**
 * deriveOrientation
 *
 * Returns [pitch, yaw, roll] in degrees for the ScenegraphLayer.
 *
 * - yaw   : heading direction derived from (prevPos → currentPos) movement vector
 * - pitch : slight forward tilt based on velocity magnitude (drones lean into flight)
 * - roll  : always 0 (simplification — bank angle would need angular velocity)
 */
function deriveOrientation(drone: DroneStatus): [number, number, number] {
  const yaw = (drone.heading ?? 0);
  
  // Try 90 or -90 on the ROLL axis
  return [0, yaw, 90]; 
  // OR return [0, yaw, -90];
}
// ---------------------------------------------------------------------------
// Status-based tint color
// ---------------------------------------------------------------------------

function statusColor(status: DroneStatus['status'], theme: { charging: number[], returning: number[], idle: number[], searching: number[] }): [number, number, number] {
  switch (status) {
    case 'charging':  return theme.charging as [number, number, number];
    case 'returning': return theme.returning as [number, number, number];
    case 'idle':      return theme.idle as [number, number, number];
    default:          return theme.searching as [number, number, number];
  }
}

// ---------------------------------------------------------------------------
// Layer factory
// ---------------------------------------------------------------------------

/**
 * createDroneLayer
 *
 * Renders drone agents using a GLTF quadcopter model via ScenegraphLayer.
 * Falls back gracefully if the model file is missing (deck.gl shows nothing
 * rather than crashing, so the rest of the scene still renders).
 *
 * Transitions interpolate positions at 60 FPS even when the backend only
 * sends one tick per second — eliminating the "teleport" effect.
 */
export function createDroneLayer(drones: DroneStatus[], modelUrl: string, theme: any) {
  return new ScenegraphLayer({
    id: 'drones',
    coordinateSystem: COORDINATE_SYSTEM.CARTESIAN,
    data: drones,
    scenegraph: modelUrl,
    getPosition: (d: DroneStatus) => {
      // Sit on the base pad (z=0.2) when idle/charging, otherwise fly high (z=1.5)
      const isGrounded = d.status === 'idle' || d.status === 'charging';
      return [d.x, d.y, isGrounded ? 0.5 : 1.1] as [number, number, number];
    },
    getOrientation: (d: DroneStatus) => deriveOrientation(d),
    getColor: (d: DroneStatus) => statusColor(d.status, theme),
    sizeScale: 0.5,
    _lighting: 'pbr',
    pickable: true,
    transitions: {
      getPosition: {
        duration: 1000,        // match backend tick rate
        easing: easeLinear,    // constant speed (no ease in/out on flight)
      },
      getOrientation: {
        duration: 500,         // faster yaw response
        easing: easeLinear,
      },
    },
  });
}
