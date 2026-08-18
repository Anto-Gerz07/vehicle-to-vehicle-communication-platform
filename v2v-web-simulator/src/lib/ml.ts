import type { VehicleState } from "./types";

export class MLEngine {
  private history: { speed: number; acc: number }[] = [];
  private maxHistory = 30;

  evaluate(state: VehicleState): { anomalyScore: number; isAnomaly: boolean } {
    this.history.push({ speed: state.speed, acc: state.acceleration });
    if (this.history.length > this.maxHistory) {
      this.history.shift();
    }

    if (this.history.length < 10) return { anomalyScore: 0, isAnomaly: false };

    const meanAcc = this.history.reduce((sum, h) => sum + h.acc, 0) / this.history.length;
    const varAcc = this.history.reduce((sum, h) => sum + Math.pow(h.acc - meanAcc, 2), 0) / this.history.length;
    const stdDevAcc = Math.sqrt(varAcc) || 1;

    const zScore = Math.abs(state.acceleration - meanAcc) / stdDevAcc;
    const anomalyScore = Math.min(100, Math.round(zScore * 20));
    
    return {
      anomalyScore,
      isAnomaly: anomalyScore > 80 
    };
  }
}
