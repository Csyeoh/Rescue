import React from 'react';
import { Settings, Sliders, Users, Drone, ShieldAlert, Waves, Activity, Droplets, Map as MapIcon, Terminal } from 'lucide-react';
import { MissionConfig } from '../../types';
import { ConfigRow } from '../Config/ConfigPage';

interface SidebarConfigProps {
  config: MissionConfig;
  isGenerating: boolean;
  onEditConfig: () => void;
  onGenerateMap: () => void;
  onResetSimulation: () => void;
  onDownloadLogs: () => void;
}

export const SidebarConfig: React.FC<SidebarConfigProps> = ({
  config,
  isGenerating,
  onEditConfig,
  onGenerateMap,
  onResetSimulation,
  onDownloadLogs
}) => {
  return (
    <aside className="w-64 flex flex-col gap-2 shrink-0 overflow-y-auto custom-scrollbar pr-1">
      <div className="bg-white p-5 rounded-2xl shadow-sm border border-[#c2dee1]/50">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <Settings className="text-[#416e6f]" size={20} />
            <h2 className="font-bold text-[#1A202C] uppercase text-sm tracking-tight">Mission Configuration</h2>
          </div>
          <button
            onClick={onEditConfig}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-yellow-400 hover:bg-yellow-500 text-[#416e6f] rounded-lg shadow-sm transition-all transform active:scale-95 border border-yellow-500/20 group"
            title="Edit Mission Parameters"
          >
            <Sliders size={14} className="group-hover:rotate-12 transition-transform" />
            <span className="text-[10px] font-black uppercase tracking-tight">Edit</span>
          </button>
        </div>

        <div className="space-y-5">
          <div className="space-y-2">
            <label className="text-[10px] font-black text-[#6aa7ad] uppercase tracking-widest">Simulation Difficulty</label>
            <div className="w-full bg-[#f5fffa] border border-[#c2dee1] rounded-xl px-3 py-2 text-xs font-bold text-[#416e6f] uppercase">
              {config.difficulty} - {config.difficulty === 'easy' ? 'LOW TURBULENCE' : config.difficulty === 'hard' ? 'EXTREME CONDITIONS' : 'STANDARD OPS'}
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="text-[10px] font-black text-[#416e6f]/40 uppercase tracking-widest border-b border-[#c2dee1] pb-1">Known Parameters</h3>
            <div className="space-y-3">
              <ConfigRow label="Survivors" icon={<Users size={14} />} value={config.survivors} />
              <ConfigRow label="Drone Count" icon={<Drone size={14} />} value={config.droneCount} />
              <ConfigRow label="Obstacles" icon={<ShieldAlert size={14} />} value={`${config.obstacleDensity}%`} />
              <ConfigRow label="Disaster" icon={<Waves size={14} />} value={config.disasterType.toUpperCase()} />
            </div>
          </div>

          {/* Environmental Unknowns Section */}
          <div className="space-y-4 pt-2">
            <h3 className="text-[10px] font-black text-[#416e6f]/40 uppercase tracking-widest border-b border-[#c2dee1] pb-1">Environmental Unknowns</h3>
            <div className="space-y-3">
              {config.disasterType === 'typhoon' && (
                <>
                  <ConfigRow label="Wind Speed" icon={<Activity size={14} />} value={`${config.windSpeed} km/h`} />
                  <ConfigRow label="Direction" icon={<Activity size={14} />} value={config.windDirection} />
                  <ConfigRow label="Rainfall" icon={<Droplets size={14} />} value={`${config.rainfall} mm/h`} />
                </>
              )}
              {config.disasterType === 'earthquake' && (
                <>
                  <ConfigRow label="Aftershock" icon={<Activity size={14} />} value={`${config.aftershockProb}%`} />
                  <ConfigRow label="Collapse Risk" icon={<ShieldAlert size={14} />} value={`${config.collapseRisk}%`} />
                </>
              )}
              {config.disasterType === 'tsunami' && (
                <>
                  <ConfigRow label="Flow Velocity" icon={<Waves size={14} />} value={`${config.waterFlow} m/s`} />
                  <ConfigRow label="Water Level" icon={<Droplets size={14} />} value={`${config.waterLevel} m`} />
                </>
              )}
              {config.disasterType === 'fire' && (
                <>
                  <ConfigRow label="Spread Rate" icon={<Activity size={14} />} value={`${config.fireSpread} m/min`} />
                  <ConfigRow label="Smoke Density" icon={<Activity size={14} />} value={`${config.smokeDensity}%`} />
                </>
              )}
              {config.disasterType === 'flash_flood' && (
                <>
                  <ConfigRow label="Rising Speed" icon={<Droplets size={14} />} value={`${config.risingSpeed} m/h`} />
                  <ConfigRow label="Water Level" icon={<Droplets size={14} />} value={`${config.waterLevel} m`} />
                </>
              )}
              {config.disasterType === 'default' && (
                <div className="text-[10px] font-bold text-[#6aa7ad] italic">No active unknowns</div>
              )}
            </div>
          </div>

          <button
            onClick={onGenerateMap}
            disabled={isGenerating}
            className={`w-full mt-4 flex items-center justify-center gap-2 bg-[#f5fffa] hover:bg-[#c2dee1]/30 text-[#416e6f] border border-[#c2dee1] py-3 rounded-xl font-black text-xs transition-all active:scale-95 ${isGenerating ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <MapIcon size={14} />
            {isGenerating ? 'GENERATING...' : 'GENERATE RANDOM MAP'}
          </button>

          <button
            onClick={onResetSimulation}
            className="w-full mt-2 flex items-center justify-center gap-2 bg-white hover:bg-red-50 text-red-600 border border-red-200 py-3 rounded-xl font-black text-xs transition-all active:scale-95"
          >
            <Activity size={14} />
            RESET SIMULATION
          </button>

          <button
            onClick={onDownloadLogs}
            className="w-full mt-2 flex items-center justify-center gap-2 bg-[#416e6f] hover:bg-[#416e6f]/90 text-white py-3 rounded-xl font-black text-xs transition-all active:scale-95"
          >
            <Terminal size={14} />
            DOWNLOAD MISSION LOG
          </button>
        </div>
      </div>
    </aside>
  );
};
