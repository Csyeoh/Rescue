import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Settings, Activity, ArrowLeft, Save, Sparkles, Loader2, Cpu } from 'lucide-react';
import { MissionConfig } from '../../types';
import { useToast } from '../UI/Toast';

interface ConfigPageProps {
  config: MissionConfig;
  onSave: (c: MissionConfig) => void | Promise<void>;
  onCancel: () => void;
  isGenerating?: boolean;
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

export const ConfigPage: React.FC<ConfigPageProps> = ({ config, onSave, onCancel, isGenerating = false }) => {
  const [localConfig, setLocalConfig] = useState<MissionConfig>(config);
  const { showToast } = useToast();

  const handleSave = () => {
    onSave(localConfig);
  };

  return (
    <div className="h-screen w-screen bg-mint-bg overflow-y-auto custom-scrollbar flex flex-col relative">
      {/* Loading Overlay */}
      <AnimatePresence>
        {isGenerating && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 z-[100] bg-white/80 backdrop-blur-xl flex flex-col items-center justify-center space-y-6"
          >
            <div className="relative">
              <motion.div 
                animate={{ rotate: 360 }}
                transition={{ repeat: Infinity, duration: 2, ease: "linear" }}
                className="w-24 h-24 border-4 border-azure-pale border-t-azure-dark rounded-full shadow-2xl shadow-azure-dark/20"
              />
              <div className="absolute inset-0 flex items-center justify-center">
                <Cpu className="text-azure-dark animate-pulse" size={32} />
              </div>
            </div>
            <div className="text-center space-y-2">
              <h2 className="text-2xl font-bold text-neutral-dark animate-pulse tracking-tight">AI Mapping Disaster Zone...</h2>
              <p className="text-azure-mid font-medium text-sm max-w-xs mx-auto">
                Gemini is designing a structured urban blueprint based on your parameters.
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

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
          <motion.button
            whileHover={!isGenerating ? { scale: 1.02 } : {}}
            whileTap={!isGenerating ? { scale: 0.98 } : {}}
            onClick={handleSave}
            disabled={isGenerating}
            className={`bg-azure-dark text-white px-8 py-2.5 rounded-xl font-bold shadow-lg shadow-azure-dark/20 transition-all flex items-center gap-2 ${isGenerating ? 'opacity-80 cursor-wait' : 'hover:bg-azure-dark/90'}`}
          >
            {isGenerating ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                <motion.span
                  animate={{ opacity: [0.4, 1, 0.4] }}
                  transition={{ repeat: Infinity, duration: 1.5 }}
                >
                  Generating...
                </motion.span>
              </>
            ) : (
              <>
                <Save size={18} />
                <span>Save Configuration</span>
              </>
            )}
          </motion.button>
        </div>
      </header>

      <main className="flex-1 max-w-2xl mx-auto w-full p-8 space-y-8">
        <section className="bg-white p-6 rounded-3xl shadow-sm border border-azure-pale space-y-6">
          <div className="flex items-center gap-3 border-b border-azure-pale pb-4">
            <Sparkles className="text-azure-dark" size={24} />
            <div>
              <h2 className="text-lg font-bold text-neutral-dark capitalize">Swarm Deployment Payload</h2>
              <p className="text-xs text-azure-mid font-medium">The disaster zone layout is secured. Configure agent swarm forces.</p>
            </div>
          </div>

          <div className="space-y-3">
            <label className="text-sm font-bold text-azure-mid capitalize">Agents deployed (Drones)</label>
            <input
              type="number"
              min="1"
              max="10"
              value={localConfig.droneCount}
              onChange={(e) => {
                const val = parseInt(e.target.value);
                if (isNaN(val)) return;
                setLocalConfig({ ...localConfig, droneCount: Math.max(1, Math.min(10, val)) });
              }}
              className="w-full bg-mint-bg border border-azure-pale rounded-xl px-4 py-3 text-lg font-bold text-neutral-dark outline-none focus:ring-2 focus:ring-azure-mid/20 transition-all"
            />
          </div>
        </section>
      </main>

      <footer className="bg-white border-t border-azure-pale px-8 py-6 text-center text-[11px] text-azure-mid font-medium">
        Rescue Mission Control Protocol v2.4 | Autonomous Agent Orchestration System
      </footer>
    </div>
  );
};

