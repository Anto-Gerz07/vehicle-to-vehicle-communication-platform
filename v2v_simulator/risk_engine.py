class RiskLevel:
    NORMAL = "NORMAL"
    CAUTION = "CAUTION"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

class RiskEngine:
    def __init__(self):
        self.neighbor_table = {}

    def update_neighbor(self, packet):
        self.neighbor_table[packet.vehicle_id] = packet

    def calculate_risk(self, local_state, simulated_distance=50.0):
        # In a real system, distance would come from GPS/UWB
        highest_risk = RiskLevel.NORMAL
        min_ttc = float('inf')
        triggering_event = None
        
        for neighbor_id, packet in self.neighbor_table.items():
            # Very basic mock simulation logic for TTC
            # Assuming vehicles are moving in the same direction for the demo
            closing_speed = (local_state['speed'] - packet.speed) / 3.6  # convert km/h to m/s
            
            if closing_speed > 0:
                ttc = simulated_distance / closing_speed
            else:
                ttc = float('inf')
                
            min_ttc = min(min_ttc, ttc)
            
            if packet.event != 0: # 0 is Event.NORMAL
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

        # Event-based risk override
        if triggering_event == 4: # ACCIDENT
            highest_risk = RiskLevel.WARNING
        elif triggering_event == 2 and highest_risk == RiskLevel.NORMAL: # HARSH_BRAKING
            highest_risk = RiskLevel.CAUTION

        return highest_risk, min_ttc, triggering_event

    def _risk_value(self, risk):
        values = {RiskLevel.NORMAL: 0, RiskLevel.CAUTION: 1, RiskLevel.WARNING: 2, RiskLevel.CRITICAL: 3}
        return values.get(risk, 0)
