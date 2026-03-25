import React from 'react';
import { motion } from 'motion/react';
import { GridCell, EntityType, DisasterType, DroneStatus } from '../../types';

interface GridCellProps {
  cell: GridCell;
  mode: 'god' | 'drone';
  dronesHere?: DroneStatus[];
}

export const GridCellComponent: React.FC<GridCellProps> = ({ cell, mode, dronesHere }) => {
  const isRevealed = mode === 'god' || cell.revealed;
  const effectiveType: EntityType =
    mode === 'drone' && cell.type === 'obstacle' && !cell.obstacleDiscovered ? 'empty' : cell.type;

  const getBgColor = () => {
    if (!isRevealed) return '#94a3b8'; // Neutral Slate-400 for unrevealed
    if (effectiveType === 'base') return '#164e63'; // Dark Cyan Base
    if (effectiveType === 'obstacle') return '#000000'; // High contrast black
    if (effectiveType === 'building') {
      return cell.buildingHeight && cell.buildingHeight > 5 ? '#b30000' : '#ff8a8a';
    }

    // Altitude-based gradient for terrain (Green/Teal spectrum)
    const alt = cell.altitude ?? 0;
    // Map 0-100 altitude to HSL lightness 85% to 25%
    const lightness = 85 - (alt / 100) * 60;
    return `hsl(161, 45%, ${lightness}%)`;
  };

  return (
    <div className="group relative w-full h-full aspect-square overflow-visible rounded-[3px]">
      {/* Terrain Layer */}
      <motion.div
        initial={false}
        animate={{ 
          backgroundColor: getBgColor(),
        }}
        transition={{ duration: 0.5 }}
        className="absolute inset-0 rounded-[3px]"
      />

      {/* Hover Info Tooltip */}
      {isRevealed && (
        <div className={`absolute ${cell.y < 5 ? 'top-full mt-2' : 'bottom-full mb-2'} left-1/2 -translate-x-1/2 hidden group-hover:flex flex-col items-center z-[100] pointer-events-none`}>
          {cell.y < 5 && <div className="w-2 h-2 bg-neutral-dark rotate-45 -mb-1 border-l border-t border-white/10"></div>}
          <motion.div 
            initial={{ opacity: 0, y: cell.y < 5 ? -5 : 5 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-neutral-dark text-white text-[11px] px-3 py-2 rounded-xl shadow-2xl whitespace-nowrap flex flex-col gap-1 border border-white/10"
          >
            <div className="flex justify-between gap-4">
              <span className="text-white/40 font-bold capitalize">Altitude</span>
              <span className="font-mono text-emerald-400">{(cell.altitude ?? 0).toFixed(1)}m</span>
            </div>
            {cell.type === 'building' && (
              <div className="flex justify-between gap-4 border-t border-white/5 pt-1">
                <span className="text-white/40 font-bold capitalize">Building</span>
                <span className="font-mono text-alert-red">{(cell.buildingHeight ?? 0).toFixed(1)}m</span>
              </div>
            )}
            <div className="flex justify-between gap-4 border-t border-white/5 pt-1">
              <span className="text-white/40 font-bold capitalize">Position</span>
              <span className="font-mono text-azure-pale">{cell.x}, {cell.y}</span>
            </div>
            {dronesHere && dronesHere.length > 0 && (
              <div className="flex flex-col gap-1 border-t border-white/5 pt-1">
                <span className="text-white/40 font-bold capitalize text-[10px]">Active Swarm</span>
                <div className="flex flex-wrap gap-1 max-w-[120px]">
                  {dronesHere.map(d => (
                    <span key={d.id} className="font-mono text-blue-400 text-[9px] bg-blue-400/10 px-1 rounded">
                      {d.id}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
          {cell.y >= 5 && <div className="w-2 h-2 bg-neutral-dark rotate-45 -mt-1 border-r border-b border-white/10"></div>}
        </div>
      )}


      {/* Agents Layer (Survivors and Drones) */}
      <div className="absolute inset-0 flex flex-wrap items-center justify-center gap-[1px] p-[1px] z-30 pointer-events-none overflow-hidden">
        {/* Thermal Aura Indicator (Orange Pulse) */}
        {isRevealed && cell.thermal_aura && !cell.hasSurvivor && !cell.isRescued && (
          <motion.div 
            animate={{ 
              opacity: [0.3, 0.7, 0.3],
              scale: [0.8, 1.2, 0.8]
            }}
            transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
            className="w-1.5 h-1.5 bg-orange-500/60 rounded-full blur-[1px] shrink-0"
          />
        )}

        {/* Survivor Indicator */}
        {isRevealed && ((mode === 'god' && cell.hasSurvivor) || (mode === 'drone' && cell.isRescued)) && (
          <motion.div 
            animate={{ 
              opacity: [0.6, 1, 0.6], 
              scale: cell.isRescued ? [1, 1.4, 1] : [0.8, 1.2, 0.8] 
            }}
            transition={{ repeat: Infinity, duration: 1.5 }}
            className={`w-2 h-2 rounded-full shadow-lg shrink-0 ${
              cell.isRescued 
                ? 'bg-emerald-500 shadow-emerald-500/50' 
                : 'bg-alert-yellow shadow-alert-yellow/50'
            }`}
          />
        )}

        {/* Drone Indicator (Bright Blue Dot) - Single dot representing one or more drones */}
        {dronesHere && dronesHere.length > 0 && (
          <motion.div
            animate={{ scale: [1, 1.4, 1] }}
            transition={{ repeat: Infinity, duration: 0.8 }}
            className="w-2 h-2 bg-blue-400 rounded-full shadow-[0_0_12px_#60a5fa] shrink-0"
          />
        )}
      </div>

      {/* Base Station Highlight */}
      {cell.type === 'base' && (
        <div className="absolute inset-0 border-2 border-white/20 animate-pulse z-40 pointer-events-none rounded-[3px]" />
      )}
    </div>
  );
};

