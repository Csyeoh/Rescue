import React from 'react';
import { motion } from 'motion/react';
import { ShieldAlert, Play, Square } from 'lucide-react';
import { DisasterType } from '../../types';
import { GRID_SIZE } from '../../constants';

interface HeaderProps {
  revealedCells: number;
  survivorsDetected: number;
  totalSurvivors: number;
  disasterType: DisasterType;
  isSimulationRunning: boolean;
  isAborting: boolean;
  onToggleSimulation: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  revealedCells,
  survivorsDetected,
  totalSurvivors,
  disasterType,
  isSimulationRunning,
  isAborting,
  onToggleSimulation
}) => {
  return (
    <header className="flex items-center justify-between bg-white/80 backdrop-blur-sm px-6 py-2 rounded-xl shadow-sm border border-[#6aa7ad]/20 shrink-0 mx-2 mt-2">
      <div className="flex items-center gap-4">
        <div className="p-2 rounded-xl shadow-inner">
          <img
            src="/logo.png"
            alt="Logo"
            className="w-10 h-10 object-contain"
          />
        </div>
        <div>
          <h1 className="text-xl font-black tracking-tighter text-neutral-dark">SaveMePls</h1>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-[10px] font-bold text-azure-mid uppercase tracking-widest">Drone Rescue System</span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex flex-col items-end mr-4">
          <span className="text-[10px] font-black text-azure-mid uppercase tracking-widest">Map Discovery</span>
          <div className="flex items-center gap-2">
            <span className="text-xl font-black text-emerald-500">{Math.min(100, Math.floor((revealedCells / (GRID_SIZE * GRID_SIZE)) * 100))}%</span>
            <div className="w-24 h-2 bg-[#f5fffa] border border-[#c2dee1] rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-emerald-500"
                animate={{ width: `${Math.min(100, (revealedCells / (GRID_SIZE * GRID_SIZE)) * 100)}%` }}
              />
            </div>
          </div>
        </div>
        <div className="flex flex-col items-end mr-4">
          <span className="text-[10px] font-black text-azure-mid uppercase tracking-widest">Survivors Detected</span>
          <div className="flex items-center gap-2">
            <span className="text-xl font-black text-blue-500">{survivorsDetected}/{totalSurvivors}</span>
            <div className="w-24 h-2 bg-[#f5fffa] border border-[#c2dee1] rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-blue-500"
                animate={{ width: `${(survivorsDetected / totalSurvivors) * 100}%` }}
              />
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 bg-[#f5fffa] px-4 py-2 rounded-xl border border-[#c2dee1]">
          <ShieldAlert size={16} className="text-[#d96627]" />
          <span className="text-xs font-bold text-[#416e6f] uppercase">Scenario: {disasterType}</span>
        </div>
        <button
          onClick={onToggleSimulation}
          disabled={isAborting}
          className={`flex items-center gap-2 px-8 py-3 rounded-xl font-black transition-all transform active:scale-95 shadow-lg ${isSimulationRunning
            ? 'bg-[#d65b34] text-white hover:bg-[#d96627]'
            : 'bg-[#f2cf4e] text-[#1A202C] hover:brightness-105'
            } ${isAborting ? 'opacity-70 cursor-not-allowed' : ''}`}
        >
          {isSimulationRunning ? <Square size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" />}
          {isSimulationRunning ? (isAborting ? 'ABORTING...' : 'ABORT MISSION') : 'DEPLOY SWARM'}
        </button>
      </div>
    </header>
  );
};
