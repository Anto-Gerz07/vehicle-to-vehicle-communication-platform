import type { PacketLogEntry, PerformanceMetrics } from '../lib/types';
import { EventType } from '../lib/types';

const EVENT_COLORS: Record<number, string> = {
  0: "text-zinc-500", 1: "text-amber-400", 2: "text-orange-400",
  3: "text-orange-300", 4: "text-rose-500", 5: "text-orange-400",
  6: "text-rose-500", 7: "text-rose-400"
};

const EVENT_NAMES: Record<number, string> = {
  0: "NORMAL", 1: "OVERSPEED", 2: "HARSH_BRAKING",
  3: "SUDDEN_SLOWDOWN", 4: "ACCIDENT", 5: "HAZARD",
  6: "EMERGENCY_STOP", 7: "COLLISION_WARN"
};

const PRIORITY_BADGE: Record<number, string> = {
  0: "bg-rose-500/20 text-rose-400 border border-rose-500/50 shadow-[0_0_10px_rgba(225,29,72,0.2)]",
  1: "bg-orange-500/20 text-orange-400 border border-orange-500/50",
  2: "bg-amber-500/20 text-amber-400 border border-amber-500/50",
  3: "bg-zinc-800 text-zinc-400 border border-zinc-700"
};

interface PacketLogProps {
  entries: PacketLogEntry[];
  metrics: PerformanceMetrics;
  neighborTableB: Record<string, { speed: number; acceleration: number; event: EventType; timestamp: number }>;
}

export function PacketLog({ entries, metrics, neighborTableB }: PacketLogProps) {
  const lossRate = metrics.packetsSent > 0
    ? (((metrics.packetsSent - metrics.packetsReceived) / metrics.packetsSent) * 100).toFixed(1)
    : "0.0";

  return (
    <div className="flex flex-col gap-4 h-full">
      {/* Metrics */}
      <div className="bg-zinc-900/60 backdrop-blur-lg border border-zinc-800/50 rounded-2xl p-5 shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 right-0 p-4 opacity-10"><span className="text-4xl">📊</span></div>
        <h3 className="text-[10px] font-black text-zinc-400 font-mono mb-4 tracking-[0.2em] relative z-10">PERFORMANCE METRICS</h3>
        <div className="grid grid-cols-2 gap-3 text-xs font-mono relative z-10">
          <div className="bg-zinc-950/50 rounded-xl p-3 border border-zinc-800/50">
            <div className="text-zinc-500 tracking-wider text-[10px] uppercase font-bold mb-1">Sent</div>
            <div className="text-zinc-100 font-black text-lg">{metrics.packetsSent}</div>
          </div>
          <div className="bg-zinc-950/50 rounded-xl p-3 border border-zinc-800/50">
            <div className="text-zinc-500 tracking-wider text-[10px] uppercase font-bold mb-1">Received</div>
            <div className="text-emerald-400 font-black text-lg drop-shadow-[0_0_5px_rgba(52,211,153,0.5)]">{metrics.packetsReceived}</div>
          </div>
          <div className="bg-zinc-950/50 rounded-xl p-3 border border-zinc-800/50">
            <div className="text-zinc-500 tracking-wider text-[10px] uppercase font-bold mb-1">Stale</div>
            <div className="text-amber-400 font-black text-lg">{metrics.stalePackets}</div>
          </div>
          <div className="bg-zinc-950/50 rounded-xl p-3 border border-zinc-800/50">
            <div className="text-zinc-500 tracking-wider text-[10px] uppercase font-bold mb-1">Loss Rate</div>
            <div className="text-rose-400 font-black text-lg drop-shadow-[0_0_5px_rgba(244,63,94,0.5)]">{lossRate}%</div>
          </div>
          <div className="bg-zinc-950/50 rounded-xl p-3 border border-zinc-800/50 col-span-2 flex justify-between items-center">
            <div className="text-zinc-500 tracking-wider text-[10px] uppercase font-bold">Avg Latency</div>
            <div className="text-cyan-400 font-black text-lg tracking-wider drop-shadow-[0_0_5px_rgba(34,211,238,0.5)]">{metrics.avgLatencyMs} <span className="text-xs font-bold text-zinc-600">ms</span></div>
          </div>
        </div>
      </div>

      {/* Neighbor Table (Vehicle B's view) */}
      <div className="bg-zinc-900/60 backdrop-blur-lg border border-zinc-800/50 rounded-2xl p-5 shadow-2xl">
        <h3 className="text-[10px] font-black text-zinc-400 font-mono mb-4 tracking-[0.2em]">NEIGHBOR TABLE (VEH-B)</h3>
        <div className="bg-zinc-950/50 rounded-xl overflow-hidden border border-zinc-800/50">
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="text-zinc-500 border-b border-zinc-800/80 bg-zinc-900/50 text-[10px] tracking-wider uppercase">
                <th className="text-left py-2 px-3">ID</th>
                <th className="text-right py-2 px-3">Speed</th>
                <th className="text-right py-2 px-3">Accel</th>
                <th className="text-right py-2 px-3">Age</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(neighborTableB).map(([id, v]) => {
                const ageMs = Date.now() - v.timestamp * 1000;
                const isStale = ageMs > 500;
                return (
                  <tr key={id} className={`border-b border-zinc-800/50 last:border-0 hover:bg-zinc-800/30 transition-colors ${isStale ? "text-amber-500" : "text-zinc-300"}`}>
                    <td className="py-2 px-3 font-bold text-zinc-100">{id}</td>
                    <td className="text-right py-2 px-3">{Math.round(v.speed)}</td>
                    <td className="text-right py-2 px-3">{v.acceleration.toFixed(1)}</td>
                    <td className="text-right py-2 px-3 font-bold">{ageMs < 1000 ? `${ageMs}ms` : `${(ageMs/1000).toFixed(1)}s`}</td>
                  </tr>
                );
              })}
              {Object.keys(neighborTableB).length === 0 && (
                <tr><td colSpan={4} className="text-zinc-600 text-center py-4 font-black tracking-widest text-[10px] uppercase">No neighbors</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Live Packet Log */}
      <div className="bg-zinc-900/60 backdrop-blur-lg border border-zinc-800/50 rounded-2xl p-5 shadow-2xl flex-1 overflow-hidden flex flex-col relative">
        <div className="absolute top-0 right-0 p-4 opacity-10"><span className="text-4xl">📡</span></div>
        <h3 className="text-[10px] font-black text-zinc-400 font-mono mb-4 tracking-[0.2em] relative z-10">LIVE PACKET LOG</h3>
        <div className="bg-zinc-950/50 rounded-xl border border-zinc-800/50 overflow-hidden flex flex-col flex-1 relative z-10">
          <div className="overflow-y-auto flex-1 p-2 space-y-[1px] text-[10px] font-mono">
            {[...entries].reverse().slice(0, 30).map((e) => {
              const d = new Date(e.timestamp * 1000);
              const ts = `${d.getHours().toString().padStart(2,"0")}:${d.getMinutes().toString().padStart(2,"0")}:${d.getSeconds().toString().padStart(2,"0")}`;
              return (
                <div key={e.id} className="flex items-center gap-2 py-1 px-2 rounded hover:bg-zinc-800/50 transition-colors">
                  <span className="text-zinc-600 shrink-0 font-bold">{ts}</span>
                  <span className="text-cyan-400 shrink-0 font-black tracking-wider">{e.fromId}→{e.toId}</span>
                  <span className={`shrink-0 font-bold tracking-wide ${EVENT_COLORS[e.event]}`}>{EVENT_NAMES[e.event]}</span>
                  <span className={`ml-auto px-1.5 py-0.5 rounded font-black tracking-wider shrink-0 ${PRIORITY_BADGE[e.priority]}`}>
                    P{e.priority}
                  </span>
                  <span className="text-zinc-600 shrink-0 font-bold">#{e.seq.toString().padStart(4,"0")}</span>
                </div>
              );
            })}
            {entries.length === 0 && <div className="text-zinc-600 text-center py-8 font-black tracking-widest uppercase">Waiting for packets...</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
