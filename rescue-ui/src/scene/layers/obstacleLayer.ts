import { SolidPolygonLayer } from '@deck.gl/layers';
import { PathStyleExtension } from '@deck.gl/extensions';
import { COORDINATE_SYSTEM } from '@deck.gl/core';
import { BuildingPoly } from '../sceneDataAdapters';

/**
 * createObstacleLayer
 *
 * Low rubble/debris obstacles — darker and shorter than buildings.
 * Includes animated "marching ants" dashed borders.
 */
export function createObstacleLayer(data: BuildingPoly[], time: number = 0, theme: { obstacle: number[], line: number[] }) {
  return new SolidPolygonLayer({
    id: 'obstacles',
    coordinateSystem: COORDINATE_SYSTEM.CARTESIAN,
    data,
    pickable: true,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    getPolygon: (d: BuildingPoly) => d.polygon as any,
    getFillColor: theme.obstacle as any,    // Red alert color
    getLineColor: theme.line as any,
    getElevation: (d: BuildingPoly) => d.elevation,
    extruded: true,
    stroked: true,
    lineWidthMinPixels: 2,

    // Animated "Marching Ants" Dash Effect
    extensions: [new PathStyleExtension({ dash: true })],
    getLineDashArray: [10, 5],
    dashJustified: true,
    dashOffset: time / 30, // Drives the animation speed

    material: {
      ambient: 0.6,
      diffuse: 0.9,
      shininess: 8,
    },
    updateTriggers: {
      dashOffset: time
    }
  });
}
