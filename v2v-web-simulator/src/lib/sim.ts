// Vehicle parameters: m=1500kg, Cd=0.30, A=2.2m², CR=0.015
const MASS = 1500;
const DRAG_K = 0.5 * 1.225 * 0.30 * 2.2; // 0.402 kg/m
const ROLL_F = 0.015 * MASS * 9.81;        // ~220.7 N

// ── Force-based acceleration (kinematic model) ───────────────────────────────
export function computeAccel(speedDiffMs: number, throttle: number, speedKmh: number, gear: number, mu: number): number {
  const v = speedKmh / 3.6;
  const dragA = (DRAG_K * v * v) / MASS;
  const rollA = ROLL_F / MASS;
  const parasiticA = dragA + rollA;

  if (speedDiffMs > 0.3) {
    const gf = gear === 1 ? 2.1 : gear === 2 ? 1.65 : gear === 3 ? 1.25 : gear === 4 ? 1.0 : 0.82;
    const maxNetA = Math.max(0, (4500 * (throttle / 100) * gf) / MASS - parasiticA);
    const desired = Math.min(speedDiffMs * 2.5, 3.5);
    return Math.min(desired, maxNetA);
  } else if (speedDiffMs < -0.3) {
    const maxBrakeA = mu * 9.81 * 0.85;
    const desired = Math.min(Math.abs(speedDiffMs) * 3.0, maxBrakeA);
    return -(desired + parasiticA);
  } else {
    return 0;
  }
}

// ── Braking distance ──────────────────────────────────────────────────────────
export const brakingDistance = (speedKmh: number, mu: number) => {
  const v = speedKmh / 3.6;
  return +(v * v / (2 * mu * 9.81)).toFixed(1);
};

export const frictionCoeff = (cond: string) =>
  cond === 'ICE' ? 0.2 : cond === 'RAIN' ? 0.5 : 0.8;

// ── Gear + RPM ────────────────────────────────────────────────────────────────
const RATIOS = [3.8, 2.1, 1.36, 1.0, 0.78];
export const getGear = (s: number) =>
  s < 15 ? 1 : s < 35 ? 2 : s < 60 ? 3 : s < 90 ? 4 : 5;
export const getRPM = (speedKmh: number, throttle: number) => {
  const gear = getGear(speedKmh);
  const wheelRPS = (speedKmh / 3.6) / 1.93;
  return Math.max(800, Math.min(7500, wheelRPS * 60 * RATIOS[gear - 1] * 3.73 + throttle * 4));
};

// ── IMU noise (MPU6050 Gaussian model + bias drift) ───────────────────────────
export const imuNoise = (val: number, std = 0.15) => {
  const u = Math.random() || 1e-10;
  const z = Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * Math.random());
  return val + z * std;
};

// ── ESP-NOW channel model ─────────────────────────────────────────────────────
export const getRSSI = (dist: number) =>
  dist <= 0 ? -40 : Math.round(-40 - 20 * Math.log10(dist));
export const signalLabel = (rssi: number) =>
  rssi > -60 ? 'STRONG' : rssi > -75 ? 'GOOD' : rssi > -90 ? 'WEAK' : 'LOST';
export const signalColor = (rssi: number) =>
  rssi > -60 ? 'text-green-400' : rssi > -75 ? 'text-cyan-400' : rssi > -90 ? 'text-yellow-400' : 'text-red-500';
export const dropRate = (dist: number) =>
  dist < 30 ? 0 : dist < 60 ? 0.02 : dist < 80 ? 0.08 : dist < 100 ? 0.18 : dist < 110 ? 0.55 : 1;
export const shouldDrop = (dist: number) => Math.random() < dropRate(dist);

// ── Reaction time ─────────────────────────────────────────────────────────────
export const humanReactionMs = () => 300 + Math.random() * 500;
