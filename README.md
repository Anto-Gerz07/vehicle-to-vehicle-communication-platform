# Decentralized EV Vehicle-to-Vehicle (V2V) Communication Platform

## Overview
A decentralized communication system designed to enable vehicles to exchange real-time safety and traffic information without relying on cloud connectivity. By leveraging edge computing on ESP32 microcontrollers and the ESP-NOW protocol, vehicles can achieve low-latency communication to avoid collisions, share road hazards, and support cooperative driving.

## Features
- **Cloudless Edge Intelligence**: Localized detection of dangerous events (harsh braking, overspeed, sudden slowdowns, accidents) using an integrated rule engine.
- **Sensor Fusion**: Combines OBD-II/CAN vehicle telemetry (speed, RPM, throttle) with IMU motion data (acceleration, gyroscope) for high-confidence event detection.
- **V2V Safety Protocol**: Custom lightweight binary broadcasting via ESP-NOW for minimal latency.
- **Risk & ML Engines**: Built-in Risk Engine calculates Time-To-Collision (TTC), while an ML Engine uses sliding window temporal features to detect anomalies and reduce false positives.
- **Hardware-in-the-loop (HIL) Simulator**: Professional-grade Tkinter and Web-based simulator for prototyping and analyzing vehicle behaviors and V2V network interactions.

## Project Structure
- `v2v_simulator/` - Core Python modules including the ML Engine, Risk Engine, Rule Engine, and network emulators.
- `interactive_sim.py` - A robust, interactive desktop GUI simulator for testing and visualizing V2V interactions, physics, and ML predictions.
- `run_esp32.py` - Hardware-in-the-loop script bridging the software simulator and physical ESP32 modules via serial.
- `v2v-web-simulator/` - A modern web-based monitoring dashboard for telemetry and safety logs.
- `esp32_firmware/` - Arduino `.ino` sketches for flashing the physical ESP32 V2V transceiver nodes.

## Usage

### 1. Interactive Desktop Simulator
Run the local Tkinter simulator to test physics, ML anomaly detection, and vehicle interactions:
```bash
python interactive_sim.py
```

### 2. Web Simulator Dashboard
Start the React-based frontend dashboard for viewing logs and simulated environments:
```bash
cd v2v-web-simulator
npm install
npm run dev
```

### 3. Hardware Implementation
Flash the firmware located in `esp32_firmware/` to your ESP32 microcontrollers. You can use the serial bridge to test real hardware with the python environment:
```bash
python run_esp32.py /dev/ttyUSB0
```

## Architecture Summary
Vehicles act as independent edge nodes. They gather local sensing data (OBD/IMU), process event detection locally, and transmit standardized state packets directly to nearby vehicles. Receiving nodes calculate TTC risk and trigger driver alerts (OLED/Buzzer) instantly—eliminating the round-trip latency of traditional cloud-based telemetry systems.
