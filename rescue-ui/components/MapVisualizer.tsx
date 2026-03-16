// Consistent palette for up to 6 drones
const DRONE_ZONE_COLORS: Record<string, string> = {
  drone_1: "rgba(59, 130, 246, 0.25)",   // blue
  drone_2: "rgba(234, 179, 8, 0.25)",    // yellow
  drone_3: "rgba(168, 85, 247, 0.25)",   // purple
  drone_4: "rgba(239, 68, 68, 0.25)",    // red
  drone_5: "rgba(34, 197, 94, 0.25)",    // green
  drone_6: "rgba(249, 115, 22, 0.25)",   // orange
};

const DRONE_DOT_COLORS: Record<string, string> = {
  drone_1: "#3b82f6",
  drone_2: "#eab308",
  drone_3: "#a855f7",
  drone_4: "#ef4444",
  drone_5: "#22c55e",
  drone_6: "#f97316",
};

export default function MapVisualizer({ worldState }: any) {
  const { terrain, drones, survivors } = worldState;

  const renderCell = (x: number, y: number, isGroundTruth: boolean) => {
    const cellTerrain = terrain?.find((t: any) => t.x === x && t.y === y);
    
    let bgColor = "rgb(31, 41, 55)";
    let isObstacleVisible = false;
    let zoneOverlay: string | null = null;

    if (cellTerrain) {
        if (cellTerrain.is_obstacle && (isGroundTruth || cellTerrain.obstacle_discovered)) {
            isObstacleVisible = true;
            bgColor = "black";
        } else {
            const opacity = Math.min(1.0, 0.2 + (cellTerrain.altitude / 100.0) * 0.8);
            if (cellTerrain.terrain_type === 'multiple_story') {
                bgColor = `rgba(185, 28, 28, ${opacity})`;
            } else if (cellTerrain.terrain_type === 'single_story') {
                bgColor = `rgba(249, 115, 22, ${opacity})`;
            } else {
                bgColor = `rgba(22, 163, 74, ${opacity})`;
            }
        }
        // Show drone zone overlay only on the Question Plane (right panel)
        if (!isGroundTruth && cellTerrain.assigned_drone) {
          zoneOverlay = DRONE_ZONE_COLORS[cellTerrain.assigned_drone] ?? "rgba(255,255,255,0.1)";
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
        title={cellTerrain ? `Alt: ${cellTerrain.altitude.toFixed(1)}m${cellTerrain.building_height > 0 ? ` | Height: ${cellTerrain.building_height.toFixed(1)}m` : ''} | Type: ${cellTerrain.terrain_type}${cellTerrain.assigned_drone ? ` | Zone: ${cellTerrain.assigned_drone}` : ''}` : ""}
      >
        {zoneOverlay && <div className="absolute inset-0 z-5" style={{ backgroundColor: zoneOverlay }} />}
        {isObstacleVisible && <div className="absolute inset-0 border border-gray-600 shadow-inner z-10" />}
        {isBaseCamp && <div className="absolute inset-0 bg-green-500/40 animate-pulse z-20 shadow-[0_0_15px_rgba(34,197,94,0.8)]" />}
        {isSurvivorVisible && (
          <div className="absolute inset-0 flex items-center justify-center z-30">
            <div className={`w-3/4 h-3/4 rounded-full ${survivor?.discovered ? 'bg-yellow-300 shadow-[0_0_10px_rgba(253,224,71,1)]' : 'bg-yellow-600 opacity-90'}`} />
          </div>
        )}
        {drone && (
          <div className="absolute inset-0 flex items-center justify-center z-40 animate-bounce" title={`Drone ${drone.id} (${drone.battery}%)`}>
             <div 
               className="w-4/5 h-4/5 rounded-full border border-blue-300"
               style={{ backgroundColor: DRONE_DOT_COLORS[drone.id] ?? "#3b82f6", boxShadow: `0 0 10px ${DRONE_DOT_COLORS[drone.id] ?? "#3b82f6"}` }}
             />
          </div>
        )}
      </div>
    );
  };

  // Collect unique drones that have zones to build legend
  const assignedDrones = Array.from(
    new Set((terrain ?? []).map((t: any) => t.assigned_drone).filter(Boolean))
  ) as string[];

  return (
    <div className="flex flex-col flex-grow">
      <div className="flex gap-8 mb-4 bg-gray-900 border border-gray-700 px-6 py-3 rounded-lg shadow-2xl w-full justify-center items-center">
         <div className="text-center">
             <p className="text-[10px] text-gray-400 uppercase tracking-widest mb-1">Rescue Progress</p>
             <p className="text-2xl font-bold text-yellow-400">
                {survivors?.filter((s: any) => s.discovered).length || 0} / {survivors?.length || 0}
             </p>
         </div>
      </div>

      <div className="flex gap-8 justify-center items-start">
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

          <div className="flex flex-col gap-6 bg-gray-900 border border-gray-800 p-5 rounded-lg shadow-xl mt-8">
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-widest border-b border-gray-700 pb-2">Altitude Scale</h3>
            <div>
              <p className="text-xs text-red-500 mb-1.5 font-semibold">Multiple Story (Red)</p>
              <div className="h-4 w-32 rounded bg-gradient-to-r from-red-600/20 to-red-600 border border-red-900"></div>
              <div className="flex justify-between text-[10px] text-gray-500 mt-1.5 font-mono">
                <span>20m</span>
                <span>100m+</span>
              </div>
            </div>
            <div>
              <p className="text-xs text-orange-500 mb-1.5 font-semibold">Single Story (Orange)</p>
              <div className="h-4 w-32 rounded bg-gradient-to-r from-orange-500/20 to-orange-500 border border-orange-900"></div>
              <div className="flex justify-between text-[10px] text-gray-500 mt-1.5 font-mono">
                <span>3m</span>
                <span>10m</span>
              </div>
            </div>
            <div>
              <p className="text-xs text-green-400 mb-1.5 font-semibold">Terrain (Green)</p>
              <div className="h-4 w-32 rounded bg-gradient-to-r from-green-600/20 to-green-600 border border-green-900"></div>
              <div className="flex justify-between text-[10px] text-gray-500 mt-1.5 font-mono">
                <span>1m</span>
                <span>100m+</span>
              </div>
            </div>
            {assignedDrones.length > 0 && (
              <>
                <h3 className="text-xs font-bold text-gray-400 uppercase tracking-widest border-b border-gray-700 pb-2 mt-2">Drone Zones</h3>
                {assignedDrones.map((d) => (
                  <div key={d} className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-sm border border-gray-600" style={{ backgroundColor: DRONE_DOT_COLORS[d] ?? "#fff" }} />
                    <span className="text-xs text-gray-300 capitalize">{d.replace("_", " ")}</span>
                  </div>
                ))}
              </>
            )}
          </div>
      </div>

      <div className="flex justify-center gap-6 mt-6 text-xs font-semibold uppercase tracking-wide text-gray-400 bg-gray-900 px-6 py-3 rounded-full border border-gray-800 max-w-4xl mx-auto">
        <div className="flex items-center gap-2"><div className="w-3 h-3 bg-red-600 rounded-sm"></div> Multi-Story</div>
        <div className="flex items-center gap-2"><div className="w-3 h-3 bg-orange-500 rounded-sm"></div> Single-Story</div>
        <div className="flex items-center gap-2"><div className="w-3 h-3 bg-green-600 rounded-sm"></div> Terrain</div>
        <div className="flex items-center gap-2"><div className="w-3 h-3 bg-black border border-gray-600 rounded-sm"></div> Obstacle</div>
        <div className="flex items-center gap-2"><div className="w-3 h-3 bg-yellow-400 rounded-full"></div> Survivor</div>
      </div>
    </div>
  );
}

