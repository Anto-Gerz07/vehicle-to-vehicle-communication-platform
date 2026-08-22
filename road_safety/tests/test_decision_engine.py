"""
tests/test_decision_engine.py — Unit tests for DecisionEngine.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from decision_engine import DecisionEngine


engine = DecisionEngine()


class TestDecisionEngine:
    def _decide(self, lane, pothole, flood):
        return engine.decide(lane, pothole, flood)

    def test_all_clear(self):
        p = self._decide("MIDDLE", (False, 0.0), (False, 0.0))
        assert p["alert"] == "NONE"
        assert p["pothole"] == 0.0
        assert p["flood"] == 0.0

    def test_pothole_alert(self):
        p = self._decide("MIDDLE", (True, 0.87), (False, 0.0))
        assert p["alert"] == "POTHOLE"
        assert p["pothole"] == 0.87

    def test_flood_alert(self):
        p = self._decide("LEFT", (False, 0.0), (True, 0.72))
        assert p["alert"] == "FLOOD"
        assert p["flood"] == 0.72

    def test_both_alert(self):
        p = self._decide("RIGHT", (True, 0.90), (True, 0.80))
        assert p["alert"] == "BOTH"

    def test_flood_suppresses_lane(self):
        p = self._decide("MIDDLE", (False, 0.0), (True, 0.80))
        assert p["lane"] == "UNRELIABLE"

    def test_moderate_flood_does_not_suppress_lane(self):
        # flood_conf = 0.60 is above threshold but below 0.75 suppression point
        p = self._decide("LEFT", (False, 0.0), (True, 0.60))
        assert p["lane"] == "LEFT"

    def test_is_critical_true(self):
        p = {"alert": "POTHOLE"}
        assert DecisionEngine.is_critical(p)

    def test_is_critical_false(self):
        p = {"alert": "NONE"}
        assert not DecisionEngine.is_critical(p)

    def test_timestamp_present(self):
        p = self._decide("MIDDLE", (False, 0.0), (False, 0.0))
        assert "ts" in p
        assert isinstance(p["ts"], int)
