'use client';

import React, { useMemo, useState, useEffect } from 'react';
import DeckGL from '@deck.gl/react';
import { TextLayer } from '@deck.gl/layers';
import { EnvironmentState, DroneStatus } from '../../types';
import { ORBIT_VIEW, INITIAL_VIEW_STATE } from '../../scene/viewConfig';
import { createLightingEffect } from '../../scene/lighting';
import {
  envToBuildings,
  envToObstacles,
  envToSurvivors,
  envToThermalPolygons,
} from '../../scene/sceneDataAdapters';
import {
  createBuildingLayer,
  createObstacleLayer,
  createSurvivorLayer,
  createDroneLayer,
  createTrailLayer,
  createThermalLayer,
  createBaseLayer,
  createGroundLayer,
  createSectorLayer,
  createCoverageLayer,
} from '../../scene/layers';

import SurvivorMic from '../UI/SurvivorMic';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DeckGLContainerProps {
  environmentState: EnvironmentState;
  drones: DroneStatus[];
  coverage: { x: number, y: number }[];
  mode: 'god' | 'drone';
  showCoords: boolean;
  isNightMode: boolean;
  showXRay: boolean;
  showSectors: boolean;
  selectedSurvivorId?: string | null;
}

// ---------------------------------------------------------------------------
// Drone GLB model path.
// Drops in from /public/models/drone.glb when available.
// Falls back to a public CDN model in the meantime — swap this URL once you
// have your own quadcopter .glb placed in public/models/.
// ---------------------------------------------------------------------------

const DRONE_MODEL_URL = '/models/drone.glb';

// ---------------------------------------------------------------------------
// Themes extracted from:
// Light: Greens-7.json
// Dark: sample.json
// ---------------------------------------------------------------------------

const THEMES = {
  light: {
    ground: [237, 248, 233, 255],
    grid: [161, 217, 155, 120],
    building: [65, 171, 93],     // We'll add alpha dynamically
    buildingHover: [65, 171, 93, 100],
    buildingLine: [35, 139, 69, 255],
    obstacle: [239, 68, 68],     // Red
    obstacleLine: [185, 28, 28, 255],
    base: [35, 139, 69, 255],
    baseLine: [0, 90, 50, 255],
    survivor: {
      rescued: [34, 197, 94, 255],
      waiting: [255, 126, 0, 255]
    },
    drone: {
      charging: [199, 233, 192],
      returning: [176, 38, 255],
      idle: [199, 233, 192],
      searching: [116, 196, 118]
    },
    accent: [0, 90, 50],
    background: 'linear-gradient(160deg, #edf8e9 0%, #c7e9c0 100%)'
  },
  dark: {
    ground: [41, 75, 89, 255],
    grid: [45, 168, 139, 80],
    building: [232, 218, 141],   // We'll add alpha dynamically
    buildingHover: [232, 218, 141, 100],
    buildingLine: [232, 218, 141, 255],
    obstacle: [255, 48, 48],     // Vivid Red
    obstacleLine: [220, 38, 38, 255],
    base: [244, 163, 88, 255],
    baseLine: [139, 0, 0, 255],
    survivor: {
      rescued: [34, 197, 94, 255],
      waiting: [255, 126, 0, 255]
    },
    drone: {
      charging: [244, 163, 88],
      returning: [176, 38, 255],
      idle: [244, 163, 88],
      searching: [45, 168, 139]
    },
    accent: [45, 168, 139],
    background: 'linear-gradient(160deg, #1e293b 0%, #0f172a 100%)'
  }
};



// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function DeckGLContainer({
  environmentState,
  drones,
  coverage,
  mode,
  showCoords,
  isNightMode,
  showXRay,
  showSectors,
  selectedSurvivorId: selectedSurvivorIdProp = null
}: DeckGLContainerProps) {
  const [hoveredBuildingId, setHoveredBuildingId] = useState<string | null>(null);
  const [selectedMicSurvivorId, setSelectedMicSurvivorId] = useState<number | null>(null);
  const [time, setTime] = useState(0);

  // ── Animation Loop ──
  useEffect(() => {
    let request: number;
    const animate = () => {
      setTime(t => t + 1);
      request = requestAnimationFrame(animate);
    };
    request = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(request);
  }, []);

  // ── Data adapters (memoised to prevent re-clustering on every render) ──
  const buildingData = useMemo(() => envToBuildings(environmentState), [environmentState]);
  const obstacleData = useMemo(() => envToObstacles(environmentState, mode === 'god'), [environmentState, mode]);
  const survivorData = useMemo(() => envToSurvivors(environmentState), [environmentState]);
  const thermalData = useMemo(() => envToThermalPolygons(environmentState), [environmentState]);

  // ── Layer stack (bottom → top) ─────────────────────────────────────────
  const layers = useMemo(() => {
    const theme = isNightMode ? THEMES.dark : THEMES.light;

    return [
      // 0. Base ground plane below everything
      ...createGroundLayer({ ground: theme.ground, grid: theme.grid }),

      // 0.5 Coverage layer (Fog of War)
      createCoverageLayer(coverage),

      // 1. Transient scans and Survivors
      createThermalLayer(thermalData, time),
      createSurvivorLayer(survivorData, theme.survivor, selectedSurvivorIdProp),

      // 2. Static environment
      createBuildingLayer(buildingData, hoveredBuildingId, {
        building: theme.building,
        buildingHover: theme.buildingHover,
        line: theme.buildingLine
      }, showXRay),
      createObstacleLayer(obstacleData, time, {
        obstacle: theme.obstacle,
        line: theme.obstacleLine
      }),

      // 3. Base station beacon
      createBaseLayer({ color: theme.base, line: theme.baseLine, bases: environmentState.bases }),

      // 4. Flight trails and Sectors
      createTrailLayer(drones),
      createSectorLayer(environmentState.sectors, time, showSectors),

      // 5. Drone 3D models
      createDroneLayer(drones, DRONE_MODEL_URL, theme.drone),

      // 6. Grid Axis Labels (Controlled by Toggle)
      new TextLayer({
        id: 'axis-labels',
        data: Array.from({ length: 21 }, (_, i) => i),
        visible: showCoords,
        getPosition: (i: number) => [i, -3.0, 0.05],
        getText: (i: number) => i.toString(),
        getSize: 16,
        getColor: theme.accent as any,
        getAlignmentBaseline: 'center',
        fontWeight: 'bold',
        outlineWidth: 2,
        outlineColor: [0, 0, 0, 128],
      }),

      new TextLayer({
        id: 'axis-labels-y',
        data: Array.from({ length: 21 }, (_, i) => i),
        visible: showCoords,
        getPosition: (i: number) => [-3.0, i, 0.05],
        getText: (i: number) => i.toString(),
        getSize: 16,
        getColor: theme.accent as any,
        getAlignmentBaseline: 'center',
        fontWeight: 'bold',
        outlineWidth: 2,
        outlineColor: [0, 0, 0, 128],
      }),
    ];
  }, [buildingData, obstacleData, thermalData, survivorData, drones, environmentState.sectors, hoveredBuildingId, time, showCoords,showSectors, isNightMode, selectedSurvivorIdProp]);

  // ── Lighting Rig ──
  const effect = useMemo(() => createLightingEffect(isNightMode), [isNightMode]);

  const backgroundGradient = isNightMode ? THEMES.dark.background : THEMES.light.background;



  return (
    <div
      className="absolute inset-0 w-full h-full transition-colors duration-1000"
      style={{ background: backgroundGradient }}
    >


      <DeckGL
        views={[ORBIT_VIEW]}
        // @ts-expect-error — deck.gl types sometimes misalign with Next.js strict mode
        initialViewState={INITIAL_VIEW_STATE}
        controller={true}
        effects={[effect]}
        layers={layers}
        getCursor={() => 'default'}

        onClick={(info) => {
          if (info.layer?.id === 'survivors' && info.object) {
            const rawId = (info.object as any)?.id;
            let numericId: number | null = null;
            if (typeof rawId === 'number') {
              numericId = rawId;
            } else if (typeof rawId === 'string') {
              const digits = rawId.replace(/[^\d]/g, '');
              const parsed = digits ? Number(digits) : NaN;
              numericId = Number.isFinite(parsed) ? parsed : null;
            }
            if (numericId === null && typeof (info as any).index === 'number') {
              numericId = (info as any).index;
            }
            setSelectedMicSurvivorId(numericId);
          } else {
            // Clicked somewhere else, dismiss the mic
            setSelectedMicSurvivorId(null);
          }
        }}

        getTooltip={(info) => {
          if (!info || !info.object) return null;
          const { object, layer, coordinate } = info;
          const [mouseX, mouseY] = coordinate ? coordinate.map(v => v.toFixed(2)) : ['?', '?'];

          let content = '';
          let title = '';
          let displayX = mouseX;
          let displayY = mouseY;

          switch (layer?.id) {
            case 'buildings':
              title = `Building: ${object.id}`;
              displayX = object.center[0].toFixed(2);
              displayY = object.center[1].toFixed(2);
              content = `
                <div class="flex flex-col gap-1 mt-1">
                  <div class="flex justify-between gap-4"><span>Survivors:</span><span class="font-bold text-azure-mid">${object.survivorCount}</span></div>
                  <div class="flex justify-between gap-4"><span>Found:</span><span class="font-bold text-emerald-500">${object.foundCount}</span></div>
                </div>
              `;
              break;
            case 'obstacles':
              title = 'Obstacle';
              displayX = object.center[0].toFixed(2);
              displayY = object.center[1].toFixed(2);
              break;
            case 'base-station':
              const baseDrones = drones.filter(d => Math.hypot(d.x - 9.5, d.y - 9.5) < 1.0).length;
              title = 'Base Station';
              displayX = '9.50';
              displayY = '9.50';
              content = `
                <div class="flex flex-col gap-1 mt-1">
                  <div class="flex justify-between gap-4"><span>Drones docked:</span><span class="font-bold text-azure-mid">${baseDrones}</span></div>
                </div>
              `;
              break;
            case 'drones':
              title = `Drone: ${object.id}`;
              displayX = object.x.toFixed(2);
              displayY = object.y.toFixed(2);
              content = `
                <div class="flex flex-col gap-1 mt-1">
                  <div class="flex justify-between gap-4"><span>Status:</span><span class="font-bold capitalize text-azure-mid">${object.status}</span></div>
                  <div class="flex justify-between gap-4"><span>Battery:</span><span class="font-bold text-emerald-500">${object.battery}%</span></div>
                </div>
              `;
              break;
            case 'survivors':
              title = `Survivor: ${object.id ?? ''}`;
              displayX = (object.position[0]).toFixed(2);
              displayY = (object.position[1]).toFixed(2);
              content = `
                <div class="flex flex-col gap-1 mt-1">
                  <div class="flex justify-between gap-4"><span>Status:</span><span class="font-bold text-emerald-500">${object.rescued ? 'Located' : 'Unconfirmed'}</span></div>
                  <div class="flex justify-between gap-4"><span>Found tick:</span><span class="font-bold text-azure-mid">${object.foundTick ?? '—'}</span></div>
                </div>
              `;
              break;
            default:
              return null;
          }

          return {
            html: `
              <div class="bg-neutral-dark text-mint-bg p-3 rounded-lg border border-azure-dark/30 shadow-2xl backdrop-blur-md min-w-[150px]">
                <div class="text-xs font-bold text-azure-mid border-b border-azure-dark/20 pb-1 mb-2 capitalize tracking-wide">
                  ${title}
                </div>
                ${content}
                <div class="mt-3 pt-2 border-t border-azure-dark/10 text-xs text-mint-bg/60 font-mono">
                  Location: ${displayX}, ${displayY}
                </div>
              </div>
            `,
            style: {
              backgroundColor: 'transparent',
              padding: '0'
            }
          };
        }}
        onHover={(info) => {
          if (info.layer?.id === 'buildings') {
            setHoveredBuildingId(info.object?.id ?? null);
          } else if (hoveredBuildingId) {
            setHoveredBuildingId(null);
          }
        }}
      />

      {/* 2. RENDER THE MIC UI WHEN A SURVIVOR IS SELECTED */}
      {selectedMicSurvivorId !== null && (
        <SurvivorMic
          droneId={drones[0]?.id ?? "drone_1"}
          survivorId={selectedMicSurvivorId}
          
          onIntelReceived={(intelData) => {
            console.log("INTEL RECEIVED:", intelData);
            const intel = intelData.intel;
            
            // Check if medical_needs is an array before joining; otherwise show the raw value or 'None'
            const medNeeds = Array.isArray(intel?.medical_needs) 
              ? intel.medical_needs.join(', ') 
              : (intel?.medical_needs || 'None');

            const supplies = Array.isArray(intel?.requested_supplies)
              ? intel.requested_supplies.join(', ')
              : (intel?.requested_supplies || 'None');

            alert(
              `Intel Received!\n` +
              `Urgency: ${intel?.urgency_level || 'UNKNOWN'}\n` +
              `Medical Needs: ${medNeeds}\n` +
              `Supplies: ${supplies}`
            );
          }}
          onResolve={() => setSelectedMicSurvivorId(null)}
        />
      )}

    </div>
  );
}
