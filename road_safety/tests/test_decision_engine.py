"""
tests/test_decision_engine.py — Unit tests for DecisionEngine.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from decision_engine import DecisionEngine


engine = DecisionEngine()


class TestDecisionEngine:
    def _decide(self, lane, pothole):
        return engine.decide(lane, pothole)

    def test_all_clear(self):
        p = self._decide("MIDDLE", (False, 0.0))
        assert p["alert"] == "NONE"
        assert p["pothole"] == 0.0

    def test_pothole_alert(self):
        p = self._decide("MIDDLE", (True, 0.87))
        assert p["alert"] == "POTHOLE"
        assert p["pothole"] == 0.87

    def test_is_critical_true(self):
        p = {"alert": "POTHOLE"}
        assert DecisionEngine.is_critical(p)

    def test_is_critical_false(self):
        p = {"alert": "NONE"}
        assert not DecisionEngine.is_critical(p)

    def test_timestamp_present(self):
        p = self._decide("MIDDLE", (False, 0.0))
        assert "ts" in p
        assert isinstance(p["ts"], int)
