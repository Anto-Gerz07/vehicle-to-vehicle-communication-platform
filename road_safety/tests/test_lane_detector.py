"""
tests/test_lane_detector.py — Smoke tests for LaneDetector.

These tests verify the lane detector can process a synthetic frame without
crashing. Full accuracy testing requires real road footage.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import cv2
from lane_detector import LaneDetector, LaneResult


def _make_frame(w=1280, h=720) -> np.ndarray:
    """Create a minimal synthetic road frame with two white lane lines."""
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[int(h * 0.5):, :] = (60, 60, 60)      # grey road surface

    # Left lane line — diagonal white stripe
    cv2.line(frame, (w // 4, h), (w // 3, int(h * 0.6)), (200, 200, 200), 6)
    # Right lane line — diagonal white stripe
    cv2.line(frame, (3 * w // 4, h), (2 * w // 3, int(h * 0.6)), (200, 200, 200), 6)

    return frame


class TestLaneDetector:
    def setup_method(self):
        self.detector = LaneDetector()
        self.frame = _make_frame()

    def test_returns_lane_result(self):
        result = self.detector.detect(self.frame)
        assert isinstance(result, LaneResult)

    def test_lane_field_is_valid_string(self):
        result = self.detector.detect(self.frame)
        assert result.lane in {"LEFT", "MIDDLE", "RIGHT", "SINGLE", "UNKNOWN"}

    def test_debug_frame_produced(self):
        result = self.detector.detect(self.frame)
        assert result.debug_frame is not None
        assert result.debug_frame.shape == self.frame.shape

    def test_blank_frame_returns_unknown(self):
        blank = np.zeros((720, 1280, 3), dtype=np.uint8)
        result = self.detector.detect(blank)
        assert result.lane in {"SINGLE", "UNKNOWN"}

    def test_does_not_crash_on_small_frame(self):
        small = np.zeros((240, 320, 3), dtype=np.uint8)
        result = self.detector.detect(small)
        assert isinstance(result, LaneResult)
