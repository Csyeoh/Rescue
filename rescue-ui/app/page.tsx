"use client";
import { useEffect, useState } from "react";

export default function Dashboard() {
  const [worldState, setWorldState] = useState(null);

  // Poll the FastAPI server every 500ms
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
    return <div className="p-10 text-white">Connecting to Drone Swarm API...</div>;
  }

  // Find this line inside Dashboard()
  const { grid, drones, survivors, logs } = worldState;

  // Helper to check what is in a specific cell
  const getCellContent = (x, y) => {
    // 1. Check for Base Camp
    if (x === 0 && y === 0) return <div className="w-full h-full bg-green-600 rounded-sm animate-pulse" title="Base Camp" />;
    
    // 2. Check for Drones
    const drone = drones.find((d) => d.x === x && d.y === y);
    if (drone) return <div className="w-full h-full bg-blue-500 rounded-full shadow-[0_0_10px_rgba(59,130,246,0.8)]" title={`Drone ${drone.id} (${drone.battery}%)`} />;
    
    // 3. Check for Survivors
    const survivor = survivors.find((s) => s.x === x && s.y === y);
    if (survivor) {
      return survivor.discovered 
        ? <div className="w-full h-full bg-yellow-400 rounded-sm" title="Survivor (Found!)" />
        : <div className="w-full h-full bg-red-600 rounded-sm" title="Survivor (Hidden)" />;
    }

    // Default empty grid cell
    return <div className="w-full h-full bg-gray-800 rounded-sm border border-gray-700" />;
  };

  return (
    <main className="min-h-screen bg-gray-950 p-8 flex flex-col items-center font-sans">
      <h1 className="text-3xl font-bold text-white mb-6 tracking-wider">
        SWARM CONTROL <span className="text-blue-500">NEXUS</span>
      </h1>
      
      {/* The 20x20 Grid */}
      <div 
        className="grid gap-1 bg-gray-900 p-2 rounded-lg border border-gray-700 shadow-2xl"
        style={{ 
          gridTemplateColumns: `repeat(${grid.width}, minmax(0, 1fr))`,
          width: "600px", 
          height: "600px" 
        }}
      >
        {Array.from({ length: grid.height }).map((_, y) => (
          Array.from({ length: grid.width }).map((_, x) => (
            <div key={`${x}-${y}`} className="relative w-full h-full">
              {getCellContent(x, y)}
            </div>
          ))
        ))}
      </div>

      {/* Legend */}
      <div className="flex gap-6 mt-6 text-sm text-gray-400">
        <div className="flex items-center gap-2"><div className="w-4 h-4 bg-green-600 rounded-sm"></div> Base Camp</div>
        <div className="flex items-center gap-2"><div className="w-4 h-4 bg-blue-500 rounded-full"></div> Active Drone</div>
        <div className="flex items-center gap-2"><div className="w-4 h-4 bg-red-600 rounded-sm"></div> Hidden Survivor</div>
        <div className="flex items-center gap-2"><div className="w-4 h-4 bg-yellow-400 rounded-sm"></div> Found Survivor</div>
      </div>

      {/* Live Mission Log Terminal */}
      <div className="w-[600px] mt-8 bg-black border border-gray-700 rounded-lg shadow-2xl overflow-hidden">
        <div className="bg-gray-800 px-4 py-2 border-b border-gray-700 flex justify-between items-center">
          <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Mission Action Log</h2>
          <div className="flex gap-2">
            <div className="w-3 h-3 rounded-full bg-red-500"></div>
            <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
            <div className="w-3 h-3 rounded-full bg-green-500"></div>
          </div>
        </div>
        <div className="h-48 overflow-y-auto p-4 font-mono text-sm space-y-2 flex flex-col-reverse">
          {logs && logs.map((log, i) => (
            <div key={i} className="flex gap-3 text-gray-300">
              <span className="text-gray-500 whitespace-nowrap">[{log.time.split(' ')[1]}]</span>
              <span className="text-blue-400 font-bold whitespace-nowrap">{log.drone}:</span>
              <span className="text-green-400">{log.message}</span>
            </div>
          ))}
        </div>
      </div>
      
    </main>
  );
}