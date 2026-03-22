import React from 'react';
import { motion } from 'motion/react';
import { GridCell, EntityType, DisasterType } from '../../types';

interface GridCellProps {
  cell: GridCell;
  mode: 'god' | 'drone';
  isDroneHere?: boolean;
}

export const GridCellComponent: React.FC<GridCellProps> = ({ cell, mode, isDroneHere }) => {
  const isRevealed = mode === 'god' || cell.revealed;
  const effectiveType: EntityType =
    mode === 'drone' && cell.type === 'obstacle' && !cell.obstacleDiscovered ? 'empty' : cell.type;

  const getBgColor = () => {
    if (!isRevealed) return '#5a8e94'; // Blended dark teal for unrevealed
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
          </motion.div>
          {cell.y >= 5 && <div className="w-2 h-2 bg-neutral-dark rotate-45 -mt-1 border-r border-b border-white/10"></div>}
        </div>
      )}


      {/* Survivor Indicator */}
      {isRevealed && ((mode === 'god' && cell.hasSurvivor) || (mode === 'drone' && cell.isRescued)) && (
        <div className="absolute inset-0 flex items-center justify-center z-20">
          <motion.div 
            animate={{ 
              opacity: [0.6, 1, 0.6], 
              scale: cell.isRescued ? [1, 1.4, 1] : [0.8, 1.2, 0.8] 
            }}
            transition={{ repeat: Infinity, duration: 1.5 }}
            className={`w-2.5 h-2.5 rounded-full shadow-lg ${
              cell.isRescued 
                ? 'bg-emerald-500 shadow-emerald-500/50' 
                : 'bg-alert-yellow shadow-alert-yellow/50'
            }`}
          />
        </div>
      )}

      {/* Drone Indicator (Bright Blue Dot) */}
      {isDroneHere && (
        <div className="absolute inset-0 flex items-center justify-center z-30">
          <motion.div
            animate={{ scale: [1, 1.4, 1] }}
            transition={{ repeat: Infinity, duration: 0.8 }}
            className="w-2.5 h-2.5 bg-blue-400 rounded-full shadow-[0_0_12px_#60a5fa]"
          />
        </div>
      )}

      {/* Fog of War Layer (Drone Mode Only) */}
      {mode === 'drone' && !cell.revealed && (
        <div className={`absolute inset-0 z-10 bg-azure-dark/80 transition-opacity duration-500 ${cell.isIlluminated ? 'opacity-0' : 'opacity-100'}`} />
      )}

      {/* Base Station Highlight */}
      {cell.type === 'base' && (
        <div className="absolute inset-0 border-2 border-white/20 animate-pulse z-40 pointer-events-none rounded-[3px]" />
      )}
    </div>
  );
};

