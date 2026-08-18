import { EventType, RiskLevel } from '../lib/types';

const EVENT_NAMES: Record<number, string> = {
  0: "NORMAL", 1: "OVERSPEED", 2: "HARSH BRAKING",
  3: "SUDDEN SLOWDOWN", 4: "ACCIDENT", 5: "HAZARD AHEAD",
  6: "EMERGENCY STOP", 7: "COLLISION WARNING"
};



interface OledDisplayProps {
  vehicleId: string;
  speed: number;
  neighborsCount: number;
  risk: RiskLevel;
  ttc: number | null;
  event: EventType | null;
  confidence?: number;
  stale?: boolean;
}

export function OledDisplay({ vehicleId, speed, neighborsCount, risk, ttc, event, confidence = 100, stale = false }: OledDisplayProps) {
  const evName = event !== null ? EVENT_NAMES[event] ?? "UNKNOWN" : "";
  const ttcStr = ttc !== null && ttc !== Infinity ? `${ttc.toFixed(1)}s` : "—";

  // Buzzer: animated ring based on risk
  const buzzerClass =
    risk === RiskLevel.CRITICAL ? "w-3 h-3 bg-red-500 rounded-full animate-ping" :
    risk === RiskLevel.WARNING  ? "w-3 h-3 bg-orange-500 rounded-full animate-bounce" :
    risk === RiskLevel.CAUTION  ? "w-3 h-3 bg-yellow-400 rounded-full animate-pulse" :
    "w-3 h-3 bg-gray-600 rounded-full";

  const borderColor =
    risk === RiskLevel.CRITICAL ? "border-red-500/50 shadow-[0_0_30px_rgba(239,68,68,0.3)_inset,0_0_20px_rgba(239,68,68,0.5)]" :
    risk === RiskLevel.WARNING  ? "border-orange-500/50 shadow-[0_0_30px_rgba(249,115,22,0.2)_inset,0_0_20px_rgba(249,115,22,0.4)]" :
    risk === RiskLevel.CAUTION  ? "border-yellow-400/50 shadow-[0_0_30px_rgba(250,204,21,0.1)_inset,0_0_15px_rgba(250,204,21,0.3)]" :
    "border-zinc-800 shadow-[0_0_40px_rgba(0,0,0,0.8)_inset,0_0_15px_rgba(34,211,238,0.1)]";

  const textColor = 
    risk === RiskLevel.CRITICAL ? "text-red-500 drop-shadow-[0_0_8px_rgba(239,68,68,0.8)]" :
    risk === RiskLevel.WARNING  ? "text-orange-400 drop-shadow-[0_0_8px_rgba(249,115,22,0.8)]" :
    risk === RiskLevel.CAUTION  ? "text-yellow-400 drop-shadow-[0_0_8px_rgba(250,204,21,0.8)]" :
    "text-cyan-400 drop-shadow-[0_0_8px_rgba(34,211,238,0.8)]";

  return (
    <div className={`relative bg-zinc-950 font-mono p-5 rounded-2xl w-full max-w-[280px] h-[300px] flex flex-col justify-between border-4 ${borderColor} transition-all duration-500 overflow-hidden`}>
      
      {/* Glossy Screen Overlay */}
      <div className="absolute inset-0 bg-gradient-to-tr from-white/5 to-transparent opacity-50 pointer-events-none rounded-xl" />
      {/* Scanline Effect */}
      <div className="absolute inset-0 bg-[linear-gradient(rgba(0,0,0,0)_50%,rgba(0,0,0,0.25)_50%)] bg-[length:100%_4px] pointer-events-none opacity-20" />

      {/* Header row */}
      <div className="flex justify-between items-center border-b border-zinc-800/80 pb-2 relative z-10">
        <span className={`text-xs font-black tracking-widest ${stale ? "text-yellow-500 drop-shadow-[0_0_5px_rgba(234,179,8,0.8)]" : "text-cyan-400 drop-shadow-[0_0_5px_rgba(34,211,238,0.8)]"}`}>
          VEH-{vehicleId} {stale ? "⚠ STALE" : "● LIVE"}
        </span>
        <div className={buzzerClass} title="Buzzer" />
      </div>

      {/* Main content */}
      <div className={`flex-grow flex flex-col justify-center gap-3 relative z-10 ${textColor}`}>
        {risk === RiskLevel.NORMAL && (
          <>
            <div className="text-center text-[10px] tracking-widest text-zinc-500">V2V ACTIVE</div>
            <div className="flex justify-between text-xs"><span>Neighbors:</span> <span className="font-bold">{neighborsCount}</span></div>
            <div className="flex justify-between text-xs"><span>Speed:</span> <span className="font-bold">{Math.round(speed)} km/h</span></div>
            <div className="text-center font-black mt-3 text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.8)] tracking-widest">STATUS: NORMAL</div>
          </>
        )}
        {risk === RiskLevel.CAUTION && (
          <>
            <div className="font-black text-center tracking-widest animate-pulse">{evName}</div>
            <div className="flex justify-between text-xs"><span>Neighbors:</span> <span className="font-bold">{neighborsCount}</span></div>
            <div className="flex justify-between text-xs"><span>TTC:</span> <span className="font-bold">{ttcStr}</span></div>
            <div className="text-center font-black mt-2 tracking-widest">BE AWARE</div>
          </>
        )}
        {risk === RiskLevel.WARNING && (
          <>
            <div className="font-black text-center text-lg animate-pulse tracking-widest text-orange-500">!! ALERT !!</div>
            <div className="font-bold text-center tracking-wide">{evName}</div>
            <div className="text-center text-xl font-black mt-2">{ttcStr}</div>
            <div className="text-center font-black mt-1 tracking-widest text-orange-500">REDUCE SPEED</div>
          </>
        )}
        {risk === RiskLevel.CRITICAL && (
          <>
            <div className="font-black text-center text-xl animate-bounce tracking-widest text-red-500">!!! DANGER !!!</div>
            <div className="font-black text-center text-lg tracking-widest">{evName}</div>
            <div className="text-center text-2xl font-black mt-1">{ttcStr}</div>
            <div className="text-center font-black text-xl animate-pulse mt-1 tracking-widest text-red-500">SLOW DOWN!</div>
          </>
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-zinc-800/80 pt-2 flex justify-between text-[10px] font-bold text-zinc-600 relative z-10 tracking-widest">
        <span>CONF: <span className={confidence < 100 ? "text-yellow-500" : "text-emerald-500"}>{confidence}%</span></span>
        <span>{Math.round(speed)} KM/H</span>
      </div>
    </div>
  );
}
