import math

class RiskLevel:
    NORMAL = "NORMAL"
    CAUTION = "CAUTION"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

def heading_divergence(h1, h2):
    """Returns the absolute angular difference between two headings (0-180°)."""
    diff = abs(h1 - h2) % 360
    if diff > 180:
        diff = 360 - diff
    return diff

class RiskEngine:
    def __init__(self):
        self.neighbor_table = {}
        # Heading divergence threshold: beyond this, cars are not on a collision course
        self.heading_threshold_deg = 45.0

    def update_neighbor(self, packet):
        self.neighbor_table[packet.vehicle_id] = packet

    def calculate_risk(self, local_state, simulated_distance=50.0):
        highest_risk = RiskLevel.NORMAL
        min_ttc = float('inf')
        triggering_event = None

        local_heading = local_state.get('heading', 0.0)
        local_speed_ms = local_state['speed']  # m/s (already in m/s in local state)

        for neighbor_id, packet in self.neighbor_table.items():
            neighbor_speed_ms = packet.speed
            neighbor_heading = packet.heading

            # --- Heading-Aware Collision Gate ---
            # If heading divergence > threshold, they're not on a collision course
            div = heading_divergence(local_heading, neighbor_heading)
            if div > self.heading_threshold_deg:
                # Different lanes / diverging paths — TTC is irrelevant, skip alarming
                continue

            # Both cars are roughly co-directional — compute closing speed
            # Component of relative velocity along the line of approach
            closing_speed = local_speed_ms - neighbor_speed_ms

            if closing_speed > 0.1:  # Only if we're actually closing in
                ttc = simulated_distance / closing_speed
            else:
                ttc = float('inf')

            min_ttc = min(min_ttc, ttc)

            # Adaptive hazard threshold based on speed of the other car
            # (Faster NPC = bigger danger bubble)
            adaptive_dist_threshold = max(30.0, neighbor_speed_ms * 3.6 * 1.5)  # km/h * 1.5m buffer

            if packet.event != 0:
                triggering_event = packet.event

            if ttc < 1.5:
                risk = RiskLevel.CRITICAL
            elif ttc < 3.0:
                risk = RiskLevel.WARNING
            elif ttc <= 5.0:
                risk = RiskLevel.CAUTION
            else:
                risk = RiskLevel.NORMAL

            if self._risk_value(risk) > self._risk_value(highest_risk):
                highest_risk = risk

        # Event-based risk override (only if heading-aligned)
        if triggering_event == 4:  # CRASH
            highest_risk = RiskLevel.WARNING
        elif triggering_event == 2 and highest_risk == RiskLevel.NORMAL:  # HARSH_BRAKING
            highest_risk = RiskLevel.CAUTION

        return highest_risk, min_ttc, triggering_event

    def _risk_value(self, risk):
        values = {RiskLevel.NORMAL: 0, RiskLevel.CAUTION: 1, RiskLevel.WARNING: 2, RiskLevel.CRITICAL: 3}
        return values.get(risk, 0)
