"""
pothole_detector.py — YOLOv8-nano pothole detector.

Model path (from config):
  models/pothole.pt  ← fine-tuned weights (created by scripts/train_pothole.py)
  yolov8n.pt         ← fallback base weights (Ultralytics auto-download)

If neither is available the detector returns confidence 0.0 (no detection)
and prints a one-time warning.

GPU acceleration: automatically uses CUDA if available.
"""

import os
import warnings
from dataclasses import dataclass
from typing import Optional

import numpy as np

import config

try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False


@dataclass
class PotholeResult:
    detected: bool = False
    confidence: float = 0.0            # Highest-confidence detection this frame
    bbox: Optional[tuple] = None       # (x1, y1, x2, y2) in pixels, or None
    annotated_frame: Optional[np.ndarray] = None


class PotholeDetector:
    """
    YOLOv8-nano based pothole detector.

    Call detect(frame) → PotholeResult.  Each call is independent; temporal
    smoothing is handled by temporal_filter.py.
    """

    _warned = False   # class-level flag to print the missing-model warning once

    def __init__(self):
        self._model = None
        self._device = self._pick_device()
        self._load_model()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, frame: np.ndarray) -> PotholeResult:
        """Run pothole detection on a BGR frame.

        Only the bottom portion of the frame is passed to YOLO — potholes
        are always on the ground, so processing the sky wastes compute.
        """
        if self._model is None:
            return PotholeResult()

        h, w = frame.shape[:2]
        # Only look at the bottom 55% of the frame (road area)
        roi_top = int(h * 0.45)
        roi = frame[roi_top:, :]

        results = self._model.predict(
            source=roi,
            conf=config.POTHOLE_CONF_THRESHOLD,
            iou=config.POTHOLE_IOU_THRESHOLD,
            device=self._device,
            verbose=False,
        )

        return self._parse(results, frame, y_offset=roi_top)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_model(self):
        if not ULTRALYTICS_AVAILABLE:
            if not PotholeDetector._warned:
                print(
                    "[PotholeDetector] WARNING: 'ultralytics' not installed. "
                    "Run: pip install ultralytics"
                )
                PotholeDetector._warned = True
            return

        fine_tuned = config.POTHOLE_MODEL_PATH
        base       = config.POTHOLE_BASE_MODEL

        if os.path.exists(fine_tuned):
            print(f"[PotholeDetector] Loading fine-tuned model: {fine_tuned}")
            self._model = YOLO(fine_tuned)
        elif os.path.exists(base):
            print(f"[PotholeDetector] Fine-tuned model not found. Using base: {base}")
            self._model = YOLO(base)
        else:
            if not PotholeDetector._warned:
                print(
                    "[PotholeDetector] No model weights found.\n"
                    f"  Fine-tuned: {fine_tuned}  ← run scripts/train_pothole.py\n"
                    f"  Base:       {base}         ← will be auto-downloaded by ultralytics\n"
                    "  Pothole detection disabled until a model is available."
                )
                PotholeDetector._warned = True
            # Attempt to download yolov8n.pt automatically
            try:
                warnings.filterwarnings("ignore")
                self._model = YOLO(base)   # ultralytics auto-downloads
                print(f"[PotholeDetector] Auto-downloaded base model: {base}")
            except Exception as e:
                print(f"[PotholeDetector] Auto-download failed: {e}")
                self._model = None

    def _parse(self, results, frame: np.ndarray, y_offset: int = 0) -> PotholeResult:
        """Extract best detection from YOLO results.
        
        y_offset: pixels to add to y coordinates (for ROI-cropped inputs).
        """
        best_conf = 0.0
        best_bbox = None

        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                conf = float(box.conf[0])
                if conf > best_conf:
                    best_conf = conf
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    # Translate back to full-frame coordinates
                    best_bbox = (int(x1), int(y1) + y_offset, int(x2), int(y2) + y_offset)

        annotated = None
        if best_bbox is not None:
            annotated = frame.copy()
            x1, y1, x2, y2 = best_bbox
            import cv2
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 60, 255), 3)
            cv2.putText(
                annotated,
                f"Pothole {best_conf:.2f}",
                (x1, max(y1 - 10, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7, (0, 60, 255), 2, cv2.LINE_AA,
            )

        return PotholeResult(
            detected=best_conf >= config.POTHOLE_CONF_THRESHOLD,
            confidence=best_conf,
            bbox=best_bbox,
            annotated_frame=annotated,
        )

    @staticmethod
    def _pick_device() -> str:
        try:
            import torch
            if torch.cuda.is_available():
                print("[PotholeDetector] CUDA available — using GPU")
                return "cuda"
        except ImportError:
            pass
        print("[PotholeDetector] CUDA not available — using CPU")
        return "cpu"
