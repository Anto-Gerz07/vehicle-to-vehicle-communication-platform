# 🚗 V2V Dynamic Navigation & Real-time Road Hazard Map

A real-time Vehicle-to-Vehicle (V2V) mapping and road safety telemetry platform designed for Linux Mint and embedded ESP32 nodes.

---

## 🌟 Key Features

1. **🛰️ Real-time GPS Vehicle Tracking**:
   - Live location coordinates streamed from ESP32 with **NEO-6M GPS** via USB Serial or WiFi HTTP POST.
   - Smoothly animated **directional arrow icon** that rotates with vehicle heading (`0-360°`).
   - Breadcrumb historical route trail and telemetry HUD (Speed in km/h, Compass bearing, GPS satellites lock status).

2. **🚨 Road Hazard Reporting**:
   - Quick one-touch reporting for:
     - 🕳️ **Potholes & Crates**
     - ⚠️ **Dangerous Speed Bumps**
     - 🚧 **Roadblocks & Construction**
     - 🚗💨 **Traffic Gridlock**
     - 📍 **Custom Road Hazards**

3. **⌨️ Digital On-Screen Touchscreen Keyboard**:
   - Integrated full-featured virtual QWERTY keyboard with numbers, symbols, shift/caps, backspace, and clear buttons.
   - Tailored for touchscreen in-car dashboards and tablets as well as physical keyboard input.

4. **🎯 Proximity Hazard Detection & Acoustic Chimes**:
   - Computes distance to all active road hazards in real time (Haversine formula).
   - Audio alert chime and HUD warning flash when approaching within **45 meters** of any hazard.

5. **👥 3-Vote Community Verification Consensus**:
   - When within proximity of a hazard, an interactive verification dialog automatically pops up:
     > *"Is this hazard still present on the road?"*
     > - **"👍 Yes, Still Here"** (increases confirmation score)
     > - **"❌ No, Resolved / Cleared"** (registers a dismissal vote)
   - **3 "No" Votes Threshold**: When 3 or more unique users vote "No", the hazard is automatically marked as resolved and disappears from all connected maps in real time!

6. **🧪 Built-in Virtual Drive Simulator**:
   - Allows testing proximity alerts, hazard popups, and the 3-vote disappearance system indoors without requiring outdoor driving or satellite locks.

---

## 🚀 How to Run the Server

### 1. Requirements
Ensure `aiohttp` is installed:
```bash
pip3 install aiohttp
```
*(Optional: For direct USB Serial reading from ESP32, `pip3 install pyserial`)*

### 2. Start the Server on Linux Mint
```bash
cd /home/anto/Desktop/V2V/map/test
python3 server.py
```

### 3. Open the Dashboard
Open your web browser on your laptop, tablet, or phone (connected to the same WiFi network):
```
http://localhost:8080/
```
*(Or `http://<your-linux-mint-lan-ip>:8080/` from mobile/other screens)*

---

## 📡 Hardware ESP32 Connections (from `connections.md`)

| Component | ESP32-S Pin | Purpose |
| :--- | :--- | :--- |
| **GPS NEO-6M RX** | **GPIO 16 (RX2)** | Receives NMEA stream from GPS TX |
| **GPS NEO-6M TX** | **GPIO 17 (TX2)** | Transmits to GPS RX |
| **GPS VCC** | **5V / VIN** | Stable 5V power supply |
| **GPS GND** | **GND** | Common ground |

---

## 🔌 API & Ingest Endpoints

- **`GET /`**: Live web map dashboard.
- **`GET /ws`**: Bidirectional WebSocket stream for telemetry, hazard reporting, and consensus voting.
- **`POST /gps`**: Ingest GPS or IMU events from ESP32 or external scripts:
  ```json
  {
    "lat": 12.8406,
    "lng": 80.1534,
    "speed": 45.2,
    "heading": 180.0,
    "sats": 9
  }
  ```
- **`GET /events`**: Returns list of all active road hazards.
- **`POST /events`**: REST API to submit a new hazard event.

