import { RiskLevel, EventType, RoadCondition } from "./types";
import type { VehicleStatePacket, VehicleState } from "./types";

const STALE_THRESHOLD_MS = 500;

export class RiskEngine {
  neighborTable: Record<string, VehicleStatePacket> = {};
  staleCount = 0;

  updateNeighbor(packet: VehicleStatePacket) {
    this.neighborTable[packet.vehicleId] = packet;
  }

  calculateRisk(localState: VehicleState, dist: number = 20, condition: RoadCondition = RoadCondition.DRY): 
    { risk: RiskLevel; ttc: number | null; event: EventType | null; stale: boolean } {
    let highestRisk: RiskLevel = RiskLevel.NORMAL;
    let minTtc: number | null = null;
    let triggeringEvent: EventType | null = null;
    let hasStale = false;

    const multiplier = condition === RoadCondition.ICE ? 2.5 : condition === RoadCondition.RAIN ? 1.5 : 1.0;
    const nowMs = Date.now();

    for (const id in this.neighborTable) {
      const pkt = this.neighborTable[id];
      const ageMs = nowMs - pkt.timestamp * 1000;

      if (ageMs > STALE_THRESHOLD_MS) {
        hasStale = true;
        this.staleCount++;
        continue; // discard stale
      }

      const closingSpeed = (localState.speed - pkt.speed) / 3.6;
      const ttc = closingSpeed > 0 ? dist / closingSpeed : Infinity;
      if (minTtc === null || ttc < minTtc) minTtc = ttc;
      if (pkt.event !== EventType.NORMAL) triggeringEvent = pkt.event;

      let risk: RiskLevel = RiskLevel.NORMAL;
      if (ttc < 1.5 * multiplier)       risk = RiskLevel.CRITICAL;
      else if (ttc < 3.0 * multiplier)  risk = RiskLevel.WARNING;
      else if (ttc <= 5.0 * multiplier) risk = RiskLevel.CAUTION;

      if (this.riskVal(risk) > this.riskVal(highestRisk)) highestRisk = risk;
    }

    if (triggeringEvent === EventType.ACCIDENT || triggeringEvent === EventType.HAZARD) {
      if (this.riskVal(RiskLevel.WARNING) > this.riskVal(highestRisk)) highestRisk = RiskLevel.WARNING;
    } else if (triggeringEvent === EventType.HARSH_BRAKING) {
      if (this.riskVal(RiskLevel.CAUTION) > this.riskVal(highestRisk)) highestRisk = RiskLevel.CAUTION;
    }

    return { risk: highestRisk, ttc: minTtc, event: triggeringEvent, stale: hasStale };
  }

  private riskVal(r: RiskLevel) {
    return { NORMAL: 0, CAUTION: 1, WARNING: 2, CRITICAL: 3 }[r] || 0;
  }
}
