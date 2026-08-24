# Decentralized EV Vehicle-to-Vehicle (V2V) Communication Platform

## Overview
A decentralized communication system designed to enable vehicles to exchange real-time safety and traffic information without relying on cloud connectivity. By leveraging edge computing on ESP32 microcontrollers and the ESP-NOW protocol, vehicles can achieve low-latency communication to avoid collisions, share road hazards, and support cooperative driving. The project also features a long-range LoRa fallback for extended coverage and a centralized Mapping Server for fleet-level hazard visualization.

## Features
- **Cloudless Edge Intelligence**: Localized detection of dangerous events (harsh braking, overspeed, sudden slowdowns, accidents, potholes) using an integrated rule engine.
- **Sensor Fusion**: Combines OBD-II/CAN vehicle telemetry (speed, RPM, throttle) with IMU motion data (acceleration, gyroscope) for high-confidence event detection.
- **Dual-Protocol V2V**: Custom lightweight binary broadcasting via ESP-NOW for low-latency P2P mesh networking, combined with a LoRa SX1278 transceiver bridge for long-range communication.
- **Risk & ML Engines**: Built-in Risk Engine calculates Time-To-Collision (TTC), while an ML Engine uses sliding window temporal features to detect anomalies and reduce false positives.
- **Hardware-in-the-loop (HIL) Simulator**: Professional-grade Tkinter simulator for prototyping and analyzing vehicle behaviors and V2V network interactions.
- **Real-Time Live Map Tracker**: Python/Leaflet.js based dashboard to plot vehicles and visualize hazard warnings (potholes, crashes) via HTTP POST telemetry.

## Project Structure
- `v2v_simulator/` - Core Python modules including the ML Engine, Risk Engine, Rule Engine, and network emulators.
- `interactive_sim.py` - A robust, interactive desktop GUI simulator for testing and visualizing V2V interactions, physics, and ML predictions.
- `run_esp32.py` - Hardware-in-the-loop script bridging the software simulator and physical ESP32 modules via serial.
- `esp32_firmware/` - Arduino `.ino` sketches for flashing the physical ESP32 V2V transceiver nodes. Contains primary ESP-NOW firmware and LoRa bridging firmware.
- `map/test/` - Python GPS relay server and Live GPS Tracker HTML client using OpenStreetMap.
- `v2v-web-simulator/` - A modern web-based monitoring dashboard for telemetry and safety logs.

## Setup and Replication Instructions

### 1. Software Environment Setup
1. **Clone the repository**:
   ```bash
   git clone https://github.com/shaik-hasan-AS/V2V.git
   cd V2V
   ```
2. **Install Python dependencies**:
   Ensure you have Python 3.8+ installed. It is recommended to use a virtual environment.
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   pip install aiohttp  # For map server
   ```

### 2. Hardware Implementation (ESP32 Nodes)
To replicate the physical V2V mesh network:
1. Wire an ESP32 to a 0.96" SSD1306 OLED display (I2C), an MPU6500 IMU (I2C), and a NEO-6M GPS module (UART2).
2. For long-range fallback, connect an SX1278 LoRa module via SPI.
3. Flash the main firmware located in `esp32_firmware/esp32_firmware.ino` to each vehicle node. For LoRa nodes, use the sketches in `esp32_firmware/Lora_sender` or `Lora_receiver`.
4. Ensure each ESP32 has a unique `myState.vehicle_id` (e.g., 'A', 'B') in the firmware setup before flashing.
5. You can bridge the node to a PC using:
   ```bash
   python run_esp32.py /dev/ttyUSB0
   ```

### 3. Running the Simulators & Dashboards

**A. Interactive Desktop Simulator (HIL)**
Run the local Tkinter simulator to test physics, ML anomaly detection, and vehicle interactions:
```bash
python interactive_sim.py
```

**B. Live GPS Map Tracker**
Start the real-time hazard mapping server:
```bash
cd map/test
python3 server.py
```
Open a browser and navigate to `http://localhost:8080/` to view the live dashboard and hazards (potholes, crashes). The ESP32 nodes / Simulator will post JSON data to the `/gps` endpoint.

**C. Web Simulator Dashboard (Optional)**
Start the React-based frontend dashboard for viewing historical logs:
```bash
cd v2v-web-simulator
npm install
npm run dev
```

## Architecture Summary
Vehicles act as independent edge nodes gathering local sensing data (OBD/IMU/GPS). They process event detection locally and transmit standardized state packets directly to nearby vehicles via ESP-NOW. Receiving nodes calculate TTC risk and trigger driver alerts instantly (OLED/Buzzer). Simultaneously, critical hazard data (like potholes) is forwarded over LoRa/HTTP to a centralized map server for fleet-level visualization, ensuring robust, low-latency, and redundant safety communication.
