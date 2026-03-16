export default function TelemetryPanel({ drones, survivors, terrain }: any) {
  return (
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
  );
}
