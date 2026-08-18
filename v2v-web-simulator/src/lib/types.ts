export const EventType = {
  NORMAL: 0, OVERSPEED: 1, HARSH_BRAKING: 2,
  SUDDEN_SLOWDOWN: 3, ACCIDENT: 4, HAZARD: 5,
  EMERGENCY_STOP: 6, COLLISION_WARNING: 7
} as const;
export type EventType = typeof EventType[keyof typeof EventType];

export const RiskLevel = {
  NORMAL: "NORMAL", CAUTION: "CAUTION", WARNING: "WARNING", CRITICAL: "CRITICAL"
} as const;
export type RiskLevel = typeof RiskLevel[keyof typeof RiskLevel];

export const RoadCondition = { DRY: "DRY", RAIN: "RAIN", ICE: "ICE" } as const;
export type RoadCondition = typeof RoadCondition[keyof typeof RoadCondition];

export const MessagePriority = {
  EMERGENCY: 0, COLLISION: 1, BRAKING: 2, NORMAL: 3
} as const;
export type MessagePriority = typeof MessagePriority[keyof typeof MessagePriority];

export interface VehicleState {
  speed: number;        // km/h
  acceleration: number; // m/s²
  rpm: number;          // 0-8000
  throttle: number;     // 0-100%
  gyroX: number;        // deg/s roll
  gyroY: number;        // deg/s pitch
  gyroZ: number;        // deg/s yaw
}

export interface VehicleStatePacket {
  vehicleId: string;
  seq: number;
  timestamp: number;
  speed: number;
  acceleration: number;
  heading: number;
  event: EventType;
  confidence: number;
  priority: MessagePriority;
  gyroZ: number;
  rpm: number;
}

export interface PacketLogEntry {
  id: string;
  timestamp: number;
  fromId: string;
  toId: string;
  event: EventType;
  speed: number;
  acceleration: number;
  confidence: number;
  priority: MessagePriority;
  seq: number;
}

export interface PerformanceMetrics {
  packetsSent: number;
  packetsReceived: number;
  stalePackets: number;
  avgLatencyMs: number;
  lastLatencyMs: number;
}
