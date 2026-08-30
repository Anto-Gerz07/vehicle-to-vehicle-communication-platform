# Decentralized EV Vehicle-to-Vehicle (V2V) Communication Platform

## What We Did
We built a decentralized communication system that enables vehicles to exchange real-time safety and traffic information without relying on cloud connectivity. By leveraging edge computing on ESP32 microcontrollers, vehicles achieve low-latency communication to avoid collisions, share road hazards, and support cooperative driving. 

We developed a complete ecosystem including:
- **Cloudless Edge Intelligence**: Localized detection of dangerous events (harsh braking, overspeed, sudden slowdowns, accidents, potholes) using an integrated rule engine.
- **Sensor Fusion Engine**: Combines OBD-II/CAN vehicle telemetry (speed, RPM, throttle) with IMU motion data (acceleration, gyroscope) for high-confidence event detection.
- **Dual-Protocol V2V**: Custom lightweight binary broadcasting via ESP-NOW for low-latency P2P mesh networking, combined with a LoRa SX1278 transceiver bridge for long-range communication.
- **Advanced Predictive Engines**: A Risk Engine calculates Time-To-Collision (TTC), while an ML Engine uses sliding window temporal features to detect anomalies and reduce false positives.
- **Simulation and Visualization**: A professional-grade Tkinter hardware-in-the-loop (HIL) simulator for testing, alongside a Python/Leaflet.js based dashboard to plot vehicles and visualize hazard warnings in real-time.

## Technology Stack
- **Hardware**: ESP32 Microcontrollers, MPU6500 IMU, NEO-6M GPS, SX1278 LoRa Transceivers, SSD1306 OLED Displays.
- **Embedded Software**: C/C++ using Arduino framework, ESP-NOW protocol, SPI/I2C communication protocols.
- **Simulation and Logic**: Python 3.8+, Tkinter for desktop GUI, Scikit-learn (ML Engine), Pandas.
- **Mapping Server**: Python (aiohttp) backend, WebSocket for real-time data streaming, HTML5/CSS3/JavaScript frontend with Leaflet.js and OpenStreetMap (Nominatim).
- **Computer Vision (Road Safety Pipeline)**: OpenCV for lane detection, YOLOv8-nano for pothole detection.

## How to Replicate It

### 1. Software Environment Setup
1. **Clone the repository**:
   ```bash
   git clone https://github.com/Anto-Gerz07/vehicle-to-vehicle-communication-platform.git
   cd vehicle-to-vehicle-communication-platform
   ```
2. **Install Python dependencies**:
   Ensure you have Python 3.8+ installed. It is recommended to use a virtual environment.
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   pip install aiohttp
   ```

### 2. Hardware Implementation (ESP32 Nodes)
To replicate the physical V2V mesh network:
1. Wire an ESP32 to a 0.96-inch SSD1306 OLED display (I2C), an MPU6500 IMU (I2C), and a NEO-6M GPS module (UART2).
2. For long-range fallback, connect an SX1278 LoRa module via SPI.
3. Flash the main firmware located in `esp32_firmware/esp32_firmware.ino` to each vehicle node. For LoRa nodes, use the sketches in `esp32_firmware/Lora_sender` or `Lora_receiver`.
4. Ensure each ESP32 has a unique `myState.vehicle_id` (e.g., 'A', 'B') in the firmware setup before flashing.
5. You can bridge the node to a PC using the serial bridge script:
   ```bash
   python run_esp32.py /dev/ttyUSB0
   ```

### 3. Running the Simulators and Dashboards

**Interactive Desktop Simulator (HIL)**
Run the local Tkinter simulator to test physics, ML anomaly detection, and vehicle interactions:
```bash
python interactive_sim.py
```

**Live GPS Map Tracker**
Start the real-time hazard mapping server:
```bash
cd map/test
python3 server.py
```
Open a browser and navigate to `http://localhost:8080/` to view the live dashboard and hazards (potholes, crashes). The ESP32 nodes and simulator will post JSON data to the `/gps` endpoint.
