# Road Safety Vision Pipeline

Real-time webcam-based road hazard detection system.
Detects **lane position**, **potholes**, and **flooded roads** on a laptop GPU
and sends compact results to an ESP32 over USB serial for V2V broadcasting.

---

## Architecture

```
Webcam (720p / 1080p)
        │
        ▼
  ┌─────────────┐
  │  camera.py  │  Frame capture + FPS tracking
  └──────┬──────┘
         │ raw BGR frames
    ┌────┴────────────────┐
    │                     │
┌───▼──────┐   ┌──────────▼────────┐   ┌─────────────▼──────┐
│  lane    │   │   pothole         │   │   flood             │
│ detector │   │   detector        │   │   detector          │
│ (OpenCV) │   │   (YOLOv8-nano)   │   │   (MobileNetV2)    │
└───┬──────┘   └──────────┬────────┘   └─────────────┬──────┘
    │                     │                           │
    └──────────┬──────────┘───────────────────────────┘
               ▼
      temporal_filter.py
        (LaneFilter + ConfidenceFilter)
               │
               ▼
       decision_engine.py
               │
        ┌──────┴──────┐
        │             │
  HUD Display    serial_esp32.py
  (OpenCV)           │
                      ▼
                   ESP32
```

---

## Quick Start

### 1. Activate the environment

The virtual environment is pre-configured in `.venv/` with Python 3.12 + CUDA 12.1 torch.

```bash
cd road_safety
source .venv/bin/activate
```

Or run directly without activating:
```bash
.venv/bin/python main.py
```

### 2. Train the models (for full accuracy)

#### Pothole detector (YOLOv8-nano, Roboflow dataset)
```bash
export ROBOFLOW_API_KEY=your_key_here   # free account at roboflow.com
.venv/bin/python scripts/train_pothole.py
```
This downloads the dataset, fine-tunes for ~50 epochs, and saves `models/pothole.pt`.
Until trained, the system runs with `yolov8n.pt` base (general object detector).

#### Flood classifier (MobileNetV2)
```bash
# 1. Download a flood/road dataset from:
#    https://www.kaggle.com/datasets/search?q=flood+road
#    https://universe.roboflow.com  (search "flooded road")
#
# 2. Arrange it as:
#    datasets/flood/train/normal/
#    datasets/flood/train/flooded/
#    datasets/flood/val/normal/
#    datasets/flood/val/flooded/

.venv/bin/python scripts/train_flood.py
```
Saves `models/flood.pth`. Until trained, flood detection returns 0.0.

### 3. Run the pipeline

```bash
.venv/bin/python main.py
```

**Keyboard shortcuts:**
| Key | Action |
|-----|--------|
| `Q` / `ESC` | Quit |
| `S` | Save current frame to `recordings/` |
| `D` | Toggle debug overlay (lane lines, ROI) |

---

## Configuration

All tunable parameters are in `config.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `CAMERA_INDEX` | `0` | Webcam device index |
| `POTHOLE_CONF_THRESHOLD` | `0.45` | Min YOLO confidence |
| `FLOOD_CONF_THRESHOLD` | `0.55` | Min flood probability |
| `SERIAL_PORT` | `/dev/ttyUSB0` | ESP32 serial port |
| `SERIAL_ENABLED` | `True` | Disable if no hardware |
| `LANE_SMOOTHING_FRAMES` | `15` | Temporal vote window |

---

## ESP32 Packet Format

One JSON object per line at 115200 baud:

```json
{"lane":"MIDDLE","pothole":0.91,"flood":0.0,"alert":"POTHOLE","ts":1724256000}
```

| Field | Values |
|-------|--------|
| `lane` | `LEFT` \| `MIDDLE` \| `RIGHT` \| `SINGLE` \| `UNKNOWN` \| `UNRELIABLE` |
| `pothole` | `0.0` (none) or EMA confidence when confirmed |
| `flood` | `0.0` (none) or EMA confidence when confirmed |
| `alert` | `NONE` \| `POTHOLE` \| `FLOOD` \| `BOTH` |
| `ts` | Unix timestamp |

---

## Running Tests

```bash
cd road_safety
pytest tests/ -v
```

---

## File Structure

```
road_safety/
├── main.py                  # Pipeline orchestrator
├── config.py                # All tunable constants
├── camera.py                # Webcam capture
├── lane_detector.py         # Classical CV lane detection
├── pothole_detector.py      # YOLOv8-nano inference
├── flood_detector.py        # MobileNetV2 classifier
├── temporal_filter.py       # Rolling-window smoothers
├── decision_engine.py       # Multi-modal fusion + alert logic
├── serial_esp32.py          # JSON-over-serial ESP32 bridge
├── requirements.txt
├── scripts/
│   ├── train_pothole.py     # Fine-tune pothole detector
│   └── train_flood.py       # Train flood classifier
├── models/                  # Trained weights (git-ignored)
├── datasets/                # Training data (git-ignored)
├── recordings/              # Saved frames/video (git-ignored)
└── tests/
    ├── test_lane_detector.py
    ├── test_temporal_filter.py
    └── test_decision_engine.py
```

---

## Processing Budget (RTX 4060, 720p input)

| Module | Target FPS | Cadence |
|--------|-----------|---------|
| Camera capture | 30 | Every frame |
| Lane detection (CV) | 30 | Every frame |
| Pothole detection (YOLO) | ~10 | Every 3rd frame |
| Flood detection (MobileNetV2) | ~5 | Every 6th frame |
