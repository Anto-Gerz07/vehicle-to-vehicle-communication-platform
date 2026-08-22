"""
flood_detector.py — MobileNetV2 binary road-flood classifier.

Classes:
  0 — Normal road
  1 — Flooded road

Model path (from config):
  models/flood.pth  ← fine-tuned weights (created by scripts/train_flood.py)

If the weights file is missing the detector returns confidence 0.0 and
prints a one-time warning until you run the training script.

GPU acceleration: automatically uses CUDA if available.
"""

import os
from dataclasses import dataclass
from typing import Optional

import numpy as np

import config

try:
    import torch
    import torch.nn as nn
    from torchvision import transforms, models
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


@dataclass
class FloodResult:
    flooded: bool = False
    confidence: float = 0.0    # P(flooded)


class FloodDetector:
    """
    MobileNetV2 binary classifier: Normal Road vs Flooded Road.

    Call detect(frame) → FloodResult.  Temporal smoothing is handled by
    temporal_filter.py — this class returns raw per-frame probabilities.
    """

    _warned = False

    def __init__(self):
        self._model  = None
        self._device = self._pick_device()
        self._transform = self._build_transform()
        self._load_model()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, frame: np.ndarray) -> FloodResult:
        """
        Run flood classification on a BGR frame.
        Returns FloodResult with P(flooded) probability.
        """
        if self._model is None:
            return FloodResult()

        tensor = self._preprocess(frame)

        with torch.no_grad():
            logits = self._model(tensor)
            probs  = torch.softmax(logits, dim=1)
            # class 0: flooded, class 1: normal
            flood_prob = float(probs[0, 0].item())

        return FloodResult(
            flooded=flood_prob >= config.FLOOD_CONF_THRESHOLD,
            confidence=flood_prob,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_model(self):
        if not TORCH_AVAILABLE:
            if not FloodDetector._warned:
                print(
                    "[FloodDetector] WARNING: 'torch' / 'torchvision' not installed. "
                    "Run: pip install torch torchvision"
                )
                FloodDetector._warned = True
            return

        model_path = config.FLOOD_MODEL_PATH
        if not os.path.exists(model_path):
            if not FloodDetector._warned:
                print(
                    f"[FloodDetector] Fine-tuned weights not found at '{model_path}'.\n"
                    "  Run scripts/train_flood.py to train the flood classifier.\n"
                    "  Flood detection disabled until weights are present."
                )
                FloodDetector._warned = True
            return

        print(f"[FloodDetector] Loading model from {model_path}")
        model = models.mobilenet_v2(weights=None)
        # Replace classifier head for binary classification
        in_features = model.classifier[1].in_features
        model.classifier[1] = nn.Linear(in_features, 2)
        try:
            state = torch.load(model_path, map_location=self._device, weights_only=False)
        except TypeError:
            # Older PyTorch versions don't have the weights_only parameter
            state = torch.load(model_path, map_location=self._device)
        model.load_state_dict(state)
        model.to(self._device)
        model.eval()
        self._model = model
        print(f"[FloodDetector] Model ready on {self._device}")

    def _preprocess(self, frame: np.ndarray) -> "torch.Tensor":
        """Convert BGR frame → normalised tensor on the target device."""
        import cv2
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        from PIL import Image
        pil = Image.fromarray(rgb)
        tensor = self._transform(pil).unsqueeze(0).to(self._device)
        return tensor

    def _build_transform(self):
        if not TORCH_AVAILABLE:
            return None
        size = config.FLOOD_INPUT_SIZE
        return transforms.Compose([
            transforms.Resize((size, size)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std =[0.229, 0.224, 0.225],
            ),
        ])

    @staticmethod
    def _pick_device() -> str:
        if TORCH_AVAILABLE and torch.cuda.is_available():
            print("[FloodDetector] CUDA available — using GPU")
            return "cuda"
        print("[FloodDetector] CUDA not available — using CPU")
        return "cpu"
