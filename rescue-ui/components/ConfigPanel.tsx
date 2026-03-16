import { useState, useEffect } from "react";

export default function ConfigPanel({
  config,
  setConfig,
  isGenerating,
  partitioningStatus,
  handleGenerateMap,
  handleDeploySwarm
}: any) {
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const handleDroneChange = (e: any) => {
    let val = e.target.value;
    setConfig({...config, num_drones: val});
    
    if (val !== "" && (parseInt(val) < 3 || parseInt(val) > 5)) {
      showToast("Range: 3 - 5");
    }
  };

  const handleSurvivorChange = (e: any) => {
    let val = e.target.value;
    setConfig({...config, num_survivors: val});
    
    if (val !== "" && (parseInt(val) < 1 || parseInt(val) > 20)) {
      showToast("Range: 1 - 20");
    }
  };
  return (
    <div className="w-72 mr-8 flex-shrink-0">
      <h1 className="text-2xl font-bold text-white mb-6 tracking-wider">
        SWARM <span className="text-blue-500">NEXUS</span>
      </h1>
      
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 shadow-xl text-white">
        <h2 className="text-lg font-bold mb-4 text-cyan-400 border-b border-gray-700 pb-2 flex justify-between items-center">
          Mission Setup
          {isGenerating && <span className="text-xs text-yellow-400 animate-pulse">Architecting...</span>}
          {partitioningStatus?.active && <span className="text-xs text-cyan-400 animate-pulse">Partitioning...</span>}
        </h2>
        <p className="text-xs text-gray-500 mb-4 uppercase tracking-widest">Fixed 20x20 Grid</p>
        
        <div className="mb-4">
          <label className="block text-sm mb-1 text-gray-400">Layout Scenario</label>
          <select 
            value={config.scenario}
            onChange={(e) => setConfig({...config, scenario: e.target.value})}
            className="w-full bg-gray-800 p-2 rounded border border-gray-700 focus:border-cyan-500 focus:outline-none text-white text-sm"
          >
            <option value="downtown">Downtown Commercial</option>
            <option value="suburban">Suburban Neighborhood</option>
            <option value="industrial">Industrial Warehouse</option>
            <option value="coastal">Coastal Urban</option>
            <option value="mixed">Mixed Urban</option>
          </select>
        </div>

        <div className="mb-4">
          <label className="block text-sm mb-1 text-gray-400">Drone Count</label>
          <input 
            type="number" min="3" max="5"
            value={config.num_drones} 
            onChange={handleDroneChange}
            className="w-full bg-gray-800 p-2 rounded border border-gray-700 focus:border-cyan-500 focus:outline-none"
          />
        </div>

        <div className="mb-4">
          <label className="block text-sm mb-1 text-gray-400">Hidden Survivors</label>
          <input 
            type="number" min="1" max="20"
            value={config.num_survivors} 
            onChange={handleSurvivorChange}
            className="w-full bg-gray-800 p-2 rounded border border-gray-700 focus:border-cyan-500 focus:outline-none"
          />
        </div>

        <div className="mb-4">
          <label className="block text-sm mb-1 text-gray-400">Obstacle Density</label>
          <select 
            value={config.obstacle_difficulty}
            onChange={(e) => setConfig({...config, obstacle_difficulty: e.target.value})}
            className="w-full bg-gray-800 p-2 rounded border border-gray-700 focus:border-cyan-500 focus:outline-none text-white"
          >
            <option value="low">Low (5%)</option>
            <option value="med">Medium (10%)</option>
            <option value="high">High (15%)</option>
          </select>
        </div>


        <div className="flex flex-col gap-3">
          <button 
            onClick={() => handleGenerateMap(false)}
            disabled={isGenerating}
            className={`w-full font-bold py-2 px-4 rounded transition-colors shadow-lg tracking-wide text-sm border ${isGenerating ? 'bg-gray-800 border-gray-700 text-gray-500' : 'bg-gray-800 hover:bg-gray-700 text-cyan-400 border-cyan-900'}`}
          >
            {isGenerating ? "GENERATING AI MAP..." : "GENERATE MAP (CURRENT CONFIG)"}
          </button>

          <button 
            onClick={() => handleGenerateMap(true)}
            disabled={isGenerating}
            className={`w-full font-bold py-2 px-4 rounded transition-colors shadow-lg tracking-wide text-xs border flex items-center justify-center gap-2 ${isGenerating ? 'bg-gray-800 border-gray-700 text-gray-500' : 'bg-purple-600 hover:bg-purple-500 text-white border-purple-400/30'}`}
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.59-9.21l-5.44-5.44"/></svg>
            {isGenerating ? "GENERATING AI MAP..." : "GENERATE RANDOM MAP"}
          </button>

          <button 
            onClick={handleDeploySwarm}
            disabled={isGenerating}
            className={`w-full mt-2 font-bold py-3 px-4 rounded transition-colors shadow-lg tracking-wide ${isGenerating ? 'bg-gray-700 text-gray-400' : 'bg-cyan-600 hover:bg-cyan-500 text-white shadow-cyan-900/50'}`}
          >
            DEPLOY SWARM
          </button>
        </div>
        
        {toast && (
          <div className="fixed bottom-10 left-10 bg-red-600 text-white px-6 py-3 rounded shadow-2xl z-50 animate-bounce">
            {toast}
          </div>
        )}
      </div>
    </div>
  );
}
