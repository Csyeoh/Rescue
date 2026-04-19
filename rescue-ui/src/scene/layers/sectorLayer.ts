import { ScatterplotLayer } from '@deck.gl/layers';
import { PathStyleExtension } from '@deck.gl/extensions';
import { SectorData } from '../../types';

// Map drone IDs to specific prominent colours so we can trace who is searching where.
const DRONE_COLORS: Record<string, [number, number, number]> = {
  drone_1: [56, 189, 248], // Sky Blue
  drone_2: [244, 114, 182], // Pink
  drone_3: [250, 204, 21],  // Yellow
  drone_4: [167, 139, 250], // Purple
  drone_5: [251, 146, 60],  // Orange
};

const DEFAULT_COLOR: [number, number, number] = [200, 200, 200];

export function createSectorLayer(
  sectors: SectorData[] | undefined,
  time: number,
  isVisible: boolean
) {
  if (!sectors || sectors.length === 0) return null;

  // Expands up to its radius and stops over 60 frames (~1 sec)
  const progress = Math.min(1.0, time / 60);

  return new ScatterplotLayer<SectorData>({
    id: 'drone-sectors', // Fixed static ID for performance
    data: sectors,
    visible: isVisible,
    pickable: false,
    opacity: 1,
    stroked: true,
    filled: true,
    radiusScale: 1,
    lineWidthUnits: 'pixels',
    getLineWidth: 2,
    lineWidthMinPixels: 1,

    // -- STYLING ENHANCEMENTS --
    extensions: [new PathStyleExtension({ dash: true })],
    // @ts-ignore - Dash properties are provided by the extension
    getDashArray: [8, 4],
    dashJustified: true,
    dashOffset: time / 10,

    getPosition: (d: SectorData) => [d.cx + 0.5, d.cy + 0.5, 0.05],
    // 1 unit = 1 grid cell in DeckGL Cartesian rendering.
    getRadius: (d: SectorData) => d.radius * progress, 
    getFillColor: (d: SectorData) => {
        const rgb = DRONE_COLORS[d.drone_id] || DEFAULT_COLOR;
        return [...rgb, 30]; // Prescribed alpha
    },
    getLineColor: (d: SectorData) => {
        const rgb = DRONE_COLORS[d.drone_id] || DEFAULT_COLOR;
        return [...rgb, 150]; // More subtle alpha
    },
    updateTriggers: {
        getRadius: [progress],
        dashOffset: [time] // Animate dashes every frame
    }
  });
}
