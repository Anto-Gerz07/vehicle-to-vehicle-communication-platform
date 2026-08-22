# Vision-Based Road Safety & V2V System

## 1. Project Overview

The system uses a webcam connected to a laptop for real-time road perception. The laptop performs the computationally expensive computer-vision and ML tasks, while an ESP32 receives lightweight results over USB serial.

The long-term goal is to extend this into a decentralized V2V road-safety system where detected hazards can be shared with nearby vehicles.

### Initial architecture

```text
                    USB WEBCAM
                         |
                         v
                +----------------+
                |     LAPTOP     |
                |                |
                | OpenCV         |
                | Lane Detection |
                | Pothole Model  |
                | Flood Model    |
                +-------+--------+
                        |
                  Decision Layer
                        |
              +---------+---------+
              |                   |
         Local Display       USB Serial
                                  |
                                  v
                              +-------+
                              | ESP32 |
                              +---+---+
                                  |
                    +-------------+-------------+
                    |             |             |
                   GPS           IMU           V2V
```

---

# 2. Main Objectives

The vision system should predict:

1. **Current lane position**
   - Left
   - Middle
   - Right
   - For 3-lane, 2-lane, and single-lane roads

2. **Potholes**
   - Detect potholes in the visible road
   - Estimate detection confidence
   - Eventually determine whether the pothole is ahead of the vehicle

3. **Flooded roads**
   - Initially classify road as normal/flooded
   - Later extend to water-depth/severity estimation or segmentation

The ESP32 should receive only the resulting information, not the video frames.

---

# 3. Hardware

## Laptop

Current development machine:

- CPU: AMD Ryzen 7 7840HS
- CPU cores: 8 cores / 16 threads
- GPU: NVIDIA GeForce RTX 4060 Laptop GPU
- VRAM: 8 GB
- RAM: 16 GB
- Storage: NVMe SSD
- OS: Ubuntu Linux

The RTX 4060 will be used for ML inference and model development.

## ESP32

The ESP32 will initially act as:

- Serial communication interface
- Sensor interface
- GPS interface
- IMU interface
- V2V communication node
- Warning/actuation controller

ML inference on the ESP32 is **not required for the first version**.

A future version may investigate ESP32-S3 + PSRAM for TinyML.

---

# 4. Vision Pipeline

The basic pipeline is:

```text
Camera
   |
   v
OpenCV Frame Capture
   |
   v
Frame Preprocessing
   |
   +------------------+------------------+
   |                  |                  |
   v                  v                  v
Lane Detection    Pothole Detection   Flood Detection
   |                  |                  |
   +------------------+------------------+
                      |
                      v
               Decision Engine
                      |
                      v
                Result Packet
                      |
                      v
                   ESP32
```

---

# 5. Lane Detection

## Goal

Determine which lane the vehicle is currently occupying.

Possible outputs:

```text
LANE = LEFT
LANE = MIDDLE
LANE = RIGHT
LANE = SINGLE
```

The system should support:

### Three-lane road

```text
+-------+-------+-------+
| LEFT  | MIDDLE| RIGHT |
+-------+-------+-------+
```

### Two-lane road

```text
+-------+-------+
| LEFT  | RIGHT |
+-------+-------+
```

### Single-lane road

```text
+---------------+
|    SINGLE     |
+---------------+
```

## Initial approach

Lane detection does not necessarily require a neural network.

Possible pipeline:

```text
Frame
  |
  v
Region of Interest
  |
  v
Perspective Transformation
  |
  v
Lane Marking Detection
  |
  v
Lane Boundary Estimation
  |
  v
Vehicle Center Estimation
  |
  v
L / M / R Classification
```

Start with clearly marked roads before handling difficult conditions such as:

- Curved roads
- Missing lane markings
- Shadows
- Poor lighting
- Rain
- Occluded markings

---

# 6. Pothole Detection

Pothole detection should initially use an object-detection model.

Example:

```text
Camera Frame
     |
     v
Pothole Detector
     |
     v
Bounding Box + Confidence
```

Example result:

```text
POTHOLE = TRUE
CONFIDENCE = 0.91
```

The system should eventually determine whether the detected pothole is actually in the vehicle's path.

## Future improvements

- Pothole size estimation
- Distance estimation
- Severity classification
- Tracking the same pothole across frames
- GPS tagging
- Road-hazard database

---

# 7. Flood Detection

Start with a simple classification problem:

```text
NORMAL ROAD
     vs
FLOODED ROAD
```

Possible future classes:

```text
NORMAL
WET ROAD
SHALLOW FLOOD
DEEP FLOOD
```

A later version can use segmentation to identify exactly which portion of the road is covered by water.

Example:

```text
Frame
  |
  v
Flood Segmentation
  |
  v
Water-covered road area
```

This could eventually provide an estimate such as:

```text
ROAD_WATER_COVERAGE = 35%
```

---

# 8. Temporal Filtering

The system should not make important decisions based on a single frame.

For example:

```text
Frame 1 -> Pothole confidence: 0.81
Frame 2 -> Pothole confidence: 0.87
Frame 3 -> Pothole confidence: 0.91
Frame 4 -> Pothole confidence: 0.89
```

The system can then confirm:

```text
POTHOLE DETECTED
```

Similarly, lane detection should use recent history to reduce unstable results:

```text
MIDDLE
MIDDLE
MIDDLE
MIDDLE
RIGHT
```

rather than immediately switching lanes because of one noisy frame.

---

# 9. Decision Engine

The decision engine combines the outputs of all perception modules.

Example:

```text
Lane:
RIGHT

Pothole:
TRUE
Confidence:
0.91

Flood:
FALSE
Confidence:
0.03
```

The decision engine can convert this into a compact result packet.

---

# 10. Laptop-to-ESP32 Communication

Initially use USB serial communication.

Architecture:

```text
Python
  |
  v
pyserial
  |
  v
USB
  |
  v
ESP32
```

Example text protocol:

```text
LANE,R
POTHOLE,0.91
FLOOD,0.03
```

A more structured format can use JSON:

```json
{
  "lane": "right",
  "pothole": 0.91,
  "flood": 0.03
}
```

Later, GPS and vehicle information can be added:

```json
{
  "lane": "right",
  "pothole": 0.91,
  "flood": 0.03,
  "lat": 12.8231,
  "lon": 80.0427,
  "speed": 42
}
```

The ESP32 does not need to receive the actual image.

---

# 11. GPS and IMU Integration

After the basic vision system works, integrate:

- GPS
- IMU
- Vehicle speed
- Heading

This enables hazard localization.

Example:

```text
POTHOLE
LAT = 12.8231
LON = 80.0427
CONF = 0.91
```

The ESP32 can associate the vision detection with the vehicle's current position and movement.

---

# 12. V2V Communication

The long-term goal is to share road hazards between vehicles.

## Vehicle A

```text
Camera
   |
   v
Laptop / Edge AI
   |
   v
Pothole detected
   |
   v
GPS location
   |
   v
ESP32
   |
   v
V2V broadcast
```

## Vehicle B

```text
V2V message
     |
     v
ESP32
     |
     v
Hazard processing
     |
     v
Driver warning
```

Example:

```text
WARNING: POTHOLE AHEAD

Location:
12.8231, 80.0427

Confidence:
91%
```

This creates a decentralized road-hazard sharing system.

---

# 13. Development Phases

## Phase 1 — Webcam Pipeline

- [ ] Connect webcam
- [ ] Capture frames with OpenCV
- [ ] Test 720p input
- [ ] Display live video
- [ ] Measure FPS
- [ ] Record test footage
- [ ] Save individual frames

## Phase 2 — Lane Detection

- [ ] Detect lane markings
- [ ] Define road ROI
- [ ] Estimate lane boundaries
- [ ] Estimate vehicle center
- [ ] Classify left/middle/right
- [ ] Handle two-lane roads
- [ ] Handle single-lane roads
- [ ] Add temporal filtering

## Phase 3 — Pothole Detection

- [ ] Find suitable pothole dataset
- [ ] Prepare/label data
- [ ] Train or fine-tune lightweight detector
- [ ] Test GPU inference
- [ ] Tune confidence threshold
- [ ] Add temporal confirmation
- [ ] Estimate whether pothole is in vehicle path

## Phase 4 — Flood Detection

- [ ] Find flood/road-water dataset
- [ ] Prepare training data
- [ ] Train classifier
- [ ] Test real-time inference
- [ ] Tune confidence threshold
- [ ] Experiment with segmentation

## Phase 5 — Decision Engine

- [ ] Combine lane output
- [ ] Combine pothole output
- [ ] Combine flood output
- [ ] Add temporal filtering
- [ ] Define final result format

## Phase 6 — ESP32 Communication

- [ ] Connect ESP32 over USB
- [ ] Implement serial communication
- [ ] Define packet format
- [ ] Send lane results
- [ ] Send pothole results
- [ ] Send flood results
- [ ] Display/act on received results

## Phase 7 — Sensors

- [ ] Add GPS
- [ ] Add IMU
- [ ] Add speed information
- [ ] Associate hazards with location
- [ ] Estimate hazard direction/distance

## Phase 8 — V2V

- [ ] ESP32-to-ESP32 communication
- [ ] Define V2V packet
- [ ] Broadcast detected hazards
- [ ] Receive hazards from other vehicles
- [ ] Filter duplicate/stale information
- [ ] Generate driver warnings

---

# 14. Suggested Software Structure

```text
road-safety-v2v/
|
├── main.py
|
├── camera.py
|
├── lane_detector.py
|
├── pothole_detector.py
|
├── flood_detector.py
|
├── decision_engine.py
|
├── temporal_filter.py
|
├── serial_esp32.py
|
├── config.py
|
├── models/
|
├── datasets/
|
├── recordings/
|
└── tests/
```

Each perception module should be independent.

For example:

```text
main.py
   |
   +-- camera.py
   |
   +-- lane_detector.py
   |
   +-- pothole_detector.py
   |
   +-- flood_detector.py
   |
   +-- decision_engine.py
   |
   +-- serial_esp32.py
```

This makes it possible to replace one model without rewriting the entire system.

---

# 15. Performance Strategy

The laptop has an RTX 4060 with 8 GB VRAM, so GPU inference should be used for ML models.

Do not run every model at maximum possible FPS unnecessarily.

A possible target is:

```text
Camera:              30 FPS
Lane processing:     20-30 FPS
Pothole detection:   10-20 FPS
Flood detection:     5-10 FPS
```

The exact FPS will depend on the chosen models and input resolution.

Start with 720p camera input and resize frames appropriately for each model.

---

# 16. Initial Prototype Goal

The first successful prototype should be very simple:

```text
WEBCAM
  |
  v
LAPTOP
  |
  +---- Lane: MIDDLE
  |
  +---- Pothole: 0.91
  |
  +---- Flood: 0.03
  |
  v
USB SERIAL
  |
  v
ESP32
  |
  v
Display / LED / Buzzer
```

Once this works reliably, add GPS, IMU, and eventually V2V communication.

---

# 17. Long-Term System

The final concept can become:

```text
                         VEHICLE A
                  +----------------------+
                  | Camera               |
                  |       |              |
                  |       v              |
                  | Edge AI              |
                  |       |              |
                  | Lane/Pothole/Flood   |
                  |       |              |
                  |       v              |
                  | ESP32 + GPS + IMU    |
                  +----------+-----------+
                             |
                           V2V
                             |
                             v
                  +----------+-----------+
                  | ESP32                 |
                  |                       |
                  | Receive hazard data   |
                  |                       |
                  | Generate warning     |
                  +-----------------------+
                             |
                             v
                         VEHICLE B
```

The laptop-based implementation is the **development/reference system**. Once the algorithms work, lightweight versions can potentially be moved onto embedded hardware.

---

# 18. Immediate Next Steps

Do these in order:

1. Get the webcam working in Python/OpenCV.
2. Build a live video viewer.
3. Measure actual webcam FPS.
4. Implement basic lane detection.
5. Test lane classification on recorded road footage.
6. Select and train a pothole detector.
7. Select and train a flood classifier.
8. Combine the three outputs.
9. Add temporal filtering.
10. Send the results to the ESP32 over USB serial.
11. Add GPS and IMU.
12. Implement ESP32-to-ESP32 V2V communication.
