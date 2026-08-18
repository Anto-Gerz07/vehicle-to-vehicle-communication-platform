import { signalColor } from '../lib/sim';

interface RoadMapProps {
  posA: number; posB: number; posC: number;
  speedA: number; speedB: number; speedC: number;
  speedLimit: number;
  rssiAB: number; rssiBC: number;
  headOn?: boolean;
}

function SignalBar({ rssi, label }: { rssi: number; label: string }) {
  const bars = rssi > -60 ? 4 : rssi > -75 ? 3 : rssi > -90 ? 2 : 1;
  return (
    <div className="flex flex-col items-center gap-0.5">
      <div className="flex items-end gap-0.5">
        {[1, 2, 3, 4].map(b => (
          <div key={b} className={`w-1.5 rounded-sm transition-all ${b <= bars ? signalColor(rssi).replace('text-', 'bg-').replace('500', '400') + ' shadow-[0_0_8px_currentColor]' : 'bg-zinc-800/80'}`}
            style={{ height: `${b * 4}px` }} />
        ))}
      </div>
      <span className="text-[8px] text-gray-500 font-mono">{label}</span>
      <span className={`text-[8px] font-mono ${signalColor(rssi)}`}>{rssi}dBm</span>
    </div>
  );
}

export function RoadMap({ posA, posB, posC, speedA, speedB, speedC, speedLimit, rssiAB, rssiBC, headOn }: RoadMapProps) {
  // Map screen space: world positions relative to A
  const screenA = 85;
  const scale = 0.4;
  const screenB = screenA - (posA - posB) * scale;
  const screenC = screenA - (posA - posC) * scale;

  const over = (s: number) => s > speedLimit;

  return (
    <div className="w-full bg-zinc-900/60 backdrop-blur-lg rounded-2xl border border-zinc-800/50 overflow-hidden relative h-40 mb-2 shadow-2xl">
      {/* Road */}
      <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-[72px] bg-zinc-950/80 border-y border-zinc-800/50" />
      <div className="absolute w-full border-t-2 border-dashed border-zinc-700/50 top-1/2" />
      
      {/* Grid overlay for tech vibe */}
      <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:20px_20px] pointer-events-none" />

      {/* Speed limit sign */}
      <div className="absolute left-4 top-1/2 -translate-y-1/2 z-10 flex flex-col items-center">
        <div className="w-10 h-10 rounded-full border-[3px] border-rose-500 bg-white flex items-center justify-center shadow-[0_0_15px_rgba(225,29,72,0.3)]">
          <span className="text-rose-600 font-black text-xs leading-none">{speedLimit}</span>
        </div>
        <span className="text-zinc-500 text-[8px] font-bold mt-1 tracking-widest">KM/H</span>
      </div>

      {/* Vehicles */}
      {[
        { label: 'C', pos: screenC, speed: speedC, col: headOn ? 'bg-rose-500' : 'bg-emerald-400', dir: headOn ? '←' : '→', glow: headOn ? 'rgba(244,63,94,0.5)' : 'rgba(52,211,153,0.5)' },
        { label: 'B', pos: screenB, speed: speedB, col: 'bg-violet-400', dir: '→', glow: 'rgba(167,139,250,0.5)' },
        { label: 'A', pos: screenA, speed: speedA, col: 'bg-cyan-400', dir: '→', glow: 'rgba(34,211,238,0.5)' },
      ].map(v => (
        <div key={v.label}
          className="absolute z-10 transition-all duration-200"
          style={{ left: `${Math.max(10, Math.min(90, v.pos))}%`, top: '50%', transform: 'translate(-50%,-50%)' }}>
          
          <div className={`w-20 h-12 rounded-xl bg-zinc-900/90 backdrop-blur border ${over(v.speed) ? 'border-amber-400 shadow-[0_0_20px_rgba(251,191,36,0.4)]' : 'border-zinc-700/50 shadow-xl'} flex flex-col items-center justify-center text-zinc-100 overflow-hidden relative`}>
            {/* Top color bar */}
            <div className={`absolute top-0 inset-x-0 h-1.5 ${v.col}`} style={{ boxShadow: `0 0 10px ${v.glow}` }} />
            
            <div className="flex items-center gap-1 mt-1">
              <span className={`text-[10px] font-black tracking-wider ${v.col.replace('bg-', 'text-')}`}>{v.dir} VEH-{v.label}</span>
            </div>
            <span className="text-[10px] font-mono font-bold">{Math.round(v.speed)} km/h</span>
            {over(v.speed) && <span className="absolute bottom-0 inset-x-0 bg-amber-400 text-amber-950 text-[7px] font-black tracking-widest text-center">OVERSPEED</span>}
          </div>
        </div>
      ))}

      {/* RSSI indicators */}
      <div className="absolute top-2 right-4 flex gap-4 z-10">
        <SignalBar rssi={rssiBC} label="C↔B" />
        <SignalBar rssi={rssiAB} label="B↔A" />
      </div>

      {/* Position odometers */}
      <div className="absolute bottom-2 left-6 flex gap-6 text-[10px] text-zinc-500 font-mono font-bold tracking-wider z-10">
        <span>A: {posA.toFixed(0)}m</span>
        <span>B: {posB.toFixed(0)}m</span>
        <span>C: {posC.toFixed(0)}m</span>
      </div>
    </div>
  );
}
