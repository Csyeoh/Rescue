import React from 'react';
import { motion } from 'motion/react';
import { Settings, Sliders, Users, Drone, ShieldAlert, Waves, Activity, Droplets, Map as MapIcon, RefreshCcw, Download } from 'lucide-react';
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
      <div className="bg-white p-6 rounded-2xl shadow-sm border border-azure-pale/50 flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Settings className="text-azure-dark" size={20} />
            <h2 className="font-bold text-neutral-dark capitalize text-base">Mission parameters</h2>
          </div>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={onEditConfig}
            className="p-2.5 bg-azure-pale/30 hover:bg-azure-pale/50 text-azure-dark rounded-xl transition-colors border border-azure-pale/50 group"
            title="Edit Mission Parameters"
          >
            <Sliders size={16} className="group-hover:rotate-12 transition-transform" />
          </motion.button>
        </div>

        <div className="space-y-6">
          <div className="space-y-3">
            <h3 className="text-[12px] font-bold text-azure-mid/60 tracking-widest border-b border-azure-pale pb-1">Current Configuration</h3>
            <div className="space-y-1">
              <ConfigRow label="Scenario" icon={<MapIcon size={16} />} value={config.scenario} />
              <ConfigRow label="Survivors" icon={<Users size={16} />} value={config.survivors} />
              <ConfigRow label="Swarm size" icon={<Drone size={16} />} value={config.droneCount} />
              <ConfigRow label="Obstacles" icon={<ShieldAlert size={16} />} value={config.obstacleDensity} />
              <ConfigRow label="Disaster" icon={<Waves size={16} />} value={config.disasterType} />
            </div>
          </div>

          <div className="space-y-3">
            <h3 className="text-[12px] font-bold text-azure-mid/60 tracking-widest border-b border-azure-pale pb-1">Environmental Unknowns</h3>
            <div className="space-y-1">
              {config.disasterType === 'typhoon' && (
                <>
                  <ConfigRow label="Wind speed" icon={<Activity size={16} />} value={`${config.windSpeed} km/h`} />
                  <ConfigRow label="Direction" icon={<Activity size={16} />} value={config.windDirection} />
                  <ConfigRow label="Rainfall" icon={<Droplets size={16} />} value={`${config.rainfall} mm/h`} />
                </>
              )}
              {config.disasterType === 'earthquake' && (
                <>
                  <ConfigRow label="Aftershock" icon={<Activity size={16} />} value={`${config.aftershockProb}%`} />
                  <ConfigRow label="Collapse risk" icon={<ShieldAlert size={16} />} value={`${config.collapseRisk}%`} />
                </>
              )}
              {config.disasterType === 'tsunami' && (
                <>
                  <ConfigRow label="Flow velocity" icon={<Waves size={16} />} value={`${config.waterFlow} m/s`} />
                  <ConfigRow label="Water level" icon={<Droplets size={16} />} value={`${config.waterLevel} m`} />
                </>
              )}
              {config.disasterType === 'fire' && (
                <>
                  <ConfigRow label="Spread rate" icon={<Activity size={16} />} value={`${config.fireSpread} m/min`} />
                  <ConfigRow label="Smoke density" icon={<Activity size={16} />} value={`${config.smokeDensity}%`} />
                </>
              )}
              {config.disasterType === 'flash_flood' && (
                <>
                  <ConfigRow label="Rising speed" icon={<Droplets size={16} />} value={`${config.risingSpeed} m/h`} />
                  <ConfigRow label="Water level" icon={<Droplets size={16} />} value={`${config.waterLevel} m`} />
                </>
              )}
              {config.disasterType === 'default' && (
                <div className="text-[12px] font-medium text-azure-mid italic py-2">No active unknowns</div>
              )}
            </div>
          </div>

          <div className="pt-4 space-y-2 border-t border-azure-pale">
            <motion.button
              whileHover={!isGenerating ? { x: 3 } : {}}
              whileTap={!isGenerating ? { scale: 0.98 } : {}}
              onClick={onGenerateMap}
              disabled={isGenerating}
              className={`w-full flex items-center justify-center gap-2 bg-azure-dark text-white py-3 rounded-xl font-bold text-xs shadow-lg shadow-azure-dark/10 transition-all ${isGenerating ? 'opacity-80 cursor-wait' : 'hover:bg-azure-dark/90'}`}
            >
              {isGenerating ? (
                <>
                  <RefreshCcw size={14} className="animate-spin" />
                  <motion.span
                    animate={{ opacity: [0.4, 1, 0.4] }}
                    transition={{ repeat: Infinity, duration: 1.5 }}
                  >
                    Generating...
                  </motion.span>
                </>
              ) : (
                <>
                  <MapIcon size={14} />
                  <span>Generate map</span>
                </>
              )}
            </motion.button>


            <motion.button
              whileHover={{ x: 3 }}
              whileTap={{ scale: 0.98 }}
              onClick={onResetSimulation}
              className="w-full flex items-center justify-center gap-2 bg-white text-alert-red border border-alert-red/20 py-3 rounded-xl font-bold text-sm hover:bg-alert-red/5 transition-all"
            >
              <RefreshCcw size={16} />
              Reset mission
            </motion.button>

            <motion.button
              whileHover={{ x: 3 }}
              whileTap={{ scale: 0.98 }}
              onClick={onDownloadLogs}
              className="w-full flex items-center justify-center gap-2 bg-mint-bg text-azure-dark border border-azure-pale py-3 rounded-xl font-bold text-sm hover:border-azure-mid transition-all"
            >
              <Download size={16} />
              Export logs
            </motion.button>
          </div>
        </div>
      </div>
    </aside>
  );
};

