import { signalLabel, signalColor } from '../lib/sim';
import { SparklineChart } from './SparklineChart';

function IMUBar({ label, value, max, hi }: { label: string; value: number; max: number; hi: boolean }) {
  return (
    <div className="flex items-center gap-2 text-[10px] tracking-wider uppercase font-bold text-zinc-500">
      <span className="w-12 shrink-0">{label}</span>
      <div className="flex-1 bg-zinc-950/80 h-2 rounded-full overflow-hidden border border-zinc-800/50 relative">
        <div className={`absolute left-0 top-0 h-full transition-all duration-100 ${hi ? "bg-rose-500 shadow-[0_0_10px_rgba(244,63,94,0.8)]" : "bg-cyan-500 shadow-[0_0_10px_rgba(34,211,238,0.8)]"}`}
          style={{ width: `${Math.min(100, (Math.abs(value) / max) * 100)}%` }} />
      </div>
      <span className={`font-mono w-10 text-right font-black ${hi ? "text-rose-400" : "text-zinc-300"}`}>{value.toFixed(1)}</span>
    </div>
  );
}

interface VehicleControlProps {
  vehicleId: string;
  targetSpeed: number;
  setTargetSpeed: (s: number) => void;
  speed: number;
  accel: number;
  rpm: number;
  throttle: number;
  setThrottle: (t: number) => void;
  gyroX: number; gyroZ: number;
  anomalyScore: number;
  rssiAB?: number; rssiBC?: number;
  brakingDist: number;
  speedHistData: number[];
  accelHistData: number[];
  gear: number;
  disabled?: boolean;
  onBrake: () => void; onCrash: () => void; onReset: () => void;
}

export function VehicleControl({
  vehicleId, targetSpeed, setTargetSpeed, speed, accel, rpm, throttle, setThrottle,
  gyroX, gyroZ, anomalyScore, rssiAB, rssiBC, brakingDist, speedHistData, accelHistData,
  gear, disabled, onBrake, onCrash, onReset
}: VehicleControlProps) {
  const links = [rssiAB !== undefined && { label: 'A↔B', rssi: rssiAB }, rssiBC !== undefined && { label: 'B↔C', rssi: rssiBC }].filter(Boolean) as { label: string; rssi: number }[];

  return (
    <div className={`flex flex-col gap-4 w-full transition-opacity ${disabled ? "opacity-50 pointer-events-none" : ""}`}>
      <div className="flex justify-between items-center">
        <span className="font-black text-zinc-100 tracking-wider">VEHICLE {vehicleId}</span>
        <div className="flex gap-2 text-[10px] font-black font-mono tracking-widest">
          <span className="bg-zinc-800 px-2 py-1 rounded text-zinc-300 border border-zinc-700/50 shadow-inner">G{gear}</span>
          <span className="bg-zinc-800 px-2 py-1 rounded text-zinc-300 border border-zinc-700/50 shadow-inner">{accel.toFixed(1)} m/s²</span>
        </div>
      </div>

      {/* OBD-II sliders */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-zinc-950/30 p-3 rounded-xl border border-zinc-800/50">
          <label className="text-zinc-500 text-[10px] uppercase font-bold flex justify-between mb-2 tracking-wider">Target Speed <span className="text-cyan-400 font-black">{Math.round(targetSpeed)} km/h</span></label>
          <input type="range" min="0" max="150" value={targetSpeed} onChange={e => setTargetSpeed(Number(e.target.value))} className="w-full" />
        </div>
        <div className="bg-zinc-950/30 p-3 rounded-xl border border-zinc-800/50">
          <label className="text-zinc-500 text-[10px] uppercase font-bold flex justify-between mb-2 tracking-wider">Throttle <span className="text-emerald-400 font-black">{Math.round(throttle)}%</span></label>
          <input type="range" min="0" max="100" value={throttle} onChange={e => setThrottle(Number(e.target.value))} className="w-full" />
        </div>
      </div>

      {/* RPM */}
      <div className="bg-zinc-950/30 p-3 rounded-xl border border-zinc-800/50">
        <div className="flex justify-between text-[10px] font-bold tracking-wider uppercase text-zinc-500 mb-2"><span>Engine RPM</span><span className="font-mono text-zinc-200 font-black">{Math.round(rpm)}</span></div>
        <div className="bg-zinc-950/80 h-2 rounded-full overflow-hidden border border-zinc-800/50 relative">
          <div className={`absolute left-0 top-0 h-full transition-all duration-200 ${rpm > 6000 ? 'bg-rose-500 shadow-[0_0_10px_rgba(244,63,94,0.8)]' : rpm > 4000 ? 'bg-amber-400 shadow-[0_0_10px_rgba(251,191,36,0.8)]' : 'bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.8)]'}`} style={{ width: `${(rpm / 7500) * 100}%` }} />
        </div>
      </div>

      {/* IMU */}
      <div className="bg-zinc-950/30 p-3 rounded-xl border border-zinc-800/50 space-y-2">
        <div className="text-[10px] text-zinc-600 font-black tracking-[0.2em]">RAW IMU SENSOR</div>
        <IMUBar label="Accel X" value={gyroX} max={10} hi={Math.abs(gyroX) > 3} />
        <IMUBar label="Gyro Z" value={gyroZ} max={80} hi={Math.abs(gyroZ) > 30} />
      </div>

      {/* ML Anomaly */}
      <div className="bg-zinc-950/30 p-3 rounded-xl border border-zinc-800/50">
        <div className="flex justify-between text-[10px] tracking-wider font-bold uppercase text-zinc-500 mb-2">
          <span>ML Anomaly Score</span>
          <span className={`font-black ${anomalyScore > 80 ? "text-rose-500" : "text-zinc-400"}`}>{anomalyScore}%</span>
        </div>
        <div className="bg-zinc-950/80 h-2 rounded-full overflow-hidden border border-zinc-800/50 relative">
          <div className={`absolute left-0 top-0 h-full transition-all duration-300 ${anomalyScore > 80 ? 'bg-rose-500 shadow-[0_0_10px_rgba(244,63,94,0.8)]' : 'bg-cyan-500 shadow-[0_0_10px_rgba(34,211,238,0.8)]'}`} style={{ width: `${anomalyScore}%` }} />
        </div>
      </div>

      {/* RSSI links */}
      {links.length > 0 && (
        <div className="flex gap-3">
          {links.map(l => (
            <div key={l.label} className="flex-1 bg-zinc-950/50 rounded-xl border border-zinc-800/50 px-3 py-2 text-center">
              <div className="text-[10px] font-black tracking-widest text-zinc-500">{l.label}</div>
              <div className={`text-xs font-black tracking-wider ${signalColor(l.rssi)}`}>{signalLabel(l.rssi)}</div>
              <div className="text-[10px] font-bold text-zinc-600">{l.rssi} dBm</div>
            </div>
          ))}
        </div>
      )}

      {/* Braking distance */}
      <div className="text-[10px] text-zinc-500 font-bold tracking-widest uppercase text-center mt-1">
        Stop dist @ {Math.round(speed)} km/h: <span className="text-orange-500 font-black">{brakingDist}m</span>
      </div>

      {/* Sparklines */}
      <div className="grid grid-cols-2 gap-3 mt-1">
        <div className="bg-zinc-950/30 p-2 rounded-xl border border-zinc-800/50"><SparklineChart data={speedHistData} color="#22d3ee" label="Speed" unit=" km/h" /></div>
        <div className="bg-zinc-950/30 p-2 rounded-xl border border-zinc-800/50"><SparklineChart data={accelHistData} color={accelHistData[accelHistData.length - 1] < -2 ? "#f43f5e" : "#a78bfa"} label="Accel" unit=" m/s²" /></div>
      </div>

      {/* Buttons */}
      <div className="grid grid-cols-3 gap-3 mt-2">
        <button onClick={onBrake} className="bg-orange-500/10 hover:bg-orange-500/20 text-orange-400 border border-orange-500/30 py-2 rounded-xl text-[10px] font-black tracking-widest uppercase transition-all shadow-[0_0_10px_rgba(249,115,22,0.1)] active:scale-95">Hard Brake</button>
        <button onClick={onCrash} className="bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 py-2 rounded-xl text-[10px] font-black tracking-widest uppercase transition-all shadow-[0_0_10px_rgba(244,63,94,0.1)] active:scale-95">Force Crash</button>
        <button onClick={onReset} className="bg-zinc-800/50 hover:bg-zinc-700/50 text-zinc-300 border border-zinc-700/50 py-2 rounded-xl text-[10px] font-black tracking-widest uppercase transition-all active:scale-95">Reset</button>
      </div>
    </div>
  );
}
