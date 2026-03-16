"use client";
import { useEffect, useState, useRef } from "react";

import ConfigPanel from "../components/ConfigPanel";
import MapVisualizer from "../components/MapVisualizer";
import LogPanel from "../components/LogPanel";
import TelemetryPanel from "../components/TelemetryPanel";

export default function Dashboard() {
  const [worldState, setWorldState] = useState<any>({
    grid: { width: 20, height: 20 },
    terrain: [],
    drones: [],
    survivors: [],
    logs: []
  });
  const [isGenerating, setIsGenerating] = useState(false);
  const [isPreview, setIsPreview] = useState(false);
  const [mapData, setMapData] = useState<any>(null);
  const [partitioningStatus, setPartitioningStatus] = useState<{ active: boolean; message: string }>({
    active: false,
    message: "",
  });

  const wsRef = useRef<WebSocket | null>(null);

  const [config, setConfig] = useState({
    scenario: "downtown",
    num_drones: 3,
    drone_battery: 100,
    num_survivors: 5,
    obstacle_difficulty: "med"
  });

  // WebSocket listener for real-time backend events
  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket("ws://localhost:8000/ws");
      wsRef.current = ws;

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === "partitioning_start") {
          setIsPreview(false);
          setPartitioningStatus({ active: true, message: msg.payload.message });
        } else if (msg.type === "partitioning_complete") {
          setPartitioningStatus({ active: false, message: "" });
          setWorldState(msg.payload);
        }
      };

      ws.onclose = () => {
        // Auto-reconnect after 2s
        setTimeout(connect, 2000);
      };
    };
    connect();
    return () => wsRef.current?.close();
  }, []);

  const handleDeploySwarm = async () => {
    try {
      const { scenario, ...restConfig } = config;
      const deployConfig = { ...restConfig, map_data: mapData };
      const response = await fetch("http://localhost:8000/api/start_mission", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(deployConfig),
      });

      const result = await response.json();
      console.log("Mission Status:", result);
      setIsPreview(false);
    } catch (error) {
      console.error("Failed to connect to Nexus Core:", error);
      alert("Failed to start simulation. Check FastAPI server.");
    }
  };

  const handleGenerateMap = async (useRandom = false) => {
    setIsGenerating(true);
    let currentConfig = { ...config };
    
    if (useRandom) {
      const obstacleDiffs = ["low", "med", "high"];
      const scenarios = ["downtown", "suburban", "industrial", "coastal", "mixed"];
      
      currentConfig = {
        ...currentConfig,
        scenario: scenarios[Math.floor(Math.random() * scenarios.length)], 
        num_drones: Math.floor(Math.random() * 3) + 3,
        num_survivors: Math.floor(Math.random() * 12) + 4, 
        obstacle_difficulty: obstacleDiffs[Math.floor(Math.random() * obstacleDiffs.length)]
      };
      setConfig(currentConfig);
    }

    try {
      const { num_drones, ...mapGenConfig } = currentConfig;
      const response = await fetch("http://localhost:8000/api/generate_map", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(mapGenConfig),
      });

      const result = await response.json();
      console.log("Map Generation Status:", result);
      
      if (result.map_data) {
        setIsPreview(true);
        setMapData(result.map_data);
        
        const previewState = {
          grid: { width: 20, height: 20 },
          terrain: result.map_data.cells.map((c: any) => ({ ...c, obstacle_discovered: false })),
          drones: Array.from({length: currentConfig.num_drones}).map((_, i) => ({ id: `drone_${i+1}`, x: 9, y: 9, battery: 100 })),
          survivors: result.map_data.blueprint.survivors.map((s: any, i: number) => ({ id: `survivor_${i+1}`, x: s.x, y: s.y, discovered: false })),
          logs: [{ time: new Date().toISOString().split('T')[1].substring(0,8), drone: "SYSTEM", message: "Map preview generated. Awaiting deployment." }]
        };
        setWorldState(previewState);
        setConfig({ ...currentConfig });
      } else {
        alert(result.message || "Failed to generate map.");
      }
    } catch (error) {
      console.error("Failed to connect to Nexus Core:", error);
      alert("Failed to generate map. Check FastAPI server.");
    }
    setIsGenerating(false);
  };


  const { terrain, drones, survivors, logs } = worldState;

  return (
    <main className="min-h-screen bg-gray-950 p-6 flex flex-col font-sans pb-20 relative">
      <div className="flex w-full max-w-[1400px] mx-auto">
        <ConfigPanel 
          config={config} 
          setConfig={setConfig} 
          isGenerating={isGenerating} 
          partitioningStatus={partitioningStatus}
          handleGenerateMap={handleGenerateMap} 
          handleDeploySwarm={handleDeploySwarm} 
        />
        <MapVisualizer worldState={worldState} />
      </div>

      <LogPanel logs={logs} />
      <TelemetryPanel drones={drones} survivors={survivors} terrain={terrain} />
    </main>
  );
}
