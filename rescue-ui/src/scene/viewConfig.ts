import { OrbitView } from '@deck.gl/core';

// ---------------------------------------------------------------------------
// OrbitView — used instead of MapView because the backend coordinate space
// is a 20×20 abstract Cartesian plane, not GPS coordinates.
// ---------------------------------------------------------------------------

export const ORBIT_VIEW = new OrbitView({
  id: 'orbit',
  controller: {
    scrollZoom: true,
    dragPan: true,
    dragRotate: true,
    doubleClickZoom: true,
    touchZoom: true,
    touchRotate: true,
    keyboard: true,
  },
});

export const INITIAL_VIEW_STATE = {
  // Center camera on the middle of the 20×20 world
  target: [10, 10, 0] as [number, number, number],
  zoom: 3.5,
  // Dramatic angle: looking down from 55° gives big-picture situational awareness
  pitch: 55,
  bearing: -30,
  minZoom: 1,
  maxZoom: 15,
};
