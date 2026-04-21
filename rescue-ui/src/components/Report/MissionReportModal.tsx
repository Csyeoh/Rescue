import React from 'react';
import { motion } from 'framer-motion';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { MissionReport } from '../../types';

interface MissionReportModalProps {
  report: MissionReport;
  onClose: () => void;
}

export const MissionReportModal: React.FC<MissionReportModalProps> = ({ report, onClose }) => {
  return (
    <motion.div 
      initial={{ opacity: 0 }} 
      animate={{ opacity: 1 }} 
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4"
    >
      <motion.div 
        initial={{ y: 50, scale: 0.95 }}
        animate={{ y: 0, scale: 1 }}
        className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl overflow-hidden border border-slate-200"
      >
        {/* Header */}
        <div className="bg-slate-900 px-6 py-4 flex justify-between items-center text-white">
          <div>
            <h2 className="text-xl font-bold">Post-Mission Debrief</h2>
            <p className="text-sm text-slate-300">Telemetry & Swarm Efficiency Analysis</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white px-3 py-1 bg-slate-800 rounded">
            Close
          </button>
        </div>

        <div className="p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Key Metrics Panel */}
          <div className="lg:col-span-1 space-y-4">
            <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
              <p className="text-sm text-slate-500 font-medium uppercase tracking-wider">Discovery AUC</p>
              <p className="text-3xl font-bold text-emerald-600">
                {report.discovery_auc.toLocaleString()} <span className="text-sm text-slate-400 font-normal">units</span>
              </p>
              <p className="text-xs text-slate-500 mt-1">Higher AUC means faster initial map coverage.</p>
            </div>

            <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
              <p className="text-sm text-slate-500 font-medium uppercase tracking-wider">Mean Time to Discovery</p>
              <p className="text-3xl font-bold text-blue-600">
                {report.mean_time_to_discovery} <span className="text-sm text-slate-400 font-normal">ticks</span>
              </p>
              <p className="text-xs text-slate-500 mt-1">Average time taken to locate a survivor.</p>
            </div>

            <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
              <p className="text-sm text-slate-500 font-medium uppercase tracking-wider">Energy Efficiency</p>
              <p className="text-3xl font-bold text-amber-600">
                {report.energy_efficiency} <span className="text-sm text-slate-400 font-normal">bat/cell</span>
              </p>
              <p className="text-xs text-slate-500 mt-1">Battery units consumed per grid cell revealed.</p>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
               <div className="bg-slate-50 p-3 rounded-xl border border-slate-200 text-center">
                  <p className="text-xs text-slate-500 uppercase">Coverage</p>
                  <p className="text-xl font-bold text-slate-800">{report.coverage_percentage}%</p>
               </div>
               <div className="bg-slate-50 p-3 rounded-xl border border-slate-200 text-center">
                  <p className="text-xs text-slate-500 uppercase">Rescued</p>
                  <p className="text-xl font-bold text-slate-800">{report.survivors_found}</p>
               </div>
            </div>
          </div>

          {/* Area Under Curve Chart */}
          <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 p-4 flex flex-col">
            <h3 className="text-sm font-bold text-slate-800 mb-4 uppercase tracking-wider">Area Under Curve (Discovery Velocity)</h3>
            <div className="flex-1 min-h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={report.chart_data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorCoverage" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                  <XAxis dataKey="tick" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip 
                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                    labelStyle={{ fontWeight: 'bold', color: '#0f172a' }}
                  />
                  <Area 
                    type="monotone" 
                    dataKey="coverage" 
                    stroke="#10b981" 
                    strokeWidth={3}
                    fillOpacity={1} 
                    fill="url(#colorCoverage)" 
                    name="Area Covered"
                  />
                  {/* Map survivor discovery points as vertical lines */}
                  {report.chart_data.map((point, index) => {
                     // Check if survivors found increased at this tick
                     const prev = index > 0 ? report.chart_data[index-1].survivors : 0;
                     if (point.survivors > prev) {
                        return (
                           <ReferenceLine key={index} x={point.tick} stroke="#ef4444" strokeDasharray="3 3" />
                        );
                     }
                     return null;
                  })}
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="flex justify-center mt-2 space-x-6 text-xs text-slate-500">
               <span className="flex items-center"><div className="w-3 h-3 bg-emerald-500 rounded-sm mr-2 opacity-50"></div> Area Covered</span>
               <span className="flex items-center"><div className="w-3 h-[2px] bg-red-500 border-t border-dashed mr-2"></div> Survivor Found</span>
            </div>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
};