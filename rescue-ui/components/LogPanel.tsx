export default function LogPanel({ logs }: any) {
  return (
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
  );
}
