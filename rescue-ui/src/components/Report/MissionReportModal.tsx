import React from 'react';
import { motion } from 'motion/react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { CoverageStatsCell, MissionReport } from '../../types';

interface MissionReportModalProps {
  report: MissionReport;
  onClose: () => void;
}

export const MissionReportModal: React.FC<MissionReportModalProps> = ({ report, onClose }) => {
  const overlapPct = typeof report.thermal_overlap_pct === 'number' ? report.thermal_overlap_pct : null;
  const overlapCells = typeof report.overlap_cells_unique === 'number' ? report.overlap_cells_unique : null;
  const thermalCells = typeof report.thermal_cells_unique === 'number' ? report.thermal_cells_unique : null;
  const totalSurvivors = typeof report.total_survivors === 'number' ? report.total_survivors : null;

  const maxCoverageCells = 1600;
  const idealEnergy = 0.5;

  const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

  const rescuedRatio = clamp01(
    (totalSurvivors ?? report.survivors_found) > 0
      ? report.survivors_found / (totalSurvivors ?? report.survivors_found)
      : 1
  );
  const coverageRatio = clamp01((report.coverage_percentage ?? 0) / 100);
  const maxAuc = Math.max(1, (report.mission_duration_ticks ?? 0) * maxCoverageCells);
  const velocityRatio = clamp01((report.discovery_auc ?? 0) / maxAuc);
  const overlapRatio = clamp01((report.thermal_overlap_pct ?? 0) / 100);
  const energyRatio = report.energy_efficiency > 0 ? idealEnergy / report.energy_efficiency : 0;

  const rescuePoints = rescuedRatio * 25;
  const coveragePoints = coverageRatio * 15;
  const velocityPoints = velocityRatio * 30;
  const overlapPoints = (1 - overlapRatio) * 15;
  const energyPoints = clamp01(energyRatio) * 15;

  const sisRaw = rescuePoints + coveragePoints + velocityPoints + overlapPoints + energyPoints;
  const sis = Math.max(0, Math.min(100, Math.round(sisRaw)));

  const tier =
    sis >= 90 ? 'S-Tier (Flawless AI Routing)'
    : sis >= 80 ? 'A-Tier (Highly Efficient)'
    : sis >= 70 ? 'B-Tier (Acceptable)'
    : sis >= 60 ? 'C-Tier (Inefficient)'
    : 'F-Tier (Swarm logic failure)';

  const tierColor =
    sis >= 90 ? 'text-emerald-400'
    : sis >= 80 ? 'text-sky-400'
    : sis >= 70 ? 'text-yellow-300'
    : sis >= 60 ? 'text-orange-400'
    : 'text-red-400';

  const gridSize = 40;
  const coverageStats = Array.isArray(report.coverage_stats) ? report.coverage_stats : [];
  const hasCoverageStats = coverageStats.length > 0;
  const statsMap = new Map<string, CoverageStatsCell>();
  for (const cell of coverageStats) {
    statsMap.set(`${cell.x},${cell.y}`, cell);
  }

  const getHeatColor = (total: number) => {
    if (total <= 0) return 'rgba(0,0,0,0)';
    if (total === 1) return 'rgba(34,197,94,0.45)';
    if (total === 2) return 'rgba(245,158,11,0.55)';
    return 'rgba(239,68,68,0.60)';
  };

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
        <div className="bg-slate-900 px-6 py-4 flex justify-between items-start text-white gap-4">
          <div>
            <h2 className="text-xl font-bold">Post-Mission Debrief</h2>
            <p className="text-sm text-slate-300">Telemetry & Swarm Efficiency Analysis</p>
          </div>
          <div className="flex items-start gap-4">
            <div className="text-right leading-tight">
              <div className="text-[11px] uppercase tracking-wider text-slate-300">Swarm Intelligence Score</div>
              <div className="text-3xl font-extrabold">{sis}</div>
              <div className={`text-xs font-semibold ${tierColor}`}>{tier}</div>
            </div>
            <button onClick={onClose} className="text-slate-400 hover:text-white px-3 py-1 bg-slate-800 rounded">
              Close
            </button>
          </div>
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

            <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
              <p className="text-sm text-slate-500 font-medium uppercase tracking-wider">Thermal / Vision Overlap</p>
              <p className="text-3xl font-bold text-rose-600">
                {overlapPct === null ? '—' : `${overlapPct.toFixed(1)}%`}
              </p>
              <p className="text-xs text-slate-500 mt-1">
                {overlapCells === null || thermalCells === null
                  ? 'How much thermal scanning overlapped already-seen (vision) area.'
                  : `${overlapCells} / ${thermalCells} thermal-scanned cells overlapped vision coverage.`}
              </p>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
               <div className="bg-slate-50 p-3 rounded-xl border border-slate-200 text-center">
                  <p className="text-xs text-slate-500 uppercase">Coverage</p>
                  <p className="text-xl font-bold text-slate-800">{report.coverage_percentage}%</p>
               </div>
               <div className="bg-slate-50 p-3 rounded-xl border border-slate-200 text-center">
                  <p className="text-xs text-slate-500 uppercase">Rescued</p>
                  <p className="text-xl font-bold text-slate-800">
                    {totalSurvivors === null ? report.survivors_found : `${report.survivors_found}/${totalSurvivors}`}
                  </p>
               </div>
            </div>
          </div>

          {/* Area Under Curve Chart */}
          <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 p-4 flex flex-col">
            <h3 className="text-sm font-bold text-slate-800 mb-4 uppercase tracking-wider">Area Under Curve (Discovery Velocity)</h3>
            <div className="h-[320px] w-full min-w-0">
              <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={320}>
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

            {hasCoverageStats ? (
              <div className="mt-5">
                <h3 className="text-sm font-bold text-slate-800 mb-3 uppercase tracking-wider">Overlap Heatmap (Vision + Thermal Visits)</h3>
                <div className="relative h-[260px] w-full overflow-hidden rounded-xl border border-slate-200 bg-white">
                  <svg
                    className="h-full w-full"
                    viewBox={`0 0 ${gridSize} ${gridSize}`}
                    preserveAspectRatio="none"
                  >
                    {Array.from({ length: gridSize }).flatMap((_, y) =>
                      Array.from({ length: gridSize }).map((__, x) => {
                        const cell = statsMap.get(`${x},${y}`);
                        const total = cell ? cell.physical_visits + cell.thermal_scans : 0;
                        const sy = gridSize - 1 - y;
                        return (
                          <rect
                            key={`${x}-${y}`}
                            x={x}
                            y={sy}
                            width={1}
                            height={1}
                            fill={getHeatColor(total)}
                            stroke="rgba(148,163,184,0.25)"
                            strokeWidth={0.06}
                            shapeRendering="crispEdges"
                          />
                        );
                      })
                    )}
                  </svg>
                </div>
                <div className="flex justify-center mt-2 space-x-6 text-xs text-slate-500">
                  <span className="flex items-center"><div className="w-3 h-3 rounded-sm mr-2" style={{ background: 'rgba(34,197,94,0.45)' }}></div> 1 visit</span>
                  <span className="flex items-center"><div className="w-3 h-3 rounded-sm mr-2" style={{ background: 'rgba(245,158,11,0.55)' }}></div> 2 visits</span>
                  <span className="flex items-center"><div className="w-3 h-3 rounded-sm mr-2" style={{ background: 'rgba(239,68,68,0.6)' }}></div> 3+ visits</span>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
};
