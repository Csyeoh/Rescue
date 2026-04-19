import React from 'react';
import { motion } from 'motion/react';
import { Settings, Sliders, Drone, Map as MapIcon, RefreshCcw, Download } from 'lucide-react';
import { MissionConfig } from '../../types';
import { ConfigRow } from '../Config/ConfigPage';

interface SidebarConfigProps {
  config: MissionConfig;
  isGenerating: boolean;
  onEditConfig: () => void;
  onResetSimulation: () => void;
  onDownloadLogs: () => void;
}

export const SidebarConfig: React.FC<SidebarConfigProps> = ({
  config,
  onEditConfig,
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
              <ConfigRow label="Swarm size" icon={<Drone size={16} />} value={config.droneCount} />
              <ConfigRow label="Layout" icon={<MapIcon size={16} />} value="Static (map.txt)" />
            </div>
          </div>

          <div className="pt-4 space-y-2 border-t border-azure-pale">
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
