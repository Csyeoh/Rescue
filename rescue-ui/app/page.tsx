"use client";
import { useEffect, useState } from "react";

export default function Dashboard() {
  const [worldState, setWorldState] = useState<any>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  
  const [config, setConfig] = useState({
    scenario: "A dense residential area near a steep hill.",
    flood_type: "Flash Flood", // NEW
    num_drones: 2,
    drone_battery: 100,
    num_survivors: 5,
    obstacle_difficulty: "med",
    sim_difficulty: "easy"
  });

  const handleDeploySwarm = async () => {
    setIsGenerating(true);
    try {
      const response = await fetch("http://localhost:8000/api/start_mission", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });

      const result = await response.json();
      console.log("Mission Status:", result);
    } catch (error) {
      console.error("Failed to connect to Nexus Core:", error);
      alert("Failed to start simulation. Check FastAPI server.");
    }
    setIsGenerating(false);
  };

  const handleRandomDeploy = async () => {
    setIsGenerating(true);
    const obstacleDiffs = ["low", "med", "high"];
    const simDiffs = ["easy", "hard"];
    const floodTypes = ["River (Monsoon) Flood", "Flash Flood", "Storm Surge", "Dam Break"]; // NEW
    
    const randomConfig = {
      scenario: "", 
      flood_type: floodTypes[Math.floor(Math.random() * floodTypes.length)], // NEW
      num_drones: Math.floor(Math.random() * 5) + 2,
      drone_battery: 100,
      num_survivors: Math.floor(Math.random() * 12) + 4, 
      obstacle_difficulty: obstacleDiffs[Math.floor(Math.random() * obstacleDiffs.length)],
      sim_difficulty: simDiffs[Math.floor(Math.random() * simDiffs.length)]
    };

    setConfig(randomConfig);

    try {
      const response = await fetch("http://localhost:8000/api/start_mission", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(randomConfig),
      });

      const result = await response.json();
      console.log("Random Mission Status:", result);
    } catch (error) {
      console.error("Failed to connect to Nexus Core:", error);
      alert("Failed to start simulation. Check FastAPI server.");
    }
    setIsGenerating(false);
  };

  useEffect(() => {
    const fetchState = async () => {
      try {
        const res = await fetch("http://localhost:8000/state");
        const data = await res.json();
        setWorldState(data);
      } catch (error) {
        console.error("Failed to fetch world state. Is FastAPI running?", error);
      }
    };
    const interval = setInterval(fetchState, 500);
    return () => clearInterval(interval);
  }, []);

  if (!worldState) {
    return <div className="p-10 text-white flex justify-center items-center min-h-screen bg-gray-950">Connecting to Drone Swarm API...</div>;
  }

  if (worldState.error || !worldState.grid) {
    return (
      <div className="p-10 text-white flex flex-col justify-center items-center min-h-screen bg-gray-950">
        <h2 className="text-2xl font-bold text-red-500 mb-2">Simulation Offline</h2>
        <p className="text-gray-400">Waiting for deployment configuration...</p>
        <p className="text-xs text-gray-600 mt-4">Backend Status: {worldState.error || "Awaiting initialization"}</p>
      </div>
    );
  }

  const { grid, terrain, drones, survivors, logs, environment } = worldState;

  const renderCell = (x: number, y: number, isGroundTruth: boolean) => {
    const cellTerrain = terrain?.find((t: any) => t.x === x && t.y === y);
    
    let bgColor = "rgb(31, 41, 55)";
    let isObstacleVisible = false;

    if (cellTerrain) {
        if (cellTerrain.is_obstacle && (isGroundTruth || cellTerrain.obstacle_discovered)) {
            isObstacleVisible = true;
            bgColor = "black";
        } else {
            const opacity = Math.min(1.0, 0.2 + (cellTerrain.altitude / 10) * 0.8);
            bgColor = cellTerrain.terrain_type === 'building' 
                ? `rgba(220, 38, 38, ${opacity})`
                : `rgba(22, 163, 74, ${opacity})`;
        }
    }

    const isBaseCamp = x === 9 && y === 9;
    const drone = drones?.find((d: any) => d.x === x && d.y === y);
    const survivor = survivors?.find((s: any) => s.x === x && s.y === y);
    const isSurvivorVisible = survivor && (isGroundTruth || survivor.discovered);

    return (
      <div 
        className="w-full h-full relative" 
        style={{ backgroundColor: bgColor }} 
        title={cellTerrain ? `Alt: ${cellTerrain.altitude.toFixed(1)}m | Type: ${cellTerrain.terrain_type}` : ""}
      >
        {/* Layer 1: Water (Calculated dynamically on the UI side!) */}
        {cellTerrain && environment?.global_water_level > cellTerrain.altitude && !isObstacleVisible && (
          <div className="absolute inset-0 bg-cyan-600 pointer-events-none" 
               style={{ opacity: 0.3 + (Math.min(environment.global_water_level - cellTerrain.altitude, 5) / 5) * 0.7 }} />
        )}
        {isObstacleVisible && <div className="absolute inset-0 border border-gray-600 shadow-inner z-10" />}
        {isBaseCamp && <div className="absolute inset-0 bg-green-500/40 animate-pulse z-20 shadow-[0_0_15px_rgba(34,197,94,0.8)]" />}
        {isSurvivorVisible && (
          <div className="absolute inset-0 flex items-center justify-center z-30">
            <div className={`w-3/4 h-3/4 rounded-full ${survivor.discovered ? 'bg-yellow-300 shadow-[0_0_10px_rgba(253,224,71,1)]' : 'bg-yellow-600 opacity-90'}`} />
          </div>
        )}
        {drone && (
          <div className="absolute inset-0 flex items-center justify-center z-40 animate-bounce" title={`Drone ${drone.id} (${drone.battery}%)`}>
             <div className="w-4/5 h-4/5 bg-blue-500 rounded-full shadow-[0_0_10px_rgba(59,130,246,0.9)] border border-blue-300" />
          </div>
        )}
      </div>
    );
  };

  return (
    <main className="min-h-screen bg-gray-950 p-6 flex flex-col font-sans pb-20">
      <div className="flex w-full max-w-[1400px] mx-auto">
        
        {/* LEFT COLUMN: Configuration Panel */}
        <div className="w-72 mr-8 flex-shrink-0">
          <h1 className="text-2xl font-bold text-white mb-6 tracking-wider">
            SWARM <span className="text-blue-500">NEXUS</span>
          </h1>
          
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 shadow-xl text-white">
            <h2 className="text-lg font-bold mb-4 text-cyan-400 border-b border-gray-700 pb-2 flex justify-between items-center">
              Mission Setup
              {isGenerating && <span className="text-xs text-yellow-400 animate-pulse">Architecting...</span>}
            </h2>
            <p className="text-xs text-gray-500 mb-4 uppercase tracking-widest">Fixed 20x20 Grid</p>
            
            <div className="mb-4">
              <label className="block text-sm mb-1 text-gray-400">Drone Count</label>
              <input 
                type="number" min="1" max="10"
                value={config.num_drones || ""} 
                onChange={(e) => setConfig({...config, num_drones: parseInt(e.target.value)})}
                className="w-full bg-gray-800 p-2 rounded border border-gray-700 focus:border-cyan-500 focus:outline-none"
              />
            </div>

            <div className="mb-4">
              <label className="block text-sm mb-1 text-gray-400">Hidden Survivors</label>
              <input 
                type="number" min="1" max="20"
                value={config.num_survivors || ""} 
                onChange={(e) => setConfig({...config, num_survivors: parseInt(e.target.value)})}
                className="w-full bg-gray-800 p-2 rounded border border-gray-700 focus:border-cyan-500 focus:outline-none"
              />
            </div>

            <div className="mb-4">
              <label className="block text-[10px] mb-1 text-gray-400 uppercase tracking-wider">Flood Type</label>
              <select 
                value={config.flood_type}
                onChange={(e) => setConfig({...config, flood_type: e.target.value})}
                className="w-full bg-gray-800 p-2 rounded border border-gray-700 focus:border-cyan-500 focus:outline-none text-sm text-white font-semibold"
              >
                <option value="River (Monsoon) Flood">River (Monsoon) Flood</option>
                <option value="Flash Flood">Flash Flood</option>
                <option value="Storm Surge">Storm Surge</option>
                <option value="Dam Break">Dam Break</option>
              </select>
            </div>

            <div className="mb-4">
              <label className="block text-sm mb-1 text-gray-400">Obstacle Density</label>
              <select 
                value={config.obstacle_difficulty}
                onChange={(e) => setConfig({...config, obstacle_difficulty: e.target.value})}
                className="w-full bg-gray-800 p-2 rounded border border-gray-700 focus:border-cyan-500 focus:outline-none text-white"
              >
                <option value="low">Low (5%)</option>
                <option value="med">Medium (15%)</option>
                <option value="high">High (25%)</option>
              </select>
            </div>

            <div className="mb-6">
              <label className="block text-sm mb-1 text-gray-400">Simulation Difficulty</label>
              <select 
                value={config.sim_difficulty}
                onChange={(e) => setConfig({...config, sim_difficulty: e.target.value})}
                className="w-full bg-gray-800 p-2 rounded border border-gray-700 focus:border-cyan-500 focus:outline-none text-white"
              >
                <option value="easy">Standard (Random Spawns)</option>
                <option value="hard">Hard (Survivors at Edges)</option>
              </select>
            </div>

            <div className="flex flex-col gap-3">
              <button 
                onClick={handleDeploySwarm}
                disabled={isGenerating}
                className={`w-full font-bold py-3 px-4 rounded transition-colors shadow-lg tracking-wide ${isGenerating ? 'bg-gray-700 text-gray-400' : 'bg-cyan-600 hover:bg-cyan-500 text-white shadow-cyan-900/50'}`}
              >
                {isGenerating ? "GENERATING AI MAP..." : "DEPLOY SWARM"}
              </button>

              <button 
                onClick={handleRandomDeploy}
                disabled={isGenerating}
                className={`w-full font-bold py-2 px-4 rounded transition-colors shadow-lg tracking-wide text-xs border flex items-center justify-center gap-2 ${isGenerating ? 'bg-gray-800 border-gray-700 text-gray-500' : 'bg-purple-600 hover:bg-purple-500 text-white border-purple-400/30'}`}
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.59-9.21l-5.44-5.44"/></svg>
                {isGenerating ? "GENERATING AI MAP..." : "QUICK RANDOM DEPLOY"}
              </button>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: Dual Visualizers */}
        <div className="flex flex-col flex-grow">
          
          <div className="flex gap-8 mb-4 bg-gray-900 border border-gray-700 px-6 py-3 rounded-lg shadow-2xl w-full justify-center items-center">
             <div className="text-center">
                 <p className="text-[10px] text-gray-400 uppercase tracking-widest mb-1">Initial Base Water Level</p>
                 <p className="text-2xl font-bold text-cyan-400">{environment?.global_water_level?.toFixed(2) || "0.00"}m</p>
             </div>
             
             <div className="h-8 w-px bg-gray-700"></div>
             
             <div className="text-center">
                 <p className="text-[10px] text-gray-400 uppercase tracking-widest mb-1">Rising Speed</p>
                 <p className="text-2xl font-bold text-blue-400">+{environment?.water_speed?.toFixed(4) || "0.0000"}m/tick</p>
             </div>
             
             <div className="h-8 w-px bg-gray-700"></div>
             
             {/* NEW: Rescue Progress Tracker */}
             <div className="text-center">
                 <p className="text-[10px] text-gray-400 uppercase tracking-widest mb-1">Rescue Progress</p>
                 <p className="text-2xl font-bold text-yellow-400">
                    {survivors?.filter((s: any) => s.discovered).length || 0} / {survivors?.length || 0}
                 </p>
             </div>
          </div>

          <div className="flex gap-8 justify-center items-start">
              {/* GRID 1: ANSWER PLANE */}
              <div>
                  <h3 className="text-center text-sm font-bold text-gray-400 uppercase tracking-widest mb-2">
                    Answer Plane <span className="text-purple-400">(Ground Truth)</span>
                  </h3>
                  <div 
                    className="grid gap-px bg-gray-900 p-1.5 rounded-lg border border-purple-900 shadow-[0_0_15px_rgba(168,85,247,0.2)] relative"
                    style={{ gridTemplateColumns: `repeat(20, minmax(0, 1fr))`, width: "420px", height: "420px" }}
                  >
                    {Array.from({ length: 20 }).map((_, y) => (
                      Array.from({ length: 20 }).map((_, x) => (
                        <div key={`ans-${x}-${y}`} className="relative w-full h-full overflow-hidden">
                          {renderCell(x, y, true)}
                        </div>
                      ))
                    ))}
                  </div>
              </div>

              {/* GRID 2: QUESTION PLANE */}
              <div>
                  <h3 className="text-center text-sm font-bold text-gray-400 uppercase tracking-widest mb-2">
                    Question Plane <span className="text-cyan-400">(Drone View)</span>
                  </h3>
                  <div 
                    className="grid gap-px bg-gray-900 p-1.5 rounded-lg border border-cyan-900 shadow-[0_0_15px_rgba(34,211,238,0.2)] relative"
                    style={{ gridTemplateColumns: `repeat(20, minmax(0, 1fr))`, width: "420px", height: "420px" }}
                  >
                    {Array.from({ length: 20 }).map((_, y) => (
                      Array.from({ length: 20 }).map((_, x) => (
                        <div key={`que-${x}-${y}`} className="relative w-full h-full overflow-hidden">
                          {renderCell(x, y, false)}
                        </div>
                      ))
                    ))}
                  </div>
              </div>

              {/* ALTITUDE COLOR SCALE */}
              <div className="flex flex-col gap-6 bg-gray-900 border border-gray-800 p-5 rounded-lg shadow-xl mt-8">
                <h3 className="text-xs font-bold text-gray-400 uppercase tracking-widest border-b border-gray-700 pb-2">Altitude Scale</h3>
                <div>
                  <p className="text-xs text-red-400 mb-1.5 font-semibold">Building (Red)</p>
                  <div className="h-4 w-32 rounded bg-gradient-to-r from-red-600/20 to-red-600 border border-red-900"></div>
                  <div className="flex justify-between text-[10px] text-gray-500 mt-1.5 font-mono">
                    <span>1m</span>
                    <span>10m</span>
                  </div>
                </div>
                <div>
                  <p className="text-xs text-green-400 mb-1.5 font-semibold">Terrain (Green)</p>
                  <div className="h-4 w-32 rounded bg-gradient-to-r from-green-600/20 to-green-600 border border-green-900"></div>
                  <div className="flex justify-between text-[10px] text-gray-500 mt-1.5 font-mono">
                    <span>1m</span>
                    <span>10m</span>
                  </div>
                </div>
              </div>
          </div>

          <div className="flex justify-center gap-6 mt-6 text-xs font-semibold uppercase tracking-wide text-gray-400 bg-gray-900 px-6 py-3 rounded-full border border-gray-800 max-w-2xl mx-auto">
            <div className="flex items-center gap-2"><div className="w-3 h-3 bg-red-600 rounded-sm"></div> Building</div>
            <div className="flex items-center gap-2"><div className="w-3 h-3 bg-green-600 rounded-sm"></div> Terrain</div>
            <div className="flex items-center gap-2"><div className="w-3 h-3 bg-black border border-gray-600 rounded-sm"></div> Obstacle</div>
            <div className="flex items-center gap-2"><div className="w-3 h-3 bg-yellow-400 rounded-full"></div> Survivor</div>
          </div>

        </div>
      </div>

      {/* MASSIVE ACTION LOG FOR AI REASONING */}
      <div className="w-full max-w-[1400px] mx-auto mt-10 bg-black border border-gray-800 rounded-lg shadow-2xl overflow-hidden font-mono">
        <div className="bg-gray-900 px-6 py-3 border-b border-gray-800 flex justify-between items-center">
          <h2 className="text-sm font-bold text-gray-400 uppercase tracking-widest">AI Swarm Action & Reasoning Log</h2>
        </div>
        <div className="h-64 overflow-y-auto p-6 text-sm space-y-3 flex flex-col-reverse bg-black/50 custom-scrollbar">
          {logs && logs.map((log: any, i: number) => (
            <div key={i} className="flex gap-4 text-gray-300 hover:bg-gray-900/50 p-2 rounded transition-colors break-words border-l-2 border-cyan-500/30">
              <span className="text-gray-500 whitespace-nowrap">[{log.time.split(' ')[1]}]</span>
              <span className="text-cyan-500 font-bold whitespace-nowrap w-20">{log.drone}:</span>
              <span className="text-green-400 leading-relaxed">{log.message}</span>
            </div>
          ))}
        </div>
      </div>

      {/* BOTTOM SECTION: Backend Telemetry Inspector (3 Columns) */}
      <div className="w-full max-w-[1400px] mx-auto mt-6 bg-gray-900 border border-gray-700 rounded-lg p-6 shadow-xl text-white font-mono text-sm">
        <h2 className="text-lg font-bold text-purple-400 mb-4 border-b border-gray-800 pb-2 uppercase tracking-widest">
          Backend Telemetry Inspector (God Mode)
        </h2>
        
        <div className="grid grid-cols-3 gap-8">
          <div>
            <h3 className="text-blue-400 font-bold mb-2 flex justify-between">
              <span>Drones</span>
              <span className="text-gray-500">({drones?.length || 0})</span>
            </h3>
            <pre className="bg-black border border-gray-800 p-4 rounded overflow-y-auto h-48 text-xs text-blue-200 custom-scrollbar">
              {JSON.stringify(drones, null, 2)}
            </pre>
          </div>

          <div>
             <h3 className="text-yellow-400 font-bold mb-2 flex justify-between">
              <span>Survivors</span>
              <span className="text-gray-500">({survivors?.length || 0})</span>
            </h3>
             <pre className="bg-black border border-gray-800 p-4 rounded overflow-y-auto h-48 text-xs text-yellow-200 custom-scrollbar">
              {JSON.stringify(survivors, null, 2)}
            </pre>
          </div>

          <div>
             <h3 className="text-gray-400 font-bold mb-2 flex justify-between">
              <span>Obstacles</span>
              <span className="text-gray-500">({terrain?.filter((t: any) => t.is_obstacle).length || 0})</span>
            </h3>
             <pre className="bg-black border border-gray-800 p-4 rounded overflow-y-auto h-48 text-xs text-gray-300 custom-scrollbar">
              {JSON.stringify(
                terrain?.filter((t: any) => t.is_obstacle).map((t: any) => ({ x: t.x, y: t.y, altitude: t.altitude.toFixed(1) })), 
                null, 2
              )}
            </pre>
          </div>
        </div>
      </div>
      
    </main>
  );
}