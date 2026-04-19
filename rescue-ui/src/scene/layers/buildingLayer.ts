import { SolidPolygonLayer } from '@deck.gl/layers';
import { COORDINATE_SYSTEM } from '@deck.gl/core';
import { BuildingPoly } from '../sceneDataAdapters';

/**
 * createBuildingLayer
 *
 * Renders extruded 3D building volumes using Chaikin-smoothed polygon outlines.
 * Includes 'View Through' (X-Ray) and hover transparency logic.
 */
export function createBuildingLayer(
  data: BuildingPoly[], 
  hoveredId: string | null, 
  theme: { building: number[], buildingHover: number[], line: number[] },
  viewThroughActive: boolean = false
) {
  const baseAlpha = viewThroughActive ? 70 : 255;
  const hoverAlpha = 40;

  return new SolidPolygonLayer({
    id: 'buildings',
    coordinateSystem: COORDINATE_SYSTEM.CARTESIAN,
    data,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    getPolygon: (d: BuildingPoly) => d.polygon as any,
    pickable: true,
    getFillColor: (d: BuildingPoly) => {
      const isHovered = d.id === hoveredId;
      const alpha = isHovered ? (viewThroughActive ? hoverAlpha : 100) : baseAlpha;
      return [...theme.building.slice(0, 3), alpha] as any;
    },
    getLineColor: theme.line as any,
    getElevation: (d: BuildingPoly) => d.elevation,
    extruded: true,
    lineWidthMinPixels: 1,
    updateTriggers: {
      getFillColor: [hoveredId, viewThroughActive],
    },
    material: {
      ambient: 0.3,
      diffuse: 0.65,
      shininess: 48,
      specularColor: [80, 110, 140] as unknown as [number, number, number],
    },
    transitions: {
      getElevation: 100, 
      getFillColor: 100  
    },
  });
}
