import React from 'react';
import { motion } from 'motion/react';
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
    <main className="flex-1 flex flex-col gap-4 min-h-0 overflow-hidden">
      <div className="flex-1 min-h-0">
        <div className="h-full grid grid-cols-1 xl:grid-cols-2 gap-3">
          {/* Question Plane (God View) */}
          <section className="bg-white/80 backdrop-blur-sm p-4 rounded-2xl shadow-sm border border-azure-pale/50 flex flex-col items-center overflow-hidden">
            <div className="flex items-center justify-between mb-4 w-full shrink-0">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-azure-mid" />
                <h2 className="font-bold text-neutral-dark capitalize text-base tracking-tight">
                  Question Plan
                </h2>
              </div>
              <div className="text-[12px] font-bold text-azure-dark bg-mint-bg px-2.5 py-1 rounded-lg border border-azure-pale/50 shadow-inner capitalize">
                God View
              </div>
            </div>
            
            <div className="flex-1 w-full bg-mint-bg/30 rounded-2xl border border-azure-pale/30 p-1 flex items-center justify-center overflow-hidden min-h-0">
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
                  />
                )))}
              </div>
            </div>
          </section>

          {/* Answer Plane (Drone View) */}
          <section className="bg-white/80 backdrop-blur-sm p-4 rounded-2xl shadow-sm border border-azure-pale/50 flex flex-col items-center overflow-hidden">
            <div className="flex items-center justify-between mb-4 w-full shrink-0">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <h2 className="font-bold text-neutral-dark capitalize text-base tracking-tight">
                  Answer Plan
                </h2>
              </div>
              <div className="text-[12px] font-bold text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded-lg border border-emerald-100 shadow-inner capitalize">
                Swarm View
              </div>
            </div>
            
            <div className="flex-1 w-full bg-mint-bg/30 rounded-2xl border border-azure-pale/30 p-1 flex items-center justify-center overflow-hidden min-h-0">
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
                  />
                )))}
              </div>
            </div>
          </section>
        </div>
      </div>

      {/* Legend Section */}
      <footer className="shrink-0 bg-white/90 backdrop-blur-sm p-5 rounded-2xl shadow-sm border border-azure-pale/50 flex flex-wrap items-center justify-center gap-x-12 gap-y-4">
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-2.5 text-[13px] font-bold text-azure-dark capitalize">
            <div className="w-4 h-4 bg-[#ff8a8a] rounded-sm shadow-sm" /> Single-story
          </div>
          <div className="flex items-center gap-2.5 text-[13px] font-bold text-azure-dark capitalize">
            <div className="w-4 h-4 bg-[#b30000] rounded-sm shadow-sm" /> Multi-story
          </div>
          <div className="flex items-center gap-2.5 text-[13px] font-bold text-azure-dark capitalize">
            <div className="w-4 h-4 bg-black rounded-sm shadow-sm" /> Obstacle
          </div>
        </div>

        <div className="h-5 w-px bg-azure-pale/50" />

        <div className="flex items-center gap-8">
          <div className="flex items-center gap-2.5 text-[13px] font-bold text-azure-dark capitalize">
            <div className="w-3.5 h-3.5 bg-cyan-900 rounded-sm shadow-sm" /> Base station
          </div>
          <div className="flex items-center gap-2.5 text-[13px] font-bold text-azure-dark capitalize">
            <motion.div 
              animate={{ scale: [1, 1.2, 1] }}
              transition={{ repeat: Infinity, duration: 2 }}
              className="w-3 h-3 bg-alert-yellow rounded-full shadow-[0_0_8px_rgba(242,207,78,0.6)]" 
            /> 
            Survivor
          </div>
          <div className="flex items-center gap-2.5 text-[13px] font-bold text-azure-dark capitalize">
            <motion.div 
              animate={{ scale: [1, 1.2, 1] }}
              transition={{ repeat: Infinity, duration: 2 }}
              className="w-3 h-3 bg-blue-400 rounded-full shadow-[0_0_8px_rgba(96,165,250,0.6)]" 
            /> 
            Drone
          </div>
        </div>

        <div className="h-5 w-px bg-azure-pale/50" />

        <div className="flex items-center gap-5">
          <span className="text-[12px] font-bold text-azure-mid capitalize tracking-tight">Elevation</span>
          <div className="flex items-center gap-2.5 text-[12px] font-bold text-azure-mid italic">
            <span>Lo</span>
            <div className="w-24 h-2 bg-gradient-to-r from-emerald-100 to-emerald-900 rounded-full shadow-inner" />
            <span>Hi</span>
          </div>
        </div>
      </footer>
    </main>
  );
};
