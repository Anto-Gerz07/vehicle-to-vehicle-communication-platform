# Decentralized V2V Safety Platform — MVP Specification

## 1. Project Overview

### Project
**EV Vehicle-to-Vehicle (V2V) Communication Platform**

### Makeathon Goal

Design a decentralized communication system that enables vehicles to exchange real-time safety and traffic information without depending on cloud connectivity.

The system should support:

- Collision avoidance
- Cooperative driving
- Traffic/safety information sharing
- Edge computing
- Low-latency V2V communication

### MVP Objective

Build a working prototype using **two ESP32-based vehicle nodes**.

Each node:

1. Reads vehicle information from OBD-II/CAN where available.
2. Reads motion information from an accelerometer/gyroscope.
3. Locally detects dangerous events.
4. Broadcasts vehicle state and safety events directly to nearby vehicles.
5. Receives neighboring vehicle information.
6. Calculates local collision/safety risk.
7. Displays warnings on a small OLED.
8. Uses a buzzer/LED for immediate driver alerts.

The MVP must work **without cloud connectivity or a central server**.

---

# 2. Core Concept

Each vehicle is an independent edge node.

```text
Vehicle A
  |
  | OBD/CAN
  | IMU
  | GPS (optional)
  v
ESP32
  |
  +--> Local Edge Intelligence
  |
  +--> OLED / Buzzer
  |
  +--> ESP-NOW V2V
          |
          v
       Vehicle B
          |
          v
       ESP32
          |
          +--> Local Edge Intelligence
          |
          +--> OLED / Buzzer
```

The important architectural principle is:

> A vehicle should not need to send data to a cloud server before another vehicle can react to it.

Instead:

```text
Vehicle A
   ↓
Local sensing
   ↓
Local event detection
   ↓
Direct V2V transmission
   ↓
Vehicle B
   ↓
Local risk calculation
   ↓
Driver warning
```

---

# 3. MVP Architecture

## 3.1 Vehicle Node

Each vehicle contains:

```text
                    VEHICLE NODE
┌────────────────────────────────────────────┐
│                                            │
│   OBD-II / CAN                             │
│       │                                    │
│       ├── Speed                            │
│       ├── RPM                              │
│       └── Other available parameters       │
│                                            │
│   IMU                                    │
│       │                                    │
│       ├── Acceleration                     │
│       └── Angular velocity                 │
│                                            │
│   Optional GPS                             │
│       │                                    │
│       ├── Position                         │
│       └── Heading                          │
│                                            │
│              ┌─────────────┐               │
│              │    ESP32    │               │
│              │             │               │
│              │ Edge Engine │               │
│              │             │               │
│              │ V2V Protocol│               │
│              └──────┬──────┘               │
│                     │                      │
│              ┌──────┴──────┐               │
│              │             │               │
│            OLED          Buzzer             │
│                                            │
└────────────────────────────────────────────┘
```

---

# 4. V2V Communication

## 4.1 Recommended Technology: ESP-NOW

For the MVP, use **ESP-NOW** for direct ESP32-to-ESP32 communication.

Advantages:

- No router required
- No cloud required
- Low protocol overhead
- Direct device-to-device communication
- Suitable for short safety messages
- Supports broadcast communication
- Can later support multiple vehicles

Basic topology:

```text
          ESP-NOW
             |
      ┌──────┴──────┐
      │             │
   ESP32 A       ESP32 B
      │             │
   Vehicle A      Vehicle B
```

Future topology:

```text
                 Vehicle A
                /         \
               /           \
        Vehicle B         Vehicle C
               \           /
                \         /
                 Vehicle D
```

The system should be designed so that moving from 2 vehicles to multiple vehicles does not require changing the fundamental protocol.

---

# 5. Vehicle Data Acquisition

## 5.1 OBD-II

OBD-II can provide useful vehicle information such as:

- Vehicle speed
- Engine RPM
- Throttle position
- Engine load
- Other supported PIDs

Common standard PIDs include:

| PID | Parameter |
|---|---|
| `0C` | Engine RPM |
| `0D` | Vehicle speed |
| `11` | Throttle position |

### Important limitation

Do **not** assume that generic OBD-II provides:

- Brake pedal state
- Brake pressure
- Steering angle
- Individual wheel speeds
- ABS information
- Other manufacturer-specific data

These are often ECU/module-specific.

Therefore the system should combine OBD/CAN data with IMU data.

---

# 6. OBD-II Implementation Options

## Option A — ELM327-style adapter

```text
Vehicle
   |
 OBD-II
   |
ELM327-compatible adapter
   |
 UART/Bluetooth
   |
 ESP32
```

Advantages:

- Easier MVP
- Faster to prototype
- Can expose standard OBD-II PIDs

Use this if the goal is to get the MVP working quickly.

---

## Option B — Direct CAN

For a more advanced implementation:

```text
OBD-II
   |
CAN-H / CAN-L
   |
CAN Transceiver
   |
ESP32 TWAI/CAN
```

An ESP32 can use its CAN/TWAI peripheral with an external CAN transceiver.

Advantages:

- More direct vehicle-network access
- Better technical depth
- Potentially more real-time information
- More control over CAN frames

### Recommendation

Implement the MVP with the easiest reliable OBD-II method first.

Keep direct CAN as the advanced path.

---

# 7. IMU

Add an accelerometer/gyroscope such as:

- MPU6050
- MPU6500
- Similar low-cost IMU

The IMU provides:

### Accelerometer

```text
X acceleration
Y acceleration
Z acceleration
```

### Gyroscope

```text
Angular velocity
Roll-related motion
Pitch-related motion
Yaw rate
```

The most important MVP measurement is **longitudinal acceleration**.

---

# 8. Why the IMU Matters

OBD-II may tell us:

```text
speed = 65 km/h
```

But the IMU can tell us:

```text
acceleration = -4.2 m/s²
```

This helps detect:

- Harsh braking
- Sudden deceleration
- Possible impact
- Vehicle rollover-like motion
- Sudden abnormal motion

Example:

```text
Normal driving:

+0.2
-0.1
+0.3
-0.4 m/s²


Harsh braking:

-0.8
-2.5
-4.5
-5.1 m/s²
```

---

# 9. Optional GPS

GPS is not required for the first MVP, but it significantly improves the architecture.

GPS can provide:

- Latitude
- Longitude
- Speed
- Heading
- Approximate position

This allows the system to estimate:

- Distance between vehicles
- Relative direction
- Whether vehicles are approaching each other
- Location of a reported hazard

Architecture:

```text
GPS
 |
 +--> Position
 +--> Speed
 +--> Heading
 |
 v
ESP32
```

### MVP recommendation

GPS should be treated as an **optional Phase 2/3 feature**, not a blocker for the initial prototype.

---

# 10. Safety Events

Define a small set of standard events.

```text
NORMAL
OVERSPEED
HARSH_BRAKING
SUDDEN_SLOWDOWN
ACCIDENT
HAZARD
EMERGENCY_STOP
COLLISION_WARNING
```

Use numeric event IDs in the actual packet rather than strings.

Example:

```text
0 = NORMAL
1 = OVERSPEED
2 = HARSH_BRAKING
3 = SUDDEN_SLOWDOWN
4 = ACCIDENT
5 = HAZARD
6 = EMERGENCY_STOP
7 = COLLISION_WARNING
```

---

# 11. Vehicle State Packet

Every vehicle should periodically broadcast its current state.

Conceptually:

```json
{
    "vehicle_id": 2,
    "sequence": 1842,
    "timestamp": 18293721,
    "speed": 68,
    "acceleration": -2.7,
    "heading": 183,
    "event": "HARSH_BRAKING",
    "confidence": 92
}
```

However, the actual ESP32 implementation should preferably use a compact binary struct instead of JSON.

---

# 12. Suggested Binary Packet

```text
┌──────────────────┬─────────────┐
│ Field            │ Size        │
├──────────────────┼─────────────┤
│ Vehicle ID       │ 1 byte      │
│ Sequence Number  │ 2 bytes     │
│ Timestamp        │ 4 bytes     │
│ Speed            │ 2 bytes     │
│ Acceleration     │ 2 bytes     │
│ Heading          │ 2 bytes     │
│ Event            │ 1 byte      │
│ Confidence       │ 1 byte      │
└──────────────────┴─────────────┘
```

Advantages:

- Small packets
- Fast transmission
- Low overhead
- Easy to parse
- Suitable for periodic broadcasts

---

# 13. Packet Reliability

Every packet should include:

## Vehicle ID

Identifies the sender.

```text
Vehicle A = 01
Vehicle B = 02
```

## Sequence number

Allows the receiver to detect:

- Duplicate packets
- Out-of-order packets
- Missing packets

Example:

```text
100
101
102
103
```

If:

```text
100
101
103
```

packet `102` may have been lost.

## Timestamp

Allows stale data to be rejected.

Example:

```text
if packet_age > 500 ms:
    discard packet
```

The exact timeout should be experimentally tuned.

---

# 14. Message Priority

Safety messages should have higher priority than normal state updates.

Example:

```text
Priority 0
EMERGENCY

Priority 1
COLLISION_WARNING

Priority 2
HARSH_BRAKING

Priority 3
NORMAL_STATE
```

Normal state:

```text
Periodic transmission
```

Emergency event:

```text
Immediate transmission
+ optional repeated transmission
```

This demonstrates low-latency safety communication.

---

# 15. Edge Intelligence

The most important part of the project is not simply communication.

It is what each vehicle **does with the received data**.

Each vehicle has a local edge engine:

```text
              SENSOR DATA
                   |
                   v
          ┌─────────────────┐
          │ Sensor Fusion   │
          └────────┬────────┘
                   |
                   v
          ┌─────────────────┐
          │ Event Detection │
          └────────┬────────┘
                   |
          ┌────────┴────────┐
          |                 |
          v                 v
      Normal            Hazard
          |                 |
          └────────┬────────┘
                   v
              V2V Packet
                   |
                   v
              ESP-NOW
                   |
                   v
             Other Vehicle
                   |
                   v
             Risk Engine
                   |
                   v
             Driver Alert
```

---

# 16. Start With Rule-Based Edge Intelligence

Do not start with machine learning.

A rule-based engine is:

- Easier to debug
- Easier to explain
- Fast
- Deterministic
- Suitable for ESP32
- Perfectly acceptable for an MVP

ML can be added later.

---

# 17. Overspeed Detection

Simple local rule:

```text
if speed > SPEED_LIMIT:
    event = OVERSPEED
```

Example:

```text
SPEED_LIMIT = 60 km/h

speed = 72 km/h

=> OVERSPEED
```

For the MVP, configure a fixed speed limit.

A future version could obtain speed limits from a map/GPS system.

---

# 18. Harsh Braking Detection

Use longitudinal acceleration.

Example:

```text
if acceleration < -3.0 m/s²:
    event = HARSH_BRAKING
```

The threshold should be experimentally calibrated.

A better implementation can use:

```text
speed > minimum_speed
AND
acceleration < threshold
```

to reduce false positives.

---

# 19. Sudden Slowdown Detection

Use speed over time.

Example:

```text
previous_speed = 70 km/h
current_speed = 45 km/h
time = 1 second
```

The vehicle has experienced a significant speed drop.

Possible rule:

```text
if speed_drop > threshold:
    event = SUDDEN_SLOWDOWN
```

Combine this with IMU acceleration for better confidence.

---

# 20. Accident Detection

A basic accident detector can combine multiple signals.

Possible conditions:

```text
high speed before event

AND

large negative acceleration

AND/OR

large angular velocity

AND/OR

vehicle becomes stationary
```

Example:

```text
Before:

speed = 55 km/h
acceleration = 0.2 m/s²

        ↓

Impact

        ↓

acceleration = -7.8 m/s²
gyro spike detected

        ↓

speed = 0 km/h
```

Then:

```text
event = ACCIDENT
```

The vehicle immediately broadcasts the accident event.

---

# 21. Collision Risk

Collision detection becomes much more meaningful if the system knows relative distance.

Possible sources:

### Option 1 — GPS

Use:

```text
Vehicle A position
Vehicle B position
```

to estimate distance.

### Option 2 — UWB

Use UWB for accurate ranging.

### Option 3 — Ultrasonic

Useful for a tabletop/scale demo.

However, ultrasonic should not be presented as an actual automotive V2V ranging solution.

---

# 22. Time To Collision (TTC)

If relative distance and closing speed are available:

```text
TTC = distance / closing_speed
```

Example:

```text
Distance = 20 m

Vehicle A = 30 km/h
Vehicle B = 50 km/h

Closing speed = 20 km/h
              ≈ 5.56 m/s

TTC = 20 / 5.56
    ≈ 3.6 seconds
```

Possible risk levels:

```text
TTC > 5 seconds
NORMAL

3–5 seconds
CAUTION

1.5–3 seconds
WARNING

< 1.5 seconds
CRITICAL
```

These values are prototype thresholds and must not be treated as automotive safety-certified thresholds.

---

# 23. Important V2V Design Principle

Do not transmit only:

```text
"I am braking."
```

Instead transmit the vehicle's state:

```text
speed
acceleration
heading
timestamp
event
```

Then Vehicle B independently decides:

```text
Vehicle A:
speed = 30 km/h
acceleration = -4.2 m/s²
event = HARSH_BRAKING

Vehicle B:
speed = 65 km/h

=> high risk
=> warning
```

This is what makes the project an **edge-intelligence V2V system** rather than a simple remote-alert system.

---

# 24. OLED Interface

Use a small OLED such as a 0.96-inch display.

Normal state:

```text
┌──────────────────┐
│    V2V ACTIVE    │
│                  │
│ Nearby: 1        │
│ Speed: 62 km/h   │
│                  │
│ STATUS: NORMAL   │
└──────────────────┘
```

Warning:

```text
┌──────────────────┐
│    !! ALERT !!   │
│                  │
│ VEHICLE BRAKING  │
│                  │
│ TTC: 2.1 sec     │
│ REDUCE SPEED     │
└──────────────────┘
```

Critical:

```text
┌──────────────────┐
│   !!! DANGER !!! │
│                  │
│ COLLISION RISK   │
│                  │
│ TTC: 0.9 sec     │
│ SLOW DOWN!       │
└──────────────────┘
```

Keep the UI simple.

The OLED should communicate the event immediately rather than trying to reproduce a complete dashboard.

---

# 25. Audible Warning

Add a buzzer.

Suggested behavior:

```text
NORMAL
No buzzer

CAUTION
Slow periodic beep

WARNING
Fast beep

CRITICAL
Continuous or rapid beep
```

Combine the buzzer with the OLED so the driver can notice the warning without continuously looking at the display.

---

# 26. Cooperative Hazard Propagation

This can become one of the strongest features of the project.

Example:

```text
Vehicle A
ACCIDENT
   |
   v
Vehicle B receives event
   |
   v
Vehicle B broadcasts
ACCIDENT_AHEAD
   |
   v
Vehicle C receives warning
```

Conceptually:

```text
A 🚨
↓
B ⚠
↓
C ⚠
↓
D ⚠
```

No cloud.

No central server.

The hazard propagates through the decentralized V2V network.

This demonstrates a meaningful cooperative-driving concept.

---

# 27. Neighbor Table

Each ESP32 can maintain a table of nearby vehicles.

Example:

```text
┌─────┬────────┬────────┬──────────┐
│ ID  │ Speed  │ Accel  │ Age      │
├─────┼────────┼────────┼──────────┤
│ A   │ 65     │ -0.3   │ 30 ms    │
│ B   │ 42     │ -3.4   │ 20 ms    │
│ C   │ 71     │ +0.2   │ 50 ms    │
└─────┴────────┴────────┴──────────┘
```

The table allows each vehicle to reason about its local environment.

For the first MVP, the table only needs to support 1 neighbor.

---

# 28. Recommended Hardware

For each vehicle:

| Component | Purpose |
|---|---|
| ESP32 | Main edge node |
| OBD-II/CAN interface | Vehicle data |
| MPU6050/MPU6500 | Acceleration + gyroscope |
| 0.96" OLED | Driver warning |
| Buzzer | Audible alert |
| LED | Visual warning |
| 12V → 5V/3.3V converter | Vehicle power |
| Optional GPS | Position/heading |
| Optional UWB | Accurate ranging |

---

# 29. MVP Hardware Architecture

```text
                  VEHICLE
                     |
             ┌───────┴────────┐
             │                │
          OBD-II             IMU
             │                │
             └───────┬────────┘
                     │
                     v
                  ESP32
                     |
           ┌─────────┴─────────┐
           │                   │
         OLED                Buzzer
           │
           |
       ESP-NOW V2V
           |
           v
      Other ESP32
```

---

# 30. Software Architecture

Recommended firmware structure:

```text
firmware/
│
├── main/
│   ├── main.cpp
│   ├── config.h
│   │
│   ├── sensors/
│   │   ├── imu.cpp
│   │   ├── imu.h
│   │   ├── obd.cpp
│   │   └── obd.h
│   │
│   ├── v2v/
│   │   ├── protocol.cpp
│   │   ├── protocol.h
│   │   ├── espnow.cpp
│   │   └── espnow.h
│   │
│   ├── edge/
│   │   ├── detector.cpp
│   │   ├── detector.h
│   │   ├── collision.cpp
│   │   └── collision.h
│   │
│   ├── display/
│   │   ├── oled.cpp
│   │   └── oled.h
│   │
│   └── alerts/
│       ├── buzzer.cpp
│       └── buzzer.h
│
└── README.md
```

---

# 31. Core Firmware Modules

## Sensor Manager

Responsible for:

```text
read OBD
read IMU
read GPS
filter sensor values
```

---

## Event Detector

Responsible for:

```text
overspeed
harsh braking
sudden slowdown
accident
```

---

## V2V Protocol

Responsible for:

```text
packet creation
packet validation
sequence numbers
timestamps
priority
transmission
reception
```

---

## Risk Engine

Responsible for:

```text
neighbor state
relative speed
distance
TTC
risk classification
```

---

## Display Manager

Responsible for:

```text
normal display
warning display
critical display
```

---

## Alert Manager

Responsible for:

```text
buzzer
LED
alert priority
```

---

# 32. MVP Development Phases

## Phase 1 — ESP32 Communication

Goal:

```text
ESP32 A ↔ ESP32 B
```

Implement:

- ESP-NOW initialization
- Device discovery
- Broadcast
- Receive callback
- Basic packet structure

Test:

```text
A sends "HELLO"
B receives "HELLO"
```

---

## Phase 2 — OLED + Buzzer

Add:

- OLED
- Buzzer
- LED

Test:

```text
NORMAL
WARNING
CRITICAL
```

---

## Phase 3 — IMU

Add:

- MPU6050/MPU6500
- Accelerometer reading
- Gyroscope reading
- Filtering

Implement:

```text
acceleration
angular velocity
```

---

## Phase 4 — Local Event Detection

Implement:

### Overspeed

```text
speed > limit
```

### Harsh braking

```text
acceleration < threshold
```

### Sudden slowdown

```text
large speed drop
```

### Accident

```text
impact-like acceleration
+
abnormal motion
+
stationary state
```

---

## Phase 5 — OBD-II

Integrate:

```text
OBD-II
   ↓
ESP32
```

Start with:

```text
vehicle speed
RPM
throttle
```

Do not block the project on advanced manufacturer-specific CAN data.

---

## Phase 6 — V2V Vehicle State

Broadcast:

```text
vehicle ID
timestamp
sequence number
speed
acceleration
event
```

Vehicle B maintains a neighbor state.

---

## Phase 7 — Remote Hazard Detection

Example:

```text
Vehicle A
HARSH_BRAKING
     |
     | ESP-NOW
     v
Vehicle B
     |
     v
Risk Engine
     |
     v
OLED + Buzzer
```

---

## Phase 8 — Collision Risk

Add:

```text
relative speed
distance
TTC
```

Then:

```text
NORMAL
CAUTION
WARNING
CRITICAL
```

---

## Phase 9 — Accident Propagation

Implement:

```text
A detects accident
        ↓
A broadcasts accident
        ↓
B receives
        ↓
B broadcasts hazard
        ↓
C receives
```

---

## Phase 10 — Performance Testing

Measure:

- Communication latency
- Packet loss
- Detection latency
- Warning latency
- Update frequency
- Range
- False positives

---

# 33. End-to-End Demo Scenario

The main makeathon demo should be something like this.

## Initial State

Vehicle A:

```text
Speed = 70 km/h
```

Vehicle B:

```text
Speed = 65 km/h
```

Both display:

```text
V2V ACTIVE
STATUS: NORMAL
```

---

## Event

Vehicle A suddenly brakes.

```text
70 km/h
   ↓
60 km/h
   ↓
45 km/h
   ↓
30 km/h
```

IMU detects:

```text
large negative acceleration
```

A's edge engine:

```text
event = HARSH_BRAKING
```

---

## V2V Transmission

Vehicle A immediately sends:

```text
ID = A
speed = 30
acceleration = -4.2
event = HARSH_BRAKING
timestamp = ...
```

---

## Vehicle B Processing

Vehicle B receives the packet.

It combines:

```text
My speed = 65 km/h
Other speed = 30 km/h
Other acceleration = -4.2 m/s²
Event = HARSH_BRAKING
```

Then determines:

```text
risk = HIGH
```

---

## Driver Alert

OLED:

```text
!! ALERT !!

VEHICLE BRAKING

REDUCE SPEED
```

Buzzer:

```text
BEEP BEEP BEEP
```

---

# 34. Second Demo — Accident Propagation

Vehicle A experiences an impact.

IMU:

```text
large acceleration spike
large gyro spike
vehicle stops
```

Local edge engine:

```text
ACCIDENT
```

A immediately broadcasts:

```text
EVENT = ACCIDENT
```

Vehicle B:

```text
⚠ ACCIDENT AHEAD
```

Vehicle B then propagates:

```text
ACCIDENT_AHEAD
```

Vehicle C receives:

```text
⚠ HAZARD AHEAD
```

This demonstrates decentralized hazard propagation.

---

# 35. Performance Metrics

The project should not only demonstrate functionality.

Measure the system.

## Communication latency

```text
Event detected
       ↓
Packet transmitted
       ↓
Packet received
       ↓
OLED updated
```

Measure:

```text
T_total
```

---

## Suggested measurements

### Sensor detection latency

```text
physical event
      ↓
event classification
```

### V2V latency

```text
packet sent
      ↓
packet received
```

### Alert latency

```text
event occurs
      ↓
driver warning
```

### Packet loss

```text
Packets transmitted = 1000
Packets received = 970

Packet loss = 3%
```

---

# 36. Important Safety Boundary

This project should be treated as a **prototype/research demonstrator**, not as a system capable of controlling a real vehicle.

The MVP should:

- Observe vehicle state
- Detect events
- Communicate warnings
- Alert the driver

It should **not** automatically:

- Apply brakes
- Steer the vehicle
- Override driver controls
- Modify critical vehicle ECU behavior

---

# 37. Future Improvements

After the MVP works, possible extensions include:

## Machine Learning

Replace or supplement rules with:

```text
IMU
OBD
vehicle state
      ↓
ML model
      ↓
event classification
```

Possible models:

- Random Forest
- XGBoost
- TinyML model
- Small neural network

---

## More Vehicles

Move from:

```text
2 vehicles
```

to:

```text
5–10 nodes
```

and evaluate network behavior.

---

## GPS-Based Hazard Location

Broadcast:

```text
latitude
longitude
heading
```

Then hazards can be associated with road locations.

---

## UWB Ranging

Add accurate vehicle-to-vehicle distance.

This greatly improves TTC calculation.

---

## Adaptive Risk

Instead of fixed rules:

```text
TTC < 3 sec => warning
```

consider:

```text
speed
relative speed
acceleration
road condition
vehicle state
confidence
```

to calculate a continuous risk score.

---

## Cooperative Driving

Vehicles could eventually share:

```text
speed
acceleration
intent
lane/heading
hazards
traffic conditions
```

allowing:

- Cooperative braking
- Platooning
- Cooperative merging
- Traffic optimization
- Emergency vehicle awareness

---

# 38. Future System Architecture

```text
                 V2V NETWORK
                      |
       ┌──────────────┼──────────────┐
       |              |              |
       v              v              v
   Vehicle A      Vehicle B      Vehicle C
       |              |              |
       v              v              v
   Edge Node       Edge Node       Edge Node
       |              |              |
       └──────────────┼──────────────┘
                      |
                 Hazard Sharing
                      |
                 Cooperative
                 Intelligence
```

---

# 39. Final MVP Definition

The MVP is considered complete when the following works reliably:

- [ ] Two ESP32 nodes communicate directly using ESP-NOW.
- [ ] No Wi-Fi router or cloud server is required.
- [ ] Each ESP32 has a unique vehicle ID.
- [ ] Vehicle state packets are transmitted periodically.
- [ ] Packets include sequence numbers and timestamps.
- [ ] OLED displays system status.
- [ ] Buzzer provides warning alerts.
- [ ] IMU detects significant deceleration.
- [ ] OBD-II provides at least vehicle speed where supported.
- [ ] A vehicle can detect harsh braking locally.
- [ ] A vehicle can broadcast a harsh-braking event.
- [ ] A neighboring vehicle can receive the event.
- [ ] The neighboring vehicle independently calculates risk.
- [ ] The neighboring vehicle displays a warning.
- [ ] Accident-like events can be detected using IMU data.
- [ ] Accident/hazard events can be propagated to another node.
- [ ] End-to-end communication/alert latency is measured.

---

# 40. Recommended Final MVP Scope

Do **not** try to implement everything at once.

The minimum successful version should be:

```text
                 VEHICLE A
                    │
            ┌───────┴────────┐
            │                │
          OBD-II            IMU
            │                │
            └───────┬────────┘
                    │
                  ESP32
                    │
             Edge Detection
                    │
             HARSH BRAKING
                    │
                    ▼
                ESP-NOW
                    │
                    ▼
                  ESP32
                    │
             Risk Calculation
                    │
                    ▼
             OLED + BUZZER
                    │
                    ▼
              DRIVER WARNING
```

Then add:

```text
        + GPS
        + TTC
        + Accident detection
        + Hazard propagation
        + Multiple vehicles
```

---

# 41. Project Pitch

A concise way to present the MVP:

> **We are building a decentralized V2V safety platform where every vehicle acts as an edge-computing node. Vehicles continuously share their motion state and safety events over a direct low-latency wireless link. Each receiving vehicle independently evaluates the information with local edge intelligence to detect hazards such as harsh braking, sudden slowdowns, overspeeding, and potential collisions. The system provides immediate driver alerts through an OLED and buzzer without requiring cloud connectivity or a central server.**

---

# 42. Core Value Proposition

The project demonstrates:

```text
                 NO CLOUD
                    │
                    ▼
              DIRECT V2V
                    │
                    ▼
             REAL-TIME DATA
                    │
                    ▼
             EDGE INTELLIGENCE
                    │
                    ▼
              LOCAL DECISION
                    │
                    ▼
             DRIVER WARNING
```

The most important message for the makeathon is:

> **Every vehicle can sense, communicate, reason, and warn independently.**
