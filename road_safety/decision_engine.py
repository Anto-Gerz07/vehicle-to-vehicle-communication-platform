"""decision_engine.py - Lane and pothole decision logic."""

import time


class DecisionEngine:
    def decide(
        self,
        lane: str,
        pothole: tuple[bool, float],
    ) -> dict:
        """Build a result packet from the lane and pothole results."""
        pothole_confirmed, pothole_conf = pothole

        return {
            "lane": lane,
            "pothole": round(float(pothole_conf), 3)
            if pothole_confirmed else 0.0,
            "alert": "POTHOLE" if pothole_confirmed else "NONE",
            "ts": int(time.time()),
        }

    @staticmethod
    def is_critical(packet: dict) -> bool:
        """Return True only for a pothole warning."""
        return packet.get("alert") == "POTHOLE"