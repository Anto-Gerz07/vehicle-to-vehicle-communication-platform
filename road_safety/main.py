"""
main.py — Road Safety Vision Pipeline orchestrator.

Run:
    python main.py

Keyboard shortcuts in the display window:
    Q / ESC  — quit
    S        — save current frame to recordings/
    D        — toggle debug overlay (lane lines, ROI)
"""

import sys
import time
import cv2
import numpy as np

import config
from camera         import Camera
from lane_detector  import LaneDetector
from pothole_detector import PotholeDetector

from temporal_filter import LaneFilter, ConfidenceFilter
from decision_engine import DecisionEngine
from serial_esp32   import SerialESP32


# ---------------------------------------------------------------------------
# HUD colour palette
# ---------------------------------------------------------------------------
_C = {
    "bg":      (18,  18,  18),
    "ok":      (80,  220, 100),
    "warn":    (40,  180, 255),
    "danger":  (50,   50, 220),
    "text":    (230, 230, 230),
    "dim":     (120, 120, 120),
    "lane":    (255, 200,  50),
}

_FONT = cv2.FONT_HERSHEY_SIMPLEX


def _put(frame, text, pos, colour=_C["text"], scale=None, thickness=None):
    scale     = scale     or config.HUD_FONT_SCALE
    thickness = thickness or config.HUD_THICKNESS
    cv2.putText(frame, text, pos, _FONT, scale, colour, thickness, cv2.LINE_AA)


def _draw_hud(frame, result: dict, fps: float, serial_ok: bool, debug: bool):
    """Overlay the telemetry HUD bar at the bottom of the frame."""
    h, w = frame.shape[:2]
    bar_h = 75

    # Semi-transparent bottom bar
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, h - bar_h), (w, h), _C["bg"], -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

    # Alert colour
    alert = result.get("alert", "NONE")
    alert_col = _C["danger"] if alert == "POTHOLE" else _C["ok"]

    # Row 1: Lane | Pothole
    y1 = h - bar_h + 28
    _put(frame, f"LANE: {result['lane']}", (16, y1), _C["lane"], 0.75, 2)
    _put(
        frame,
        f"POTHOLE: {result['pothole']:.2f}",
        (w // 2, y1),
        _C["danger"] if result["pothole"] > 0 else _C["dim"],
    )

    # Row 2: Alert | FPS | Serial
    y2 = h - bar_h + 62
    _put(frame, f"! {alert}",         (16, y2), alert_col, 0.7, 2)
    _put(frame, f"FPS: {fps:.1f}",    (w // 3, y2), _C["text"])
    serial_col = _C["ok"] if serial_ok else _C["dim"]
    _put(frame, f"SERIAL: {'OK' if serial_ok else 'OFF'}", (2 * w // 3, y2), serial_col)

    # Top-right: debug indicator
    if debug:
        _put(frame, "[DEBUG]", (w - 100, 24), _C["dim"], 0.55, 1)


def main():
    print("=" * 60)
    print("  Road Safety Vision Pipeline")
    print("  Press Q / ESC to quit | S to save frame | D for debug")
    print("=" * 60)

    camera   = Camera()
    lane_det = LaneDetector()
    pot_det  = PotholeDetector()
    

    lane_filter    = LaneFilter(window=config.LANE_SMOOTHING_FRAMES)
    pot_filter     = ConfidenceFilter(
        "pothole",
        threshold      = config.POTHOLE_CONF_THRESHOLD,
        confirm_frames = config.POTHOLE_CONFIRM_FRAMES,
    )
    

    engine = DecisionEngine()
    bridge = SerialESP32()

    frame_num   = 0
    debug_mode  = False
    last_packet = {}

    # Cached raw results — only update on cadence frames
    lane_raw    = None
    pot_raw     = None
    

    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                print("[main] Camera dropped — retrying...")
                time.sleep(0.05)
                continue

            frame_num += 1
            process_frame = cv2.resize(
                frame,
                (config.PROCESS_WIDTH, config.PROCESS_HEIGHT),
                interpolation=cv2.INTER_AREA,
            )

            # ----------------------------------------------------------
            # Run detectors on their respective cadences
            # ----------------------------------------------------------
            if frame_num % config.LANE_EVERY_N_FRAMES == 0:
                lane_raw = lane_det.detect(process_frame)

            if frame_num % config.POTHOLE_EVERY_N_FRAMES == 0:
                pot_raw = pot_det.detect(process_frame)

            

            # ----------------------------------------------------------
            # Temporal filtering
            # ----------------------------------------------------------
            smoothed_lane    = lane_filter.update(
                lane_raw.lane if lane_raw else "UNKNOWN"
            )
            pot_confirmed, pot_conf = pot_filter.update(
                pot_raw.confidence if pot_raw else 0.0
            )
            

            # ----------------------------------------------------------
            # Decision engine
            # ----------------------------------------------------------
            packet = engine.decide(
                lane=smoothed_lane,
                pothole=(pot_confirmed, pot_conf),
            )

            # ----------------------------------------------------------
            # Serial send (only send when packet changes to reduce noise)
            # ----------------------------------------------------------
            if packet != last_packet:
                bridge.send(packet)
                last_packet = packet

            # ----------------------------------------------------------
            # Display
            # ----------------------------------------------------------
            if config.DISPLAY_ENABLED:
                display = frame.copy()

                # Overlay lane debug lines if debug mode is on
                if debug_mode and lane_raw and lane_raw.debug_frame is not None:
                    display = lane_raw.debug_frame.copy()

                # Overlay pothole bounding box
                if pot_raw and pot_raw.bbox and pot_confirmed:
                    x1, y1, x2, y2 = pot_raw.bbox

                    sx = frame.shape[1] / config.PROCESS_WIDTH
                    sy = frame.shape[0] / config.PROCESS_HEIGHT

                    x1, x2 = int(x1 * sx), int(x2 * sx)
                    y1, y2 = int(y1 * sy), int(y2 * sy)

                    cv2.rectangle(display, (x1, y1), (x2, y2), _C["danger"], 3)
                    _put(
                        display,
                        f"POTHOLE {pot_conf:.2f}",
                        (x1, max(y1 - 10, 20)),
                        _C["danger"],
                        0.65,
                        2,
                    )

                _draw_hud(display, packet, camera.fps, bridge.connected, debug_mode)

                scale = config.DISPLAY_SCALE
                if scale != 1.0:
                    dh, dw = display.shape[:2]
                    display = cv2.resize(display, (int(dw * scale), int(dh * scale)))

                cv2.imshow(config.DISPLAY_WINDOW_NAME, display)

                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):    # Q or ESC
                    break
                elif key == ord("s"):
                    path = camera.save_frame(frame)
                    print(f"[main] Saved frame → {path}")
                elif key == ord("d"):
                    debug_mode = not debug_mode
                    print(f"[main] Debug mode: {debug_mode}")

    except KeyboardInterrupt:
        print("\n[main] Interrupted by user")
    finally:
        camera.release()
        bridge.close()
        cv2.destroyAllWindows()
        print("[main] Shutdown complete")


if __name__ == "__main__":
    main()
