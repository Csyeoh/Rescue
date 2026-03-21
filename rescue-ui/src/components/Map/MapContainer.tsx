import React from 'react';
import { GridCell, DroneStatus, DisasterType } from '../../types';
import { GridCellComponent } from './GridCell';

interface MapContainerProps {
  grid: GridCell[][];
  drones: DroneStatus[];
  disasterType: DisasterType;
}

export const MapContainer: React.FC<MapContainerProps> = ({
  grid,
  drones,
  disasterType
}) => {
  return (
    <main className="flex-1 flex flex-col gap-4 overflow-hidden min-h-0">
      <div className="flex-1 min-h-0">
        <div className="h-full grid grid-cols-2 gap-2">
          {/* Question Plane (God View) */}
          <div className="bg-white/90 backdrop-blur-sm p-2 rounded-xl shadow-sm border border-[#6aa7ad]/20 flex flex-col items-center overflow-hidden">
            <div className="flex items-center justify-between mb-2 w-full shrink-0">
              <div className="flex items-center gap-2">
                <h2 className="font-black text-slate-800 uppercase text-[10px] tracking-widest">Question Plane <span className="text-[#6aa7ad] font-bold ml-1 opacity-50">| GOD VIEW</span></h2>
              </div>
              <div className="text-[8px] font-black text-[#6aa7ad] bg-[#e1fef0] px-1.5 py-0.5 rounded border border-[#6aa7ad]/20">ABSOLUTE TRUTH</div>
            </div>
            <div className="flex-1 w-full bg-white/50 rounded-lg border border-[#6aa7ad]/10 p-0.5 flex items-center justify-center overflow-hidden min-h-0">
              <div
                className="aspect-square h-full w-auto max-w-full grid gap-[1px]"
                style={{ gridTemplateColumns: 'repeat(20, 1fr)', gridTemplateRows: 'repeat(20, 1fr)' }}
              >
                {grid.map((row, y) => row.map((cell, x) => (
                  <GridCellComponent
                    key={`q-${x}-${y}`}
                    cell={cell}
                    mode="god"
                    isDroneHere={drones.some(d => d.x === x && d.y === y)}
                    disasterType={disasterType}
                  />
                )))}
              </div>
            </div>
          </div>

          {/* Answer Plane (Drone View) */}
          <div className="bg-white/90 backdrop-blur-sm p-2 rounded-xl shadow-sm border border-[#6aa7ad]/20 flex flex-col items-center overflow-hidden">
            <div className="flex items-center justify-between mb-2 w-full shrink-0">
              <div className="flex items-center gap-2">
                <h2 className="font-black text-slate-800 uppercase text-[10px] tracking-widest">Answer Plane <span className="text-[#6aa7ad] font-bold ml-1 opacity-50">| DRONE VIEW</span></h2>
              </div>
              <div className="text-[8px] font-black text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-100">DYNAMIC UPDATE</div>
            </div>
            <div className="flex-1 w-full bg-white/50 rounded-lg border border-[#6aa7ad]/10 p-0.5 flex items-center justify-center overflow-hidden min-h-0">
              <div
                className="aspect-square h-full w-auto max-w-full grid gap-[1px]"
                style={{ gridTemplateColumns: 'repeat(20, 1fr)', gridTemplateRows: 'repeat(20, 1fr)' }}
              >
                {grid.map((row, y) => row.map((cell, x) => (
                  <GridCellComponent
                    key={`a-${x}-${y}`}
                    cell={cell}
                    mode="drone"
                    isDroneHere={drones.some(d => d.x === x && d.y === y)}
                    disasterType={disasterType}
                  />
                )))}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="shrink-0 flex flex-col gap-4">
        {/* Legend Section */}
        <div className="bg-white/90 backdrop-blur-sm p-3 rounded-xl shadow-sm border border-[#6aa7ad]/20 flex flex-wrap items-center justify-center gap-x-6 gap-y-3 max-w-full">
          <div className="flex items-center gap-2 text-[10px] font-black text-slate-700 uppercase whitespace-nowrap">
            <div className="w-3 h-3 bg-[#ff8a8a] rounded-sm" /> Single-Story
          </div>
          <div className="flex items-center gap-2 text-[10px] font-black text-[#416e6f] uppercase whitespace-nowrap">
            <div className="w-3 h-3 bg-[#b30000] rounded-sm" /> Multi-Story
          </div>
          <div className="flex items-center gap-2 text-[10px] font-black text-[#416e6f] uppercase whitespace-nowrap">
            <div className="w-3 h-3 bg-black rounded-sm" /> Obstacle
          </div>
          <div className="flex items-center gap-2 text-[10px] font-black text-[#416e6f] uppercase whitespace-nowrap">
            <div className="w-3 h-3 bg-[#87bcad] rounded-sm" /> Terrain
          </div>
          <div className="flex items-center gap-2 text-[10px] font-black text-[#416e6f] uppercase whitespace-nowrap">
            <div className="w-3 h-3 bg-cyan-900 rounded-sm" /> Base Station
          </div>
          <div className="flex items-center gap-2 text-[10px] font-black text-[#416e6f] uppercase whitespace-nowrap">
            <div className="w-2 h-2 bg-yellow-400 rounded-full shadow-[0_0_5px_#f2cf4e]" /> Survivor
          </div>
          <div className="flex items-center gap-2 text-[10px] font-black text-[#416e6f] uppercase whitespace-nowrap">
            <div className="w-2 h-2 bg-blue-400 rounded-full shadow-[0_0_5px_#60a5fa]" /> Drone
          </div>
          <div className="flex flex-col gap-1 min-w-[80px]">
            <span className="text-[8px] font-black text-[#6aa7ad] uppercase tracking-tighter">Elevation</span>
            <div className="flex items-center gap-2 text-[9px] font-bold text-[#6aa7ad] italic">
              <span>Lo</span>
              <div className="w-10 h-1 bg-gradient-to-r from-[#53a560] to-[#87bcad] rounded-full" />
              <span>Hi</span>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
};
