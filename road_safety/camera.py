"""
camera.py — Webcam capture wrapper.

Responsibilities:
  - Open the camera at the configured index and resolution
  - Provide read() → raw BGR frame
  - Track and report actual FPS
  - Optional: save frames to recordings/
"""

import cv2
import time
import os
from pathlib import Path

import config


class Camera:
    """Thread-safe-ish webcam wrapper with FPS tracking."""

    def __init__(self):
        self._cap = None
        self._fps_timestamps: list[float] = []
        self._fps_window = 30          # Rolling window for FPS calc
        self._recording_dir = Path("recordings")
        self._recording_dir.mkdir(exist_ok=True)
        self._open()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read(self) -> tuple[bool, any]:
        """Return (ok, bgr_frame). ok=False means the camera dropped."""
        if self._cap is None or not self._cap.isOpened():
            self._open()
            return False, None

        ok, frame = self._cap.read()
        if ok:
            self._track_fps()
        return ok, frame

    @property
    def fps(self) -> float:
        """Measured FPS over the last N frames."""
        if len(self._fps_timestamps) < 2:
            return 0.0
        elapsed = self._fps_timestamps[-1] - self._fps_timestamps[0]
        if elapsed == 0:
            return 0.0
        return (len(self._fps_timestamps) - 1) / elapsed

    @property
    def width(self) -> int:
        return int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)) if self._cap else 0

    @property
    def height(self) -> int:
        return int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) if self._cap else 0

    def save_frame(self, frame, prefix: str = "frame") -> str:
        """Save a single frame to recordings/. Returns the saved path."""
        ts = int(time.time() * 1000)
        path = self._recording_dir / f"{prefix}_{ts}.jpg"
        cv2.imwrite(str(path), frame)
        return str(path)

    def release(self):
        if self._cap:
            self._cap.release()
            self._cap = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.release()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _open(self):
        cap = cv2.VideoCapture(config.CAMERA_INDEX)
        if not cap.isOpened():
            raise RuntimeError(
                f"Cannot open video source {config.CAMERA_INDEX!r}. "
                "For a webcam, check that it is connected; for a video file, "
                "check that the path exists and is readable."
            )
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  config.CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS,          config.CAMERA_FPS)
        # Minimize buffer lag
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap = cap
        print(
            f"[Camera] Opened: {self.width}x{self.height} "
            f"@ {config.CAMERA_FPS} FPS requested"
        )

    def _track_fps(self):
        now = time.time()
        self._fps_timestamps.append(now)
        if len(self._fps_timestamps) > self._fps_window:
            self._fps_timestamps.pop(0)
