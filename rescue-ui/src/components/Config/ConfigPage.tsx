import React, { useState } from 'react';
import { motion } from 'motion/react';
import { Settings, Activity, Users, Drone, ShieldAlert, Waves, Droplets } from 'lucide-react';
import { MissionConfig } from '../../types';

interface ConfigPageProps {
  config: MissionConfig;
  onSave: (c: MissionConfig) => void | Promise<void>;
  onCancel: () => void;
}

export const ConfigRow = ({ label, icon, value }: { label: string, icon: React.ReactNode, value: any }) => {
  return (
    <div className="flex items-center justify-between text-xs">
      <div className="flex items-center gap-2 text-azure-dark font-bold uppercase tracking-tight">
        {icon} {label}
      </div>
      <div className="font-black text-neutral-dark">{value}</div>
    </div>
  );
};

export const ConfigPage: React.FC<ConfigPageProps> = ({ config, onSave, onCancel }) => {
  const [localConfig, setLocalConfig] = useState<MissionConfig>(config);

  return (
    <div className="flex-1 flex items-center justify-center bg-white/10 p-8 overflow-y-auto">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-white w-full max-w-2xl rounded-3xl shadow-2xl border border-azure-pale/50 overflow-hidden"
      >
        <div className="bg-azure-dark p-8 text-white">
          <div className="flex items-center gap-3 mb-2">
            <Settings size={24} />
            <h2 className="text-2xl font-black tracking-tight uppercase">Mission Configuration</h2>
          </div>
          <p className="text-white/60 text-sm font-medium">Adjust parameters for the autonomous rescue protocol.</p>
        </div>

        <div className="p-8 space-y-8">
          <div className="grid grid-cols-2 gap-8">
            <div className="space-y-4">
              <label className="text-xs font-black text-azure-mid uppercase tracking-widest">Disaster Type</label>
              <div className="grid grid-cols-3 gap-2">
                {['typhoon', 'earthquake', 'tsunami', 'fire', 'flash_flood', 'default'].map((type) => (
                  <button
                    key={type}
                    onClick={() => setLocalConfig({ ...localConfig, disasterType: type as any })}
                    className={`px-4 py-3 rounded-xl text-[10px] font-black uppercase transition-all border ${localConfig.disasterType === type
                      ? 'bg-azure-dark text-white border-azure-dark shadow-md'
                      : 'bg-mint-bg text-azure-dark border-azure-pale hover:border-azure-mid'
                      }`}
                  >
                    {type.replace('_', ' ')}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-4">
              <label className="text-xs font-black text-azure-mid uppercase tracking-widest">Simulation Difficulty</label>
              <select
                value={localConfig.difficulty}
                onChange={(e) => setLocalConfig({ ...localConfig, difficulty: e.target.value as any })}
                className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-3 text-sm font-bold outline-none focus:ring-2 focus:ring-azure-mid"
              >
                <option value="easy">EASY - LOW TURBULENCE</option>
                <option value="normal">NORMAL - STANDARD OPS</option>
                <option value="hard">HARD - EXTREME CONDITIONS</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-6">
            <div className="space-y-2">
              <label className="text-[10px] font-black text-azure-mid uppercase tracking-widest">Survivors Amount</label>
              <input
                type="number"
                value={localConfig.survivors}
                onChange={(e) => setLocalConfig({ ...localConfig, survivors: parseInt(e.target.value) })}
                className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-3 text-sm font-bold outline-none"
              />
            </div>
            <div className="space-y-2">
              <label className="text-[10px] font-black text-azure-mid uppercase tracking-widest">Drone Count</label>
              <input
                type="number"
                value={localConfig.droneCount}
                onChange={(e) => setLocalConfig({ ...localConfig, droneCount: parseInt(e.target.value) })}
                className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-3 text-sm font-bold outline-none"
              />
            </div>
            <div className="space-y-2">
              <label className="text-[10px] font-black text-azure-mid uppercase tracking-widest">Obstacles (%)</label>
              <input
                type="number"
                value={localConfig.obstacleDensity}
                onChange={(e) => setLocalConfig({ ...localConfig, obstacleDensity: parseInt(e.target.value) })}
                className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-3 text-sm font-bold outline-none"
              />
            </div>
          </div>

          {/* Environmental Unknowns Section */}
          <div className="space-y-6 pt-6 border-t border-azure-pale">
            <div className="flex items-center gap-2">
              <Activity size={18} className="text-azure-dark" />
              <h3 className="text-sm font-black text-azure-dark uppercase tracking-widest">Environmental Unknowns</h3>
            </div>

            <div className="grid grid-cols-3 gap-6">
              {localConfig.disasterType === 'typhoon' && (
                <>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Wind Speed (km/h)</label>
                    <input type="number" value={localConfig.windSpeed} onChange={(e) => setLocalConfig({ ...localConfig, windSpeed: parseInt(e.target.value) })} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Wind Direction</label>
                    <select value={localConfig.windDirection} onChange={(e) => setLocalConfig({ ...localConfig, windDirection: e.target.value })} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none">
                      {['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'].map(d => <option key={d} value={d}>{d}</option>)}
                    </select>
                  </div>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Flying Debris Prob (%)</label>
                    <input type="number" value={localConfig.debrisProb} onChange={(e) => setLocalConfig({ ...localConfig, debrisProb: parseInt(e.target.value) })} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Rainfall Rate (mm/h)</label>
                    <input type="number" value={localConfig.rainfall} onChange={(e) => setLocalConfig({ ...localConfig, rainfall: parseInt(e.target.value) })} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none" />
                  </div>
                </>
              )}

              {localConfig.disasterType === 'earthquake' && (
                <>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Aftershock Prob (%)</label>
                    <input type="number" value={localConfig.aftershockProb} onChange={(e) => setLocalConfig({ ...localConfig, aftershockProb: parseInt(e.target.value) })} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Structural Collapse Risk (%)</label>
                    <input type="number" value={localConfig.collapseRisk} onChange={(e) => setLocalConfig({ ...localConfig, collapseRisk: parseInt(e.target.value) })} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none" />
                  </div>
                </>
              )}

              {localConfig.disasterType === 'tsunami' && (
                <>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Water Flow Velocity (m/s)</label>
                    <input type="number" value={localConfig.waterFlow} onChange={(e) => setLocalConfig({ ...localConfig, waterFlow: parseInt(e.target.value) })} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Secondary Wave (min)</label>
                    <input type="number" value={localConfig.secondaryWave} onChange={(e) => setLocalConfig({ ...localConfig, secondaryWave: parseInt(e.target.value) })} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Water Level (m)</label>
                    <input type="number" value={localConfig.waterLevel} onChange={(e) => setLocalConfig({ ...localConfig, waterLevel: parseInt(e.target.value) })} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none" />
                  </div>
                </>
              )}

              {localConfig.disasterType === 'fire' && (
                <>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Fire Spread Rate (m/min)</label>
                    <input type="number" value={localConfig.fireSpread} onChange={(e) => setLocalConfig({ ...localConfig, fireSpread: parseInt(e.target.value) })} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Smoke Density (%)</label>
                    <input type="number" value={localConfig.smokeDensity} onChange={(e) => setLocalConfig({ ...localConfig, smokeDensity: parseInt(e.target.value) })} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Extreme Heat Zones (%)</label>
                    <input type="number" value={localConfig.heatZones} onChange={(e) => setLocalConfig({ ...localConfig, heatZones: parseInt(e.target.value) })} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none" />
                  </div>
                </>
              )}

              {localConfig.disasterType === 'flash_flood' && (
                <>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Initial Water Level (m)</label>
                    <input type="number" value={localConfig.waterLevel} onChange={(e) => setLocalConfig({ ...localConfig, waterLevel: parseInt(e.target.value) })} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[9px] font-black text-azure-mid uppercase tracking-widest">Rising Speed (m/h)</label>
                    <input type="number" step="0.1" value={localConfig.risingSpeed} onChange={(e) => setLocalConfig({ ...localConfig, risingSpeed: parseFloat(e.target.value) })} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2 text-xs font-bold outline-none" />
                  </div>
                </>
              )}

              {localConfig.disasterType === 'default' && (
                <div className="col-span-3 text-center py-4 text-azure-mid italic text-xs">
                  No specific environmental unknowns for default scenario.
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center justify-end gap-4 pt-4 border-t border-azure-pale">
            <button
              onClick={onCancel}
              className="px-6 py-3 rounded-xl font-bold text-azure-mid hover:text-azure-dark transition-colors"
            >
              CANCEL
            </button>
            <button
              onClick={() => onSave(localConfig)}
              className="bg-emerald-500 text-white px-10 py-3 rounded-xl font-black shadow-lg hover:bg-emerald-600 transition-all transform active:scale-95"
            >
              DEPLOY MISSION
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  );
};
