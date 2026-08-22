# Road Safety Vision Pipeline

Real-time webcam-based road hazard detection system.
Detects **lane position**, **potholes**, and **flooded roads** on a laptop GPU and sends compact results to an ESP32 over USB serial for V2V broadcasting.

---

## Architecture

```
Webcam (720p @ 15 FPS)
        │
        ▼
  ┌─────────────┐
  │  camera.py  │  Frame capture + FPS tracking
  └──────┬──────┘
         │ raw BGR frames
    ┌────┴─────────────────────┐
    │                          │
┌───▼──────┐   ┌───────────────▼──────┐   ┌─────────────▼──────┐
│  lane    │   │   pothole            │   │   flood             │
│ detector │   │   detector           │   │   detector          │
│ (OpenCV) │   │   (YOLOv8-nano)      │   │   (MobileNetV2)    │
│          │   │   ROI: bottom 55%    │   │                     │
└───┬──────┘   └───────────┬──────────┘   └──────────┬──────────┘
    │                      │                          │
    └─────────────┬─────────┘──────────────────────────┘
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
    (OpenCV)            │
                        ▼
                     ESP32
```

---

## Models

| Model | Architecture | Accuracy | Dataset |
|-------|-------------|----------|---------|
| Pothole detector | YOLOv8-nano | **88.4% mAP50** | Mendeley + Pascal VOC dataset (665 images, 80/20 split) |
| Flood classifier | MobileNetV2 | **100% val acc** | Roboflow floods dataset + dry road images |

Both models are trained via transfer learning from pre-trained ImageNet/COCO weights.

---

## Quick Start

### 1. Set up the environment

```bash
cd road_safety
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Or with the existing `.venv`:
```bash
.venv/bin/python main.py
```

### 2. Train the models

#### Pothole detector (YOLOv8-nano)

Download the dataset from [Mendeley Data](https://data.mendeley.com/datasets/tp95cdvgm8/1) and place `Potholes.zip` in `datasets/`, then:

```bash
.venv/bin/python scripts/train_pothole.py
```

Trains for 50 epochs and saves `models/pothole.pt`. To fine-tune further on new data, just place a new zip in `datasets/` and re-run — the script automatically resumes from existing weights.

#### Flood classifier (MobileNetV2)

Arrange images as:
```
datasets/flood/
├── train/
│   ├── flooded/
│   └── normal/
└── val/
    ├── flooded/
    └── normal/
```

Then run:
```bash
.venv/bin/python scripts/train_flood.py
```

Saves `models/flood.pth`. The script will auto-scrape images if the folder is missing.

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

All tunable parameters live in `config.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `CAMERA_INDEX` | `0` | Webcam device index |
| `CAMERA_FPS` | `15` | Target capture FPS |
| `POTHOLE_CONF_THRESHOLD` | `0.60` | Min YOLO confidence to report |
| `POTHOLE_EVERY_N_FRAMES` | `2` | Run pothole detection every N frames |
| `FLOOD_CONF_THRESHOLD` | `0.75` | Min flood probability to alert |
| `FLOOD_EVERY_N_FRAMES` | `5` | Run flood detection every N frames |
| `SERIAL_PORT` | `/dev/ttyUSB0` | ESP32 serial port (update to your device) |
| `SERIAL_ENABLED` | `False` | Set `True` when ESP32 is connected |

---

## ESP32 Serial Packet Format

One JSON object per line at **115200 baud**:

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
├── pothole_detector.py      # YOLOv8-nano inference (ROI-cropped)
├── flood_detector.py        # MobileNetV2 binary classifier
├── temporal_filter.py       # Rolling-window EMA smoothers
├── decision_engine.py       # Multi-modal fusion + alert logic
├── serial_esp32.py          # JSON-over-serial ESP32 bridge
├── requirements.txt
├── scripts/
│   ├── train_pothole.py     # Fine-tune pothole detector (YOLOv8)
│   └── train_flood.py       # Train flood classifier (MobileNetV2)
├── models/                  # Trained weights (git-ignored)
│   ├── pothole.pt           # YOLOv8-nano fine-tuned weights
│   └── flood.pth            # MobileNetV2 fine-tuned weights
├── datasets/                # Training data (git-ignored)
├── recordings/              # Saved frames/video (git-ignored)
└── tests/
    ├── test_lane_detector.py
    ├── test_temporal_filter.py
    └── test_decision_engine.py
```

---

## Processing Budget (RTX 4060 Laptop, 720p input)

| Module | Cadence | Effective FPS |
|--------|---------|--------------|
| Camera capture | Every frame | 15 FPS |
| Lane detection (CV) | Every frame | 15 FPS |
| Pothole detection (YOLOv8) | Every 2nd frame | ~7.5 FPS |
| Flood detection (MobileNetV2) | Every 5th frame | ~3 FPS |

> **Note:** Pothole detection processes only the **bottom 55% of the frame** (road surface area), approximately halving inference time with no accuracy loss.
