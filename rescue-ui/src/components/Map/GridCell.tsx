import React from 'react';
import { motion } from 'motion/react';
import { GridCell, EntityType, DisasterType } from '../../types';

interface GridCellProps {
  cell: GridCell;
  mode: 'god' | 'drone';
  isDroneHere?: boolean;
  disasterType: DisasterType;
}

export const GridCellComponent: React.FC<GridCellProps> = ({ cell, mode, isDroneHere, disasterType }) => {
  const isRevealed = mode === 'god' || cell.revealed;
  const effectiveType: EntityType =
    mode === 'drone' && cell.type === 'obstacle' && !cell.obstacleDiscovered ? 'empty' : cell.type;

  const getBgColor = () => {
    if (!isRevealed) return '#5a8e94'; // Blended dark teal for unrevealed
    if (effectiveType === 'base') return '#164e63'; // Dark Cyan Base
    if (effectiveType === 'obstacle') return '#000000'; // High contrast black
    if (effectiveType === 'building') {
      return cell.height > 1 ? '#b30000' : '#ff8a8a'; // Restore building colors
    }

    // Terrain: Single base color with elevation-based opacity handled in style
    return '#87bcad';
  };

  const getOpacity = () => {
    if (!isRevealed || effectiveType === 'base' || effectiveType === 'obstacle' || effectiveType === 'building') return 1;
    // Map height (1-9) to opacity (0.2-0.8)
    return 0.2 + (cell.height / 9) * 0.6;
  };

  return (
    <div className="relative w-full h-full aspect-square overflow-hidden">
      {/* Terrain Layer */}
      <div
        className="absolute inset-0 transition-all duration-500"
        style={{
          backgroundColor: getBgColor(),
          opacity: getOpacity()
        }}
      />

      {/* Survivor Indicator (Glowing Yellow for Undiscovered, Green for Discovered) */}
      {isRevealed && ((mode === 'god' && cell.hasSurvivor) || (mode === 'drone' && cell.isRescued)) && (
        <div className="absolute inset-0 flex items-center justify-center z-20">
          <motion.div 
            animate={{ 
              opacity: [0.6, 1, 0.6], 
              scale: cell.isRescued ? [1, 1.2, 1] : [0.8, 1.1, 0.8] 
            }}
            transition={{ repeat: Infinity, duration: 1.5 }}
            className={`w-2 h-2 rounded-full shadow-lg ${
              cell.isRescued 
                ? 'bg-[#10B981] shadow-[#10B981]/50' // Bright Green for Rescued
                : 'bg-[#FACC15] shadow-[#FACC15]/50' // Yellow for Undiscovered
            }`}
          />
        </div>
      )}

      {/* Drone Indicator (Bright Blue Dot) */}
      {isDroneHere && (
        <div className="absolute inset-0 flex items-center justify-center z-30">
          <motion.div
            animate={{ scale: [1, 1.3, 1] }}
            transition={{ repeat: Infinity, duration: 0.6 }}
            className="w-2 h-2 bg-blue-400 rounded-full shadow-[0_0_8px_#60a5fa]"
          />
        </div>
      )}

      {/* Fog of War Layer (Drone Mode Only) */}
      {mode === 'drone' && !cell.revealed && (
        <div className={`absolute inset-0 z-10 bg-[#4a7a7e]/80 ${cell.isIlluminated ? 'opacity-0' : 'opacity-100'}`} />
      )}

      {/* Base Station Highlight */}
      {cell.type === 'base' && (
        <div className="absolute inset-0 border border-white/30 animate-pulse z-40 pointer-events-none" />
      )}
    </div>
  );
};
