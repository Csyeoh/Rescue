import React from 'react';
import { motion } from 'motion/react';
import { ShieldAlert, Play, Square, Radio } from 'lucide-react';
import { DisasterType } from '../../types';
import { GRID_SIZE } from '../../constants';

interface HeaderProps {
  revealedCells: number;
  survivorsDetected: number;
  totalSurvivors: number;
  disasterType: DisasterType;
  isSimulationRunning: boolean;
  isAborting: boolean;
  isMapGenerated: boolean;
  onToggleSimulation: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  revealedCells,
  survivorsDetected,
  totalSurvivors,
  disasterType,
  isSimulationRunning,
  isAborting,
  isMapGenerated,
  onToggleSimulation
}) => {
  const discoveryPercent = Math.min(100, Math.floor((revealedCells / (GRID_SIZE * GRID_SIZE)) * 100));
  const detectedPercent = (survivorsDetected / totalSurvivors) * 100;

  return (
    <header className="flex items-center justify-between bg-white/90 backdrop-blur-md px-6 py-3 rounded-2xl shadow-sm border border-azure-pale/50 shrink-0 mx-1">
      <div className="flex items-center gap-4">
        <motion.div 
          whileHover={{ rotate: 5 }}
          className="p-2 bg-mint-bg rounded-xl border border-azure-pale/50"
        >
          <img
            src="/logo.png"
            alt="Logo"
            className="w-10 h-10 object-contain"
          />
        </motion.div>
        <div>
          <h1 className="text-xl font-bold tracking-tight text-neutral-dark">SaveMePls</h1>
          <div className="flex items-center gap-2">
            <Radio size={14} className="text-emerald-500 animate-pulse" />
            <span className="text-[13px] font-semibold text-azure-mid capitalize tracking-tight">Intelligent Drone Rescue System</span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-10">
        {/* Discovery Metric */}
        <div className="flex flex-col gap-1.5">
          <div className="flex justify-between items-center text-[13px] font-bold text-azure-dark capitalize">
            <span>Zone discovery</span>
            <span className="text-emerald-600 font-mono text-base">{discoveryPercent}%</span>
          </div>
          <div className="w-40 h-2.5 bg-mint-bg border border-azure-pale rounded-full overflow-hidden shadow-inner">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${discoveryPercent}%` }}
              className="h-full bg-emerald-500 rounded-full shadow-[0_0_8px_rgba(16,185,129,0.3)]"
            />
          </div>
        </div>

        {/* Survivors Metric */}
        <div className="flex flex-col gap-1.5">
          <div className="flex justify-between items-center text-[13px] font-bold text-azure-dark capitalize">
            <span>Survivors found</span>
            <span className="text-blue-600 font-mono text-base">{survivorsDetected}/{totalSurvivors}</span>
          </div>
          <div className="w-40 h-2.5 bg-mint-bg border border-azure-pale rounded-full overflow-hidden shadow-inner">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${detectedPercent}%` }}
              className="h-full bg-blue-500 rounded-full shadow-[0_0_8px_rgba(59,130,246,0.3)]"
            />
          </div>
        </div>

        <div className="h-12 w-px bg-azure-pale/50 mx-2" />

        <div className="flex items-center gap-4">
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={onToggleSimulation}
            disabled={isAborting || (!isSimulationRunning && !isMapGenerated)}
            className={`flex items-center gap-3 px-10 py-3 rounded-xl font-bold transition-all shadow-lg ${isSimulationRunning
              ? 'bg-alert-red text-white hover:bg-alert-orange shadow-alert-red/20'
              : 'bg-emerald-500 text-white hover:bg-emerald-600 shadow-emerald-500/20'
              } ${isAborting || (!isSimulationRunning && !isMapGenerated) ? 'opacity-50 cursor-not-allowed grayscale' : ''}`}
          >
            {isSimulationRunning ? <Square size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" />}
            <span className="text-base">
              {isSimulationRunning ? (isAborting ? 'Aborting...' : 'Abort mission') : 'Deploy swarm'}
            </span>
          </motion.button>
        </div>
      </div>
    </header>
  );
};
