import { EventType } from "./types";
import type { VehicleState } from "./types";

export class RuleEngine {
  speedLimit = 60.0;
  lastSpeed: number | null = null;
  lastTime: number | null = null;

  evaluate(state: VehicleState, currentTime: number): EventType {
    const { speed, acceleration, gyroZ } = state;
    let event: EventType = EventType.NORMAL;

    // Accident: large decel + near zero speed + (optional) gyro spike
    const gyroSpike = Math.abs(gyroZ) > 25;
    if (acceleration <= -5.0 && speed <= 5.0) {
      event = gyroSpike ? EventType.ACCIDENT : EventType.ACCIDENT;
    } else if (acceleration < -3.0) {
      event = EventType.HARSH_BRAKING;
    } else if (
      this.lastSpeed !== null && this.lastTime !== null &&
      this.lastSpeed - speed > 20 && currentTime - this.lastTime < 2.0
    ) {
      event = EventType.SUDDEN_SLOWDOWN;
    } else if (speed > this.speedLimit) {
      event = EventType.OVERSPEED;
    }

    this.lastSpeed = speed;
    this.lastTime = currentTime;
    return event;
  }
}
