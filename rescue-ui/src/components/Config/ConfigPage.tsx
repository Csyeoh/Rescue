import React, { useState } from 'react';
import { motion } from 'motion/react';
import { Settings, Activity, ArrowLeft, Save, Sparkles } from 'lucide-react';
import { MissionConfig } from '../../types';
import { useToast } from '../UI/Toast';

interface ConfigPageProps {
  config: MissionConfig;
  onSave: (c: MissionConfig) => void | Promise<void>;
  onCancel: () => void;
}

export const ConfigRow = ({ label, icon, value }: { label: string, icon: React.ReactNode, value: any }) => {
  return (
    <div className="flex items-center justify-between text-sm py-1">
      <div className="flex items-center gap-2 text-azure-dark font-medium capitalize">
        <span className="opacity-70">{icon}</span>
        {label}
      </div>
      <div className="font-bold text-neutral-dark">{value}</div>
    </div>
  );
};

export const ConfigPage: React.FC<ConfigPageProps> = ({ config, onSave, onCancel }) => {
  const [localConfig, setLocalConfig] = useState<MissionConfig>(config);
  const { showToast } = useToast();

  const handleSave = () => {
    onSave(localConfig);
    showToast('Mission configuration updated.', 'success');
  };

  return (
    <div className="h-screen w-screen bg-mint-bg overflow-y-auto custom-scrollbar flex flex-col">
      {/* Top Navigation Bar */}
      <header className="bg-white border-b border-azure-pale px-8 py-4 flex items-center justify-between sticky top-0 z-10 shadow-sm">
        <div className="flex items-center gap-4">
          <button
            onClick={onCancel}
            className="p-2 hover:bg-azure-pale/30 rounded-full transition-colors text-azure-dark"
          >
            <ArrowLeft size={20} />
          </button>
          <div>
            <h1 className="text-xl font-bold text-neutral-dark capitalize">Mission Configuration</h1>
            <p className="text-xs text-azure-mid font-medium">Adjust parameters for the autonomous rescue protocol</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={onCancel}
            className="px-6 py-2.5 rounded-xl font-bold text-azure-mid hover:text-azure-dark transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="bg-azure-dark text-white px-8 py-2.5 rounded-xl font-bold shadow-lg shadow-azure-dark/20 hover:bg-azure-dark/90 transition-all flex items-center gap-2"
          >
            <Save size={18} />
            Save Configuration
          </button>
        </div>
      </header>

      <main className="flex-1 max-w-5xl mx-auto w-full p-8 space-y-8">
        {/* Primary Mission Settings */}
        <section className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div className="bg-white p-6 rounded-3xl shadow-sm border border-azure-pale space-y-6">
            <div className="flex items-center gap-2 border-b border-azure-pale pb-4">
              <Settings className="text-azure-dark" size={20} />
              <h2 className="text-lg font-bold text-neutral-dark capitalize">General Parameters</h2>
            </div>

            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-bold text-azure-mid capitalize">Disaster type</label>
                <div className="grid grid-cols-3 gap-2">
                  {['typhoon', 'earthquake', 'tsunami', 'fire', 'flash_flood', 'default'].map((type) => (
                    <button
                      key={type}
                      disabled={type !== 'default'}
                      onClick={() => setLocalConfig({ ...localConfig, disasterType: type as any })}
                      className={`px-4 py-2.5 rounded-xl text-[11px] font-bold capitalize transition-all border ${localConfig.disasterType === type
                        ? 'bg-azure-dark text-white border-azure-dark shadow-md'
                        : 'bg-mint-bg text-azure-dark border-azure-pale hover:border-azure-mid'
                        } ${type !== 'default' ? 'opacity-40 cursor-not-allowed' : ''}`}
                    >
                      {type.replace('_', ' ')}
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-bold text-azure-mid capitalize">Layout (Scenario)</label>
                <select
                  value={localConfig.scenario}
                  onChange={(e) => setLocalConfig({ ...localConfig, scenario: e.target.value })}
                  className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2.5 text-sm font-medium outline-none focus:ring-2 focus:ring-azure-mid/20 transition-all"
                >
                  {['downtown', 'suburban', 'industrial', 'coastal', 'mixed urban', 'mountain outpost'].map(s => (
                    <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          <div className="bg-white p-6 rounded-3xl shadow-sm border border-azure-pale space-y-6">
            <div className="flex items-center gap-2 border-b border-azure-pale pb-4">
              <Sparkles className="text-azure-dark" size={20} />
              <h2 className="text-lg font-bold text-neutral-dark capitalize">Swarm & Population</h2>
            </div>

            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-sm font-bold text-azure-mid capitalize">Survivors (1-20)</label>
                <input
                  type="number"
                  min="1"
                  max="20"
                  value={localConfig.survivors}
                  onChange={(e) => {
                    const val = parseInt(e.target.value);
                    if (isNaN(val)) return;
                    setLocalConfig({ ...localConfig, survivors: Math.max(1, Math.min(20, val)) });
                  }}
                  className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2.5 text-sm font-bold outline-none focus:ring-2 focus:ring-azure-mid/20"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-bold text-azure-mid capitalize">Drone count (3-5)</label>
                <input
                  type="number"
                  min="3"
                  max="5"
                  value={localConfig.droneCount}
                  onChange={(e) => {
                    const val = parseInt(e.target.value);
                    if (isNaN(val)) return;
                    setLocalConfig({ ...localConfig, droneCount: Math.max(3, Math.min(5, val)) });
                  }}
                  className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2.5 text-sm font-bold outline-none focus:ring-2 focus:ring-azure-mid/20"
                />
              </div>
              <div className="space-y-2 col-span-2">
                <label className="text-sm font-bold text-azure-mid capitalize">Obstacle density</label>
                <div className="flex gap-2">
                  {['low', 'med', 'high'].map(d => (
                    <button
                      key={d}
                      onClick={() => setLocalConfig({ ...localConfig, obstacleDensity: d as any })}
                      className={`flex-1 py-2.5 rounded-xl text-sm font-bold capitalize transition-all border ${localConfig.obstacleDensity === d
                        ? 'bg-azure-dark text-white border-azure-dark'
                        : 'bg-mint-bg text-azure-dark border-azure-pale hover:border-azure-mid'
                      }`}
                    >
                      {d}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Environmental Unknowns Section */}
        <section className="bg-white p-8 rounded-3xl shadow-sm border border-azure-pale space-y-8">
          <div className="flex items-center gap-3 border-b border-azure-pale pb-4">
            <Activity className="text-azure-dark" size={24} />
            <div>
              <h2 className="text-xl font-bold text-neutral-dark capitalize">Environmental Unknowns</h2>
              <p className="text-xs text-azure-mid font-medium">Configure disaster-specific dynamic variables</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8">
            {localConfig.disasterType === 'typhoon' && (
              <>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-azure-mid capitalize">Wind speed (km/h)</label>
                  <input type="number" value={localConfig.windSpeed} onChange={(e) => setLocalConfig({ ...localConfig, windSpeed: parseInt(e.target.value) })} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2.5 text-sm font-medium outline-none" />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-azure-mid capitalize">Wind direction</label>
                  <select value={localConfig.windDirection} onChange={(e) => setLocalConfig({ ...localConfig, windDirection: e.target.value })} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2.5 text-sm font-medium outline-none">
                    {['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'].map(d => <option key={d} value={d}>{d}</option>)}
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-azure-mid capitalize">Rainfall rate (mm/h)</label>
                  <input type="number" value={localConfig.rainfall} onChange={(e) => setLocalConfig({ ...localConfig, rainfall: parseInt(e.target.value) })} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2.5 text-sm font-medium outline-none" />
                </div>
              </>
            )}

            {localConfig.disasterType === 'earthquake' && (
              <>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-azure-mid capitalize">Aftershock probability (%)</label>
                  <input type="number" value={localConfig.aftershockProb} onChange={(e) => setLocalConfig({ ...localConfig, aftershockProb: parseInt(e.target.value) })} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2.5 text-sm font-medium outline-none" />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-azure-mid capitalize">Collapse risk (%)</label>
                  <input type="number" value={localConfig.collapseRisk} onChange={(e) => setLocalConfig({ ...localConfig, collapseRisk: parseInt(e.target.value) })} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2.5 text-sm font-medium outline-none" />
                </div>
              </>
            )}

            {localConfig.disasterType === 'tsunami' && (
              <>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-azure-mid capitalize">Water flow (m/s)</label>
                  <input type="number" value={localConfig.waterFlow} onChange={(e) => setLocalConfig({ ...localConfig, waterFlow: parseInt(e.target.value) })} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2.5 text-sm font-medium outline-none" />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-azure-mid capitalize">Water level (m)</label>
                  <input type="number" value={localConfig.waterLevel} onChange={(e) => setLocalConfig({ ...localConfig, waterLevel: parseInt(e.target.value) })} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2.5 text-sm font-medium outline-none" />
                </div>
              </>
            )}

            {localConfig.disasterType === 'fire' && (
              <>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-azure-mid capitalize">Spread rate (m/min)</label>
                  <input type="number" value={localConfig.fireSpread} onChange={(e) => setLocalConfig({ ...localConfig, fireSpread: parseInt(e.target.value) })} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2.5 text-sm font-medium outline-none" />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-azure-mid capitalize">Smoke density (%)</label>
                  <input type="number" value={localConfig.smokeDensity} onChange={(e) => setLocalConfig({ ...localConfig, smokeDensity: parseInt(e.target.value) })} className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-2.5 text-sm font-medium outline-none" />
                </div>
              </>
            )}

            {localConfig.disasterType === 'default' && (
              <div className="col-span-full text-center py-12 bg-mint-bg/50 rounded-2xl border border-dashed border-azure-pale">
                <p className="text-azure-mid italic text-sm font-medium">No specific unknowns for the default scenario.</p>
              </div>
            )}
          </div>
        </section>
      </main>

      <footer className="bg-white border-t border-azure-pale px-8 py-6 text-center text-[11px] text-azure-mid font-medium">
        Rescue Mission Control Protocol v2.4 | Autonomous Agent Orchestration System
      </footer>
    </div>
  );
};

