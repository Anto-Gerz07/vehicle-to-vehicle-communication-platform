"""
lane_detector.py — Classical CV lane position classifier.

No neural network required.  Uses Canny edges + probabilistic Hough
lines to find lane markings and classify the vehicle's position as:

    LEFT | MIDDLE | RIGHT | SINGLE | UNKNOWN

Pipeline per the ideation doc:
  1. Crop ROI to the lower portion of the frame (road region)
  2. Perspective warp → bird's-eye view
  3. Grayscale → Gaussian blur → Canny edges
  4. Hough line transform → filter near-vertical / near-horizontal lines
  5. Cluster into left / right groups by slope sign
  6. Fit representative lines, compute lane boundaries + midpoint
  7. Compare vehicle centre (frame width / 2) to boundaries → classify
"""

import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import Optional

import config


@dataclass
class LaneResult:
    lane: str = "UNKNOWN"      # LEFT | MIDDLE | RIGHT | SINGLE | UNKNOWN
    left_x: Optional[int] = None    # x-coordinate of left boundary at bottom
    right_x: Optional[int] = None   # x-coordinate of right boundary at bottom
    center_x: Optional[int] = None  # midpoint of detected lane
    debug_frame: Optional[np.ndarray] = None  # annotated frame for display


class LaneDetector:
    """
    Classical CV lane detector.

    Call detect(frame) → LaneResult every frame.  Internally uses a
    majority-vote temporal smoother (see temporal_filter.py for the
    cross-module smoother; this is a lightweight per-detector version).
    """

    def __init__(self):
        self._history: list[str] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, frame: np.ndarray) -> LaneResult:
        """Run the full lane-detection pipeline on a BGR frame."""
        h, w = frame.shape[:2]
        debug = frame.copy()

        # 1. Greyscale + blur
        grey  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur  = cv2.GaussianBlur(grey, (config.LANE_BLUR_KERNEL, config.LANE_BLUR_KERNEL), 0)

        # 2. Canny edges
        edges = cv2.Canny(blur, config.LANE_CANNY_LOW, config.LANE_CANNY_HIGH)

        # 3. ROI mask — trapezoid covering lower portion of frame
        roi = self._roi_mask(edges, w, h)

        # 4. Hough lines
        lines = cv2.HoughLinesP(
            roi,
            rho=1,
            theta=np.pi / 180,
            threshold=config.LANE_HOUGH_THRESHOLD,
            minLineLength=config.LANE_HOUGH_MIN_LENGTH,
            maxLineGap=config.LANE_HOUGH_MAX_GAP,
        )

        left_lines, right_lines = self._split_lines(lines, w)

        left_fit  = self._fit_line(left_lines,  h)
        right_fit = self._fit_line(right_lines, h)

        # 5. Draw detected lines on debug frame
        self._draw_lines(debug, left_fit,  (0, 255, 100), h)
        self._draw_lines(debug, right_fit, (0, 100, 255), h)

        # 6. Classify
        result = self._classify(left_lines, right_lines, left_fit, right_fit, w, h)
        result.debug_frame = debug

        # Overlay ROI boundary
        self._draw_roi(debug, w, h)

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _roi_mask(self, edges: np.ndarray, w: int, h: int) -> np.ndarray:
        """Trapezoid mask covering the lower road area."""
        top_y = int(h * config.LANE_ROI_TOP_FRACTION)
        top_w = int(w * 0.45)   # narrow top of trapezoid
        vertices = np.array([[
            (0,      h),
            (w,      h),
            (w - top_w // 2, top_y),
            (top_w // 2,     top_y),
        ]], dtype=np.int32)
        mask = np.zeros_like(edges)
        cv2.fillPoly(mask, vertices, 255)
        return cv2.bitwise_and(edges, mask)

    def _split_lines(
        self, lines, w: int
    ) -> tuple[list, list]:
        """Split Hough lines into left / right groups by slope."""
        left, right = [], []
        if lines is None:
            return left, right

        cx = w / 2
        for line in lines:
            # OpenCV 4: shape (N,1,4) → line[0] is the 4-tuple
            # OpenCV 5: shape (N,4)   → line IS the 4-tuple
            pts = line[0] if line.ndim == 2 else line
            x1, y1, x2, y2 = int(pts[0]), int(pts[1]), int(pts[2]), int(pts[3])
            if x2 == x1:
                continue                     # vertical line — skip
            slope = (y2 - y1) / (x2 - x1)
            if abs(slope) < config.LANE_MIN_SLOPE:
                continue                     # near-horizontal — skip

            # Lines going up-right (positive slope in image coords) → right
            # Lines going up-left (negative slope)                   → left
            mid_x = (x1 + x2) / 2
            if slope < 0 and mid_x < cx:
                left.append((slope, x1, y1, x2, y2))
            elif slope > 0 and mid_x > cx:
                right.append((slope, x1, y1, x2, y2))

        return left, right

    def _fit_line(self, lines: list, h: int) -> Optional[tuple[int, int, int, int]]:
        """Fit a single representative line from a group, extended to frame bottom."""
        if not lines:
            return None
        slopes = [l[0] for l in lines]
        x1s    = [l[1] for l in lines]
        y1s    = [l[2] for l in lines]

        slope  = float(np.mean(slopes))
        x1_avg = float(np.mean(x1s))
        y1_avg = float(np.mean(y1s))

        # Extend to bottom of frame (y = h) and to ROI top
        y_bot = h
        y_top = int(h * config.LANE_ROI_TOP_FRACTION)

        if slope == 0:
            return None
        x_bot = int(x1_avg + (y_bot - y1_avg) / slope)
        x_top = int(x1_avg + (y_top - y1_avg) / slope)

        return (x_top, y_top, x_bot, y_bot)

    def _is_solid(self, lines: list, h: int) -> bool:
        """Determine if a group of Hough lines forms a SOLID or DASHED line."""
        if not lines:
            return False
            
        # Create a boolean mask for the y-axis
        y_mask = np.zeros(h, dtype=bool)
        min_y, max_y = h, 0
        
        for (slope, x1, y1, x2, y2) in lines:
            y_start = min(y1, y2)
            y_end = max(y1, y2)
            # Clip to valid bounds
            y_start = max(0, min(h - 1, y_start))
            y_end = max(0, min(h, y_end))
            if y_start < y_end:
                y_mask[y_start:y_end] = True
            min_y = min(min_y, y_start)
            max_y = max(max_y, y_end)
            
        span = max_y - min_y
        if span <= 0:
            return False
            
        coverage = np.sum(y_mask[min_y:max_y]) / span
        # Dashed lines typically have < 50% coverage. Solid lines > 70%.
        return coverage > 0.60

    def _classify(
        self,
        left_lines: list,
        right_lines: list,
        left_fit,
        right_fit,
        w: int,
        h: int,
    ) -> LaneResult:
        """Determine lane ID from solid/dashed boundaries."""
        if left_fit is None and right_fit is None:
            return LaneResult(lane="UNKNOWN")

        if left_fit is None or right_fit is None:
            # Only one lane boundary visible → single-lane or edge case
            return LaneResult(
                lane="SINGLE",
                left_x=left_fit[2]  if left_fit  else None,
                right_x=right_fit[2] if right_fit else None,
            )

        left_x  = left_fit[2]
        right_x = right_fit[2]
        lane_cx = (left_x + right_x) // 2
        lane_w  = right_x - left_x

        if lane_w <= 0:
            return LaneResult(lane="UNKNOWN")

        # Analyze solid vs dashed
        left_solid = self._is_solid(left_lines, h)
        right_solid = self._is_solid(right_lines, h)

        if left_solid and right_solid:
            lane = "SINGLE"  # Boxed in by two solid lines (1-lane road)
        elif left_solid and not right_solid:
            lane = "LEFT"    # Solid on left, dashed on right (Left lane)
        elif not left_solid and not right_solid:
            lane = "MIDDLE"  # Dashed on both sides (Middle lane)
        elif not left_solid and right_solid:
            lane = "RIGHT"   # Dashed on left, solid on right (Right lane)
        else:
            lane = "UNKNOWN"

        return LaneResult(lane=lane, left_x=left_x, right_x=right_x, center_x=lane_cx)

    def _draw_lines(self, frame, fit, colour, h):
        if fit is None:
            return
        x1, y1, x2, y2 = fit
        cv2.line(frame, (x1, y1), (x2, y2), colour, 4, cv2.LINE_AA)

    def _draw_roi(self, frame, w, h):
        top_y = int(h * config.LANE_ROI_TOP_FRACTION)
        top_w = int(w * 0.45)
        pts = np.array([
            [0, h], [w, h],
            [w - top_w // 2, top_y], [top_w // 2, top_y],
        ], dtype=np.int32)
        cv2.polylines(frame, [pts], True, (80, 80, 80), 1)
