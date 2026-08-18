import os
from .rule_engine import EVENT_NAMES
from .risk_engine import RiskLevel

class OLEDDisplay:
    def __init__(self):
        self.state = RiskLevel.NORMAL
        
    def render(self, local_speed, neighbors_count, risk, ttc=None, event=None):
        print("┌──────────────────┐")
        
        if risk == RiskLevel.NORMAL:
            print("│    V2V ACTIVE    │")
            print("│                  │")
            print(f"│ Nearby: {neighbors_count:<8} │")
            print(f"│ Speed: {int(local_speed):<2} km/h   │")
            print("│                  │")
            print("│ STATUS: NORMAL   │")
            
        elif risk == RiskLevel.CAUTION:
            print("│    V2V CAUTION   │")
            print("│                  │")
            event_name = EVENT_NAMES.get(event, "UNKNOWN").replace('_', ' ')
            print(f"│ {event_name[:16]:<16} │")
            print(f"│ Nearby: {neighbors_count:<8} │")
            if ttc and ttc != float('inf'):
                print(f"│ TTC: {ttc:.1f} sec     │")
            else:
                print("│                  │")
            print("│ BE AWARE         │")
            
        elif risk == RiskLevel.WARNING:
            print("│    !! ALERT !!   │")
            print("│                  │")
            event_name = EVENT_NAMES.get(event, "HAZARD AHEAD").replace('_', ' ')
            print(f"│ {event_name[:16]:<16} │")
            print("│                  │")
            if ttc and ttc != float('inf'):
                print(f"│ TTC: {ttc:.1f} sec     │")
            else:
                print("│                  │")
            print("│ REDUCE SPEED     │")
            
        elif risk == RiskLevel.CRITICAL:
            print("│   !!! DANGER !!! │")
            print("│                  │")
            print("│ COLLISION RISK   │")
            print("│                  │")
            if ttc and ttc != float('inf'):
                print(f"│ TTC: {ttc:.1f} sec     │")
            else:
                print("│                  │")
            print("│ SLOW DOWN!       │")
            
        print("└──────────────────┘")
