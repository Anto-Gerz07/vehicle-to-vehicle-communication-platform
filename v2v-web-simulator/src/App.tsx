import { useState, useEffect, useRef, useCallback } from 'react';
import { EventType, RiskLevel, RoadCondition, MessagePriority } from './lib/types';
import type { VehicleStatePacket, PacketLogEntry, PerformanceMetrics } from './lib/types';
import { RuleEngine } from './lib/rules';
import { RiskEngine } from './lib/risk';
import { MLEngine } from './lib/ml';
import { computeAccel, brakingDistance, frictionCoeff, getRPM, getGear, getRSSI, shouldDrop, imuNoise, humanReactionMs } from './lib/sim';
import { OledDisplay } from './components/OledDisplay';
import { VehicleControl } from './components/VehicleControl';
import { RoadMap } from './components/RoadMap';
import { PacketLog } from './components/PacketLog';
import { TTCRing } from './components/TTCRing';

// ─── Types ───────────────────────────────────────────────────────────────────
type Mode = 'normal' | 'convoy' | 'headon' | 'emergency';
type VID = 'A' | 'B' | 'C';

interface SimV {
  id: VID; pos: number; speed: number; accel: number;
  targetSpeed: number; throttle: number; rpm: number;
  gyroX: number; gyroZ: number; imuBiasX: number; imuBiasZ: number;
  manualAccel: number | null; manualUntil: number;
  reactionUntil: number; // don't auto-react until this timestamp
}

function mkSim(id: VID, speed: number, pos: number): SimV {
  return { id, pos, speed, accel: 0, targetSpeed: speed, throttle: 40, rpm: 2800, gyroX: 0, gyroZ: 0, imuBiasX: 0, imuBiasZ: 0, manualAccel: null, manualUntil: 0, reactionUntil: 0 };
}

function getPriority(ev: EventType): MessagePriority {
  if (ev === EventType.ACCIDENT || ev === EventType.EMERGENCY_STOP) return MessagePriority.EMERGENCY;
  if (ev === EventType.COLLISION_WARNING) return MessagePriority.COLLISION;
  if (ev === EventType.HARSH_BRAKING || ev === EventType.SUDDEN_SLOWDOWN) return MessagePriority.BRAKING;
  return MessagePriority.NORMAL;
}

// ─── App ─────────────────────────────────────────────────────────────────────
export default function App() {
  const [mode, setMode] = useState<Mode>('normal');
  const [weather, setWeather] = useState<RoadCondition>(RoadCondition.DRY);
  const [speedLimit, setSpeedLimit] = useState(60);
  const [isDemo, setIsDemo] = useState(false);

  // Display state (React state, updated at ~5Hz)
  const [dispA, setDispA] = useState({ speed: 70, accel: 0, rpm: 2800, throttle: 40, gyroX: 0, gyroZ: 0, targetSpeed: 70, gear: 3, pos: 300 });
  const [dispB, setDispB] = useState({ speed: 65, accel: 0, rpm: 2600, throttle: 40, gyroX: 0, gyroZ: 0, targetSpeed: 65, gear: 3, pos: 240 });
  const [dispC, setDispC] = useState({ speed: 60, accel: 0, rpm: 2400, throttle: 40, gyroX: 0, gyroZ: 0, targetSpeed: 60, gear: 3, pos: 180 });
  const [riskA, setRiskA] = useState<{ risk: RiskLevel; ttc: number | null; event: EventType | null; stale: boolean }>({ risk: RiskLevel.NORMAL, ttc: null, event: null, stale: false });
  const [riskB, setRiskB] = useState<{ risk: RiskLevel; ttc: number | null; event: EventType | null; stale: boolean }>({ risk: RiskLevel.NORMAL, ttc: null, event: null, stale: false });
  const [riskC, setRiskC] = useState<{ risk: RiskLevel; ttc: number | null; event: EventType | null; stale: boolean }>({ risk: RiskLevel.NORMAL, ttc: null, event: null, stale: false });
  const [anomaly, setAnomaly] = useState({ A: 0, B: 0, C: 0 });
  const [rssi, setRssi] = useState({ AB: -55, BC: -55 });
  const [log, setLog] = useState<PacketLogEntry[]>([]);
  const [metrics, setMetrics] = useState<PerformanceMetrics>({ packetsSent: 0, packetsReceived: 0, stalePackets: 0, avgLatencyMs: 0, lastLatencyMs: 0 });
  const [hist, setHist] = useState({ speedA: [70], speedB: [65], speedC: [60], accelA: [0], accelB: [0], accelC: [0] });
  const [brakeDist, setBrakeDist] = useState({ A: 0, B: 0, C: 0 });

  // Simulation refs (physics state — no React re-render)
  const simRef = useRef({ A: mkSim('A', 70, 300), B: mkSim('B', 65, 240), C: mkSim('C', 60, 180) });
  const modeRef = useRef<Mode>('normal');
  const weatherRef = useRef<RoadCondition>(RoadCondition.DRY);
  const slRef = useRef(60);
  const reA = useRef(new RuleEngine()); const reB = useRef(new RuleEngine()); const reC = useRef(new RuleEngine());
  const riA = useRef(new RiskEngine()); const riB = useRef(new RiskEngine()); const riC = useRef(new RiskEngine());
  const mlA = useRef(new MLEngine());   const mlB = useRef(new MLEngine());   const mlC = useRef(new MLEngine());
  const seqRef = useRef({ A: 0, B: 0, C: 0 });
  const mRef = useRef<PerformanceMetrics>({ packetsSent: 0, packetsReceived: 0, stalePackets: 0, avgLatencyMs: 0, lastLatencyMs: 0 });
  const latHist = useRef<number[]>([]);
  const logRef = useRef<PacketLogEntry[]>([]);
  const dispTick = useRef(0);

  // Sync settings to refs
  useEffect(() => { modeRef.current = mode; }, [mode]);
  useEffect(() => { weatherRef.current = weather; }, [weather]);
  useEffect(() => { slRef.current = speedLimit; reA.current.speedLimit = speedLimit; reB.current.speedLimit = speedLimit; reC.current.speedLimit = speedLimit; }, [speedLimit]);

  // ── Main sim loop (50ms = 20Hz physics + periodic V2V packets) ──────────────
  useEffect(() => {
    const TICK = 0.05;
    const timer = setInterval(() => {
      const now = Date.now();
      const nowSec = now / 1000;
      const s = simRef.current;
      const m = modeRef.current;

      // Convoy mode: 2-second headway PD controller
      if (m === 'convoy') {
        if (now > s.B.reactionUntil) {
          const dAB = Math.max(1, s.A.pos - s.B.pos);
          const tgt = Math.max(8, (s.B.speed / 3.6) * 2.0); // 2s headway
          const err = dAB - tgt;
          const closing = (s.A.speed - s.B.speed) / 3.6;
          s.B.targetSpeed = Math.max(0, Math.min(150, s.A.speed + (err * 0.6 + closing * 1.0) * 3.6));
        }
        if (now > s.C.reactionUntil) {
          const dBC = Math.max(1, s.B.pos - s.C.pos);
          const tgt = Math.max(8, (s.C.speed / 3.6) * 2.0);
          const err = dBC - tgt;
          const closing = (s.B.speed - s.C.speed) / 3.6;
          s.C.targetSpeed = Math.max(0, Math.min(150, s.B.speed + (err * 0.6 + closing * 1.0) * 3.6));
        }
      }

      // Emergency: A broadcasts emergency, B/C auto-brake after human reaction delay
      if (m === 'emergency') {
        s.A.manualAccel = null;
        if (now > s.B.reactionUntil && s.B.manualAccel === null) { s.B.manualAccel = -3.2; s.B.manualUntil = now + 5000; }
        if (now > s.C.reactionUntil && s.C.manualAccel === null) { s.C.manualAccel = -3.2; s.C.manualUntil = now + 5000; }
      }

      for (const id of ['A', 'B', 'C'] as VID[]) {
        const v = s[id];
        const mu = frictionCoeff(weatherRef.current);

        // Force-based acceleration: engine thrust vs drag + rolling + ABS braking
        let a: number;
        if (v.manualAccel !== null && now < v.manualUntil) {
          a = v.manualAccel;
        } else {
          v.manualAccel = null;
          const diff = (v.targetSpeed - v.speed) / 3.6;
          a = computeAccel(diff, v.throttle, v.speed, getGear(v.speed), mu);
        }
        v.accel = a;

        // Kinematic update
        v.speed = Math.max(0, v.speed + a * TICK * 3.6);
        v.pos += (v.speed / 3.6) * TICK;

        // Head-on: C moves backward (toward A)
        if (m === 'headon' && id === 'C') {
          v.pos -= (v.speed / 3.6) * TICK * 2;
        }

        // RPM
        v.rpm = getRPM(v.speed, v.throttle);

        // IMU with noise + bias drift
        const isAccident = a <= -7.5 && v.speed <= 2;
        const raw = isAccident
          ? { x: (Math.random() - 0.5) * 100, z: (Math.random() > 0.5 ? 1 : -1) * (40 + Math.random() * 50) }
          : { x: a * -6, z: a * -1.8 };
        v.imuBiasX += (Math.random() - 0.5) * 0.002; // drift
        v.imuBiasZ += (Math.random() - 0.5) * 0.002;
        v.gyroX = imuNoise(raw.x + v.imuBiasX, 0.18);
        v.gyroZ = imuNoise(raw.z + v.imuBiasZ, 0.12);
      }

      // ── Packet broadcasts (every tick, filtered by priority rate) ────────────
      dispTick.current++;
      // Rate control: Normal=4Hz(every 5 ticks), Braking=10Hz(every 2), Emergency=20Hz(every tick)
      const doSend = true; // per-vehicle filtering in broadcast()
      if (doSend) {
        const newLog: PacketLogEntry[] = [];
        const distAB = Math.abs(s.A.pos - s.B.pos);
        const distBC = Math.abs(s.B.pos - s.C.pos);

        const broadcast = (v: SimV, toIds: VID[], re: typeof reA, ml: typeof mlA) => {
          let ev = re.current.evaluate({ speed: v.speed, acceleration: v.accel, rpm: v.rpm, throttle: v.throttle, gyroX: v.gyroX, gyroY: 0, gyroZ: v.gyroZ }, nowSec);
          if (modeRef.current === 'emergency' && v.id === 'A') ev = EventType.EMERGENCY_STOP;
          const mlRes = ml.current.evaluate({ speed: v.speed, acceleration: v.accel, rpm: v.rpm, throttle: v.throttle, gyroX: v.gyroX, gyroY: 0, gyroZ: v.gyroZ });
          if (ev === EventType.NORMAL && mlRes.isAnomaly) ev = EventType.HAZARD;
          seqRef.current[v.id]++;
          const pkt: VehicleStatePacket = { vehicleId: v.id, seq: seqRef.current[v.id], timestamp: nowSec, speed: v.speed, acceleration: v.accel, heading: 0, event: ev, confidence: mlRes.isAnomaly ? 78 : 100, priority: getPriority(ev), gyroZ: v.gyroZ, rpm: v.rpm };

          for (const tid of toIds) {
            const dist = tid === 'A' ? distAB : tid === 'B' ? (v.id === 'A' ? distAB : distBC) : distBC;
            mRef.current.packetsSent++;
            if (!shouldDrop(dist)) { mRef.current.packetsReceived++; const ri = tid === 'A' ? riA : tid === 'B' ? riB : riC; ri.current.updateNeighbor(pkt); }
          }

          // Propagation: B adds HAZARD if A is in trouble
          if (v.id === 'B') {
            const nA = riB.current.neighborTable['A'];
            if (nA && (nA.event === EventType.ACCIDENT || nA.event === EventType.HARSH_BRAKING) && ev === EventType.NORMAL) pkt.event = EventType.HAZARD;
          }

          const lat = Math.round(2 + Math.random() * 11); latHist.current.push(lat); if (latHist.current.length > 30) latHist.current.shift();
          mRef.current.lastLatencyMs = lat;
          mRef.current.avgLatencyMs = Math.round(latHist.current.reduce((a, b) => a + b, 0) / latHist.current.length);
          mRef.current.stalePackets = riA.current.staleCount + riB.current.staleCount + riC.current.staleCount;
          newLog.push({ id: `${nowSec.toFixed(2)}-${v.id}`, timestamp: nowSec, fromId: v.id, toId: `→${toIds.join(',')}`, event: pkt.event, speed: v.speed, acceleration: v.accel, confidence: pkt.confidence, priority: pkt.priority, seq: pkt.seq });
          return { ev, mlScore: mlRes.anomalyScore };
        };

        broadcast(s.A, ['B'], reA, mlA);
        broadcast(s.B, ['A', 'C'], reB, mlB);
        broadcast(s.C, ['B'], reC, mlC);

        logRef.current = [...logRef.current.slice(-60), ...newLog];
      }
    }, 50);
    return () => clearInterval(timer);
  }, []); // no deps — uses only refs

  // ── Display update (200ms = 5Hz) ──────────────────────────────────────────
  useEffect(() => {
    const d = setInterval(() => {
      const s = simRef.current;
      const distAB = Math.abs(s.A.pos - s.B.pos);
      const distBC = Math.abs(s.B.pos - s.C.pos);
      const rssiAB = getRSSI(distAB), rssiBC = getRSSI(distBC);

      const mlResA = mlA.current.evaluate({ speed: s.A.speed, acceleration: s.A.accel, rpm: s.A.rpm, throttle: s.A.throttle, gyroX: s.A.gyroX, gyroY: 0, gyroZ: s.A.gyroZ });
      const mlResB = mlB.current.evaluate({ speed: s.B.speed, acceleration: s.B.accel, rpm: s.B.rpm, throttle: s.B.throttle, gyroX: s.B.gyroX, gyroY: 0, gyroZ: s.B.gyroZ });
      const mlResC = mlC.current.evaluate({ speed: s.C.speed, acceleration: s.C.accel, rpm: s.C.rpm, throttle: s.C.throttle, gyroX: s.C.gyroX, gyroY: 0, gyroZ: s.C.gyroZ });

      setDispA({ speed: s.A.speed, accel: s.A.accel, rpm: s.A.rpm, throttle: s.A.throttle, gyroX: s.A.gyroX, gyroZ: s.A.gyroZ, targetSpeed: s.A.targetSpeed, gear: getGear(s.A.speed), pos: s.A.pos });
      setDispB({ speed: s.B.speed, accel: s.B.accel, rpm: s.B.rpm, throttle: s.B.throttle, gyroX: s.B.gyroX, gyroZ: s.B.gyroZ, targetSpeed: s.B.targetSpeed, gear: getGear(s.B.speed), pos: s.B.pos });
      setDispC({ speed: s.C.speed, accel: s.C.accel, rpm: s.C.rpm, throttle: s.C.throttle, gyroX: s.C.gyroX, gyroZ: s.C.gyroZ, targetSpeed: s.C.targetSpeed, gear: getGear(s.C.speed), pos: s.C.pos });
      setRiskA(riA.current.calculateRisk({ speed: s.A.speed, acceleration: s.A.accel, rpm: s.A.rpm, throttle: s.A.throttle, gyroX: s.A.gyroX, gyroY: 0, gyroZ: s.A.gyroZ }, distAB, weatherRef.current));
      setRiskB(riB.current.calculateRisk({ speed: s.B.speed, acceleration: s.B.accel, rpm: s.B.rpm, throttle: s.B.throttle, gyroX: s.B.gyroX, gyroY: 0, gyroZ: s.B.gyroZ }, distAB, weatherRef.current));
      setRiskC(riC.current.calculateRisk({ speed: s.C.speed, acceleration: s.C.accel, rpm: s.C.rpm, throttle: s.C.throttle, gyroX: s.C.gyroX, gyroY: 0, gyroZ: s.C.gyroZ }, distBC, weatherRef.current));
      setAnomaly({ A: mlResA.anomalyScore, B: mlResB.anomalyScore, C: mlResC.anomalyScore });
      setRssi({ AB: rssiAB, BC: rssiBC });
      const mu = frictionCoeff(weatherRef.current);
      setBrakeDist({ A: brakingDistance(s.A.speed, mu), B: brakingDistance(s.B.speed, mu), C: brakingDistance(s.C.speed, mu) });
      setHist(prev => ({ speedA: [...prev.speedA.slice(-30), s.A.speed], speedB: [...prev.speedB.slice(-30), s.B.speed], speedC: [...prev.speedC.slice(-30), s.C.speed], accelA: [...prev.accelA.slice(-30), s.A.accel], accelB: [...prev.accelB.slice(-30), s.B.accel], accelC: [...prev.accelC.slice(-30), s.C.accel] }));
      setLog([...logRef.current]);
      setMetrics({ ...mRef.current });
    }, 200);
    return () => clearInterval(d);
  }, []);

  // ── Actions ───────────────────────────────────────────────────────────────
  const applyManual = (id: VID, accel: number, dur = 3000) => {
    simRef.current[id].manualAccel = accel;
    simRef.current[id].manualUntil = Date.now() + dur;
  };
  const handleBrake = (id: VID) => applyManual(id, -4.5, 2500);
  const handleCrash = (id: VID) => { simRef.current[id].targetSpeed = 0; applyManual(id, -8.5, 4000); };
  const handleReset = (id: VID) => {
    const defaults: Record<VID, [number, number]> = { A: [70, 300], B: [65, 240], C: [60, 180] };
    const [spd, pos] = defaults[id];
    simRef.current[id] = mkSim(id, spd, pos);
    reA.current = new RuleEngine(); reB.current = new RuleEngine(); reC.current = new RuleEngine();
  };

  // ── Demo Scenario (MD Section 33) ─────────────────────────────────────────
  const runDemo = useCallback(() => {
    setIsDemo(true); setMode('normal');
    simRef.current = { A: mkSim('A', 70, 300), B: mkSim('B', 65, 240), C: mkSim('C', 60, 180) };
    setTimeout(() => { simRef.current.A.targetSpeed = 72; }, 1500);
    setTimeout(() => applyManual('A', -4.5, 2000), 3000);
    setTimeout(() => { simRef.current.A.targetSpeed = 40; }, 3200);
    setTimeout(() => { simRef.current.B.reactionUntil = Date.now() + humanReactionMs(); }, 3300);
    setTimeout(() => handleCrash('A'), 6500);
    setTimeout(() => setIsDemo(false), 12000);
  }, []);

  // ── Export CSV ─────────────────────────────────────────────────────────────
  const exportCSV = () => {
    const rows = ['timestamp,from,to,event,speed,accel,seq', ...logRef.current.map(e => `${e.timestamp.toFixed(3)},${e.fromId},${e.toId},${e.event},${e.speed.toFixed(1)},${e.acceleration.toFixed(2)},${e.seq}`)].join('\n');
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([rows], { type: 'text/csv' }));
    a.download = 'v2v_telemetry.csv'; a.click();
  };

  const neighborB = Object.fromEntries(Object.entries(riB.current.neighborTable).map(([id, p]) => [id, { speed: p.speed, acceleration: p.acceleration, event: p.event, timestamp: p.timestamp }]));
  const modeBtn = (m: Mode, label: string, activeCol: string) => (
    <button key={m} onClick={() => setMode(m)}
      className={`px-3 py-1 rounded-[10px] text-[10px] font-bold tracking-wider transition-all duration-300 ${mode === m ? `${activeCol}` : 'bg-transparent text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50'}`}>
      {label}
    </button>
  );

  const vehiclePanel = (id: VID, label: string, col: string, disp: typeof dispA, risk: typeof riskA, an: number, rssiA?: number, rssiB?: number) => (
    <div className="flex flex-col gap-3 bg-zinc-900/60 backdrop-blur-lg p-5 rounded-2xl border border-zinc-800/50 shadow-2xl relative">
      <div className={`absolute -top-3 left-4 px-4 py-0.5 rounded-full text-[10px] font-black tracking-widest text-zinc-950 ${col}`}>{label}</div>
      <div className="flex items-center justify-between mt-1">
        <OledDisplay vehicleId={id} speed={disp.speed} neighborsCount={Object.keys(id === 'A' ? riA : id === 'B' ? riB : riC).length}
          risk={risk.risk} ttc={risk.ttc} event={risk.event} confidence={an > 70 ? 78 : 100} stale={risk.stale} />
        <TTCRing ttc={risk.ttc} size={70} />
      </div>
      <VehicleControl vehicleId={id} targetSpeed={disp.targetSpeed} setTargetSpeed={s => { simRef.current[id].targetSpeed = s; }}
        speed={disp.speed} accel={disp.accel} rpm={disp.rpm} throttle={disp.throttle} setThrottle={t => { simRef.current[id].throttle = t; }}
        gyroX={disp.gyroX} gyroZ={disp.gyroZ} anomalyScore={an}
        rssiAB={rssiA} rssiBC={rssiB}
        brakingDist={id === 'A' ? brakeDist.A : id === 'B' ? brakeDist.B : brakeDist.C}
        speedHistData={id === 'A' ? hist.speedA : id === 'B' ? hist.speedB : hist.speedC}
        accelHistData={id === 'A' ? hist.accelA : id === 'B' ? hist.accelB : hist.accelC}
        gear={disp.gear} disabled={isDemo && id === 'A'}
        onBrake={() => handleBrake(id)} onCrash={() => handleCrash(id)} onReset={() => handleReset(id)} />
    </div>
  );

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans selection:bg-cyan-500/30">
      <header className="flex flex-wrap gap-3 justify-between items-center bg-zinc-900/40 backdrop-blur-md border-b border-zinc-800/50 px-6 py-4 shadow-xl z-50">
        <div>
          <h1 className="text-xl font-black tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-zinc-100 to-zinc-400">V2V EDGE INTELLIGENCE</h1>
          <p className="text-zinc-500 text-[10px] tracking-wider uppercase font-semibold mt-1">Kinematic Physics • ESP-NOW • IMU Noise • ML Anomaly</p>
        </div>
        <div className="flex flex-wrap gap-3 items-center">
          <div className="flex gap-1.5 p-1 bg-zinc-950/50 rounded-xl border border-zinc-800/50">
            {modeBtn('normal', 'NORMAL', 'bg-blue-500 text-white shadow-[0_0_15px_rgba(59,130,246,0.5)]')}
            {modeBtn('convoy', 'CONVOY', 'bg-purple-500 text-white shadow-[0_0_15px_rgba(168,85,247,0.5)]')}
            {modeBtn('headon', 'HEAD-ON', 'bg-rose-600 text-white shadow-[0_0_15px_rgba(225,29,72,0.5)]')}
            {modeBtn('emergency', 'EMERGENCY', 'bg-orange-500 text-white shadow-[0_0_15px_rgba(249,115,22,0.5)]')}
          </div>
          <select value={weather} onChange={e => setWeather(e.target.value as RoadCondition)} className="bg-zinc-900/80 border border-zinc-700/50 text-zinc-200 rounded-lg px-3 py-1.5 text-xs font-mono outline-none hover:border-zinc-600 transition-colors">
            <option value={RoadCondition.DRY}>DRY (μ=0.80)</option>
            <option value={RoadCondition.RAIN}>RAIN (μ=0.50)</option>
            <option value={RoadCondition.ICE}>ICE (μ=0.20)</option>
          </select>
          <div className="flex items-center gap-2 bg-zinc-900/80 border border-zinc-700/50 rounded-lg px-3 py-1.5 hover:border-zinc-600 transition-colors">
            <label className="text-zinc-500 text-[10px] font-bold uppercase tracking-wider">Limit</label>
            <input type="number" min={20} max={130} value={speedLimit} onChange={e => setSpeedLimit(Number(e.target.value))} className="bg-transparent text-zinc-200 text-xs font-mono w-10 outline-none text-right" />
            <span className="text-zinc-600 text-xs font-mono">km/h</span>
          </div>
          <button onClick={runDemo} disabled={isDemo} className={`px-4 py-1.5 rounded-xl text-xs font-black tracking-wider transition-all ${isDemo ? 'bg-zinc-800 text-zinc-500 cursor-not-allowed' : 'bg-zinc-100 text-zinc-900 hover:bg-white shadow-[0_0_20px_rgba(255,255,255,0.3)] hover:scale-105 active:scale-95'}`}>
            {isDemo ? 'RUNNING...' : 'RUN DEMO'}
          </button>
          <button onClick={exportCSV} className="px-4 py-1.5 rounded-xl text-xs font-bold tracking-wider bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 hover:border-zinc-500 text-zinc-300 transition-all hover:scale-105 active:scale-95">EXPORT CSV</button>
        </div>
      </header>

      <div className="flex-1 flex flex-col xl:flex-row relative z-10">
        <div className="flex-1 p-6 flex flex-col overflow-auto gap-6">
          <RoadMap posA={dispA.pos} posB={dispB.pos} posC={dispC.pos} speedA={dispA.speed} speedB={dispB.speed} speedC={dispC.speed} speedLimit={speedLimit} rssiAB={rssi.AB} rssiBC={rssi.BC} headOn={mode === 'headon'} />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {vehiclePanel('C', 'VEHICLE C (REAR)', 'bg-emerald-400', dispC, riskC, anomaly.C, undefined, rssi.BC)}
            {vehiclePanel('B', 'VEHICLE B (MIDDLE)', 'bg-violet-400', dispB, riskB, anomaly.B, rssi.AB, rssi.BC)}
            {vehiclePanel('A', 'VEHICLE A (LEADER)', 'bg-cyan-400', dispA, riskA, anomaly.A, rssi.AB, undefined)}
          </div>
        </div>
        <div className="w-full xl:w-96 bg-zinc-900/40 backdrop-blur-md border-t xl:border-t-0 xl:border-l border-zinc-800/50 p-6 xl:h-[calc(100vh-73px)] xl:sticky xl:top-[73px] overflow-y-auto">
          <PacketLog entries={log} metrics={metrics} neighborTableB={neighborB} />
        </div>
      </div>
    </div>
  );
}
