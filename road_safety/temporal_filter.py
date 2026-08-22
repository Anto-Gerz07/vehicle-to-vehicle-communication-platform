"""
temporal_filter.py — Rolling-window smoother for all three perception outputs.

The individual detectors return raw per-frame predictions which can be noisy.
This module stabilises them:

  LaneFilter      — majority vote over last N frames
  ConfidenceFilter — EMA + confirmation counter for probability-valued outputs
                     (used for both pothole and flood)

All state is kept here; the detectors themselves are stateless per-frame.
"""

from collections import deque
from typing import Optional

import config


class LaneFilter:
    """
    Majority-vote smoothing for lane classification strings.

    Prevents single noisy frames from causing lane switches.
    """

    VALID_LANES = {"LEFT", "MIDDLE", "RIGHT", "SINGLE", "UNKNOWN"}

    def __init__(self, window: int = config.LANE_SMOOTHING_FRAMES):
        self._window = window
        self._buf: deque[str] = deque(maxlen=window)

    def update(self, raw: str) -> str:
        """Push a new raw lane prediction; return the smoothed label."""
        if raw not in self.VALID_LANES:
            raw = "UNKNOWN"
        self._buf.append(raw)

        if not self._buf:
            return "UNKNOWN"

        # Majority vote — ignore UNKNOWN when computing
        counts: dict[str, int] = {}
        for v in self._buf:
            if v != "UNKNOWN":
                counts[v] = counts.get(v, 0) + 1

        if not counts:
            return "UNKNOWN"

        return max(counts, key=counts.get)

    def reset(self):
        self._buf.clear()


class ConfidenceFilter:
    """
    EMA smoothing + consecutive-frame confirmation for probability outputs.

    Used for both pothole and flood confidence scores.

    A detection is 'confirmed' when the smoothed EMA score stays above
    `threshold` for at least `confirm_frames` consecutive frames.
    """

    def __init__(
        self,
        name: str,
        threshold: float,
        ema_alpha: float = 0.4,
        confirm_frames: int = 3,
    ):
        self._name           = name
        self._threshold      = threshold
        self._alpha          = ema_alpha   # EMA weight for newest sample
        self._confirm_frames = confirm_frames

        self._ema       = 0.0
        self._confirmed = 0     # consecutive frames above threshold
        self._active    = False # current confirmed state

    def update(self, raw_confidence: float) -> tuple[bool, float]:
        """
        Push a new raw confidence; return (is_confirmed, smoothed_confidence).

        is_confirmed is True only after `confirm_frames` consecutive updates
        above the threshold; it resets to False as soon as a frame drops below.
        """
        # EMA update
        self._ema = self._alpha * raw_confidence + (1 - self._alpha) * self._ema

        if self._ema >= self._threshold:
            self._confirmed += 1
        else:
            self._confirmed = 0
            self._active    = False

        if self._confirmed >= self._confirm_frames:
            self._active = True

        return self._active, round(self._ema, 4)

    def reset(self):
        self._ema       = 0.0
        self._confirmed = 0
        self._active    = False
