"""
decision_engine.py — Combines stabilised perception outputs into a result packet.

Inputs (already temporally smoothed):
  - lane:    str   — LEFT | MIDDLE | RIGHT | SINGLE | UNKNOWN
  - pothole: (bool, float)  — (confirmed, ema_confidence)
  - flood:   (bool, float)  — (confirmed, ema_confidence)

Output dict (sent to ESP32 and shown on HUD):
  {
    "lane":    "MIDDLE",
    "pothole": 0.91,       # 0.0 if not detected
    "flood":   0.03,       # 0.0 if not detected
    "alert":   "POTHOLE",  # or "FLOOD" | "BOTH" | "NONE"
    "ts":      1724256000
  }

Cross-modal logic:
  - If flood is confirmed (high water), lane detection is marked UNRELIABLE.
  - Alert priority: BOTH > POTHOLE > FLOOD > NONE
"""

import time
from typing import Optional


class DecisionEngine:

    def decide(
        self,
        lane: str,
        pothole: tuple[bool, float],
        flood: tuple[bool, float],
    ) -> dict:
        """
        Build the final result packet.

        Args:
            lane:    Smoothed lane label string.
            pothole: (confirmed, ema_confidence) from ConfidenceFilter.
            flood:   (confirmed, ema_confidence) from ConfidenceFilter.

        Returns:
            Result dict suitable for JSON serialisation.
        """
        pothole_confirmed, pothole_conf = pothole
        flood_confirmed,   flood_conf   = flood

        # Cross-modal: heavy flooding makes lane detection unreliable
        effective_lane = lane
        if flood_confirmed and flood_conf > 0.75:
            effective_lane = "UNRELIABLE"

        # Alert level
        if pothole_confirmed and flood_confirmed:
            alert = "BOTH"
        elif pothole_confirmed:
            alert = "POTHOLE"
        elif flood_confirmed:
            alert = "FLOOD"
        else:
            alert = "NONE"

        return {
            "lane":    effective_lane,
            "pothole": round(pothole_conf, 3) if pothole_confirmed else 0.0,
            "flood":   round(flood_conf,   3) if flood_confirmed   else 0.0,
            "alert":   alert,
            "ts":      int(time.time()),
        }

    @staticmethod
    def is_critical(packet: dict) -> bool:
        """True if the packet warrants an immediate driver warning."""
        return packet.get("alert") in {"POTHOLE", "FLOOD", "BOTH"}
