"""
config.py — Central configuration for the Road Safety Vision Pipeline.

All tunable constants live here. Change values here rather than hunting
through individual modules.
"""

# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------
CAMERA_INDEX = 0              # Webcam index; use a valid video path for file input
CAMERA_WIDTH  = 1280       # Capture width in pixels
CAMERA_HEIGHT = 720        # Capture height in pixels
CAMERA_FPS    = 15         # Requested capture FPS (reduced to save compute)

# ---------------------------------------------------------------------------
# Processing cadence  (run every N-th frame to manage GPU budget)
# ---------------------------------------------------------------------------
LANE_EVERY_N_FRAMES    = 2   # Lane detection: every 2nd frame
POTHOLE_EVERY_N_FRAMES = 3   # Pothole detection: every 3rd frame


# ---------------------------------------------------------------------------
# Lane detection (classical CV)
# ---------------------------------------------------------------------------
LANE_ROI_TOP_FRACTION    = 0.55   # ROI starts this far down the frame (0–1)
LANE_CANNY_LOW           = 50
LANE_CANNY_HIGH          = 150
LANE_BLUR_KERNEL         = 5      # Gaussian blur kernel size (must be odd)
LANE_HOUGH_THRESHOLD     = 50     # Accumulator threshold for Hough lines
LANE_HOUGH_MIN_LENGTH    = 80     # Minimum line length in pixels
LANE_HOUGH_MAX_GAP       = 30     # Maximum gap between line segments
LANE_MIN_SLOPE           = 0.3    # Reject near-horizontal lines (abs slope)
LANE_SMOOTHING_FRAMES    = 8      # Temporal majority-vote window size (reduced for 15 FPS)

# ---------------------------------------------------------------------------
# Pothole detection (YOLOv8-nano)
# ---------------------------------------------------------------------------
POTHOLE_MODEL_PATH   = "models/pothole.pt"  # Fine-tuned weights
POTHOLE_BASE_MODEL   = "yolov8n.pt"         # Fallback base weights
POTHOLE_CONF_THRESHOLD = 0.60               # Min confidence to report (increased)
POTHOLE_IOU_THRESHOLD  = 0.45               # NMS IoU threshold
POTHOLE_SMOOTH_FRAMES  = 7                  # EMA window size (increased)
POTHOLE_CONFIRM_FRAMES = 3 
POTHOLE_IMAGE_SIZE = 512                 # Frames above threshold to confirm

# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# ESP32 Serial
# ---------------------------------------------------------------------------
SERIAL_PORT     = "/dev/ttyUSB0"   # Update to your actual device
SERIAL_BAUDRATE = 115200
SERIAL_TIMEOUT  = 1.0              # seconds
SERIAL_ENABLED  = False            # Set False to run without hardware (disabled for now)

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
DISPLAY_ENABLED     = True
DISPLAY_WINDOW_NAME = "Road Safety — V2V"
DISPLAY_SCALE       = 1.0           # Scale factor for the output window
HUD_FONT_SCALE      = 0.65
HUD_THICKNESS       = 2
PROCESS_WIDTH = 960
PROCESS_HEIGHT = 540