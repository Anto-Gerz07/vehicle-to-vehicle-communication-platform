"""
tests/test_temporal_filter.py — Unit tests for LaneFilter and ConfidenceFilter.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from temporal_filter import LaneFilter, ConfidenceFilter


class TestLaneFilter:
    def test_majority_vote_basic(self):
        f = LaneFilter(window=5)
        for _ in range(4):
            f.update("MIDDLE")
        f.update("RIGHT")   # one noisy frame
        assert f.update("MIDDLE") == "MIDDLE"

    def test_single_result(self):
        f = LaneFilter(window=5)
        result = f.update("LEFT")
        assert result == "LEFT"

    def test_unknown_ignored_in_vote(self):
        f = LaneFilter(window=5)
        f.update("UNKNOWN")
        f.update("UNKNOWN")
        f.update("LEFT")
        assert f.update("LEFT") == "LEFT"

    def test_all_unknown(self):
        f = LaneFilter(window=5)
        for _ in range(5):
            f.update("UNKNOWN")
        assert f.update("UNKNOWN") == "UNKNOWN"

    def test_reset(self):
        f = LaneFilter(window=5)
        for _ in range(4):
            f.update("RIGHT")
        f.reset()
        assert f.update("LEFT") == "LEFT"


class TestConfidenceFilter:
    def test_not_confirmed_below_threshold(self):
        f = ConfidenceFilter("test", threshold=0.5, ema_alpha=1.0, confirm_frames=3)
        confirmed, conf = f.update(0.3)
        assert not confirmed

    def test_confirmed_after_n_frames(self):
        f = ConfidenceFilter("test", threshold=0.4, ema_alpha=1.0, confirm_frames=3)
        f.update(0.9)
        f.update(0.9)
        confirmed, _ = f.update(0.9)
        assert confirmed

    def test_resets_on_drop(self):
        f = ConfidenceFilter("test", threshold=0.4, ema_alpha=1.0, confirm_frames=3)
        f.update(0.9); f.update(0.9); f.update(0.9)
        # One frame drops below threshold
        confirmed, _ = f.update(0.1)
        assert not confirmed

    def test_ema_smoothing(self):
        """EMA should smooth out a single spike."""
        f = ConfidenceFilter("test", threshold=0.5, ema_alpha=0.2, confirm_frames=3)
        f.update(0.0)
        f.update(0.0)
        # Single spike — EMA should stay well below 0.5
        confirmed, conf = f.update(1.0)
        assert conf < 0.5
        assert not confirmed
