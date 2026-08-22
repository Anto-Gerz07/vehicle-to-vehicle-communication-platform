# OBD2/CAN Bus Simulation Guide

## Overview

OBD2 (On-Board Diagnostics, standardized under SAE J1979) runs over the CAN bus (ISO 15765, typically 500 kbps for most cars post-2008) and exposes data via **PIDs (Parameter IDs)** under different "Modes." Mode 01 (live data) is what you'll use for simulation.

---

## Standard Mode 01 PIDs (Live Data)

| Parameter | PID (hex) | Formula | Range |
|---|---|---|---|
| Engine RPM | 0x0C | ((A×²⁵⁶)+B)/4 | 0–16,383.75 rpm |
| Vehicle speed | 0x0D | A | 0–255 km/h |
| Coolant temperature | 0x05 | A−40 | −40 to 215 °C |
| Engine load | 0x04 | A/2.55 | 0–100% |
| Intake air temp | 0x0F | A−40 | −40 to 215 °C |
| MAF air flow rate | 0x10 | ((A×²⁵⁶)+B)/100 | 0–655.35 g/s |
| Throttle position | 0x11 | A/2.55 | 0–100% |
| Fuel level | 0x2F | A/2.55 | 0–100% |
| Intake manifold pressure | 0x0B | A | 0–255 kPa |
| Ambient air temp | 0x46 | A−40 | −40 to 215 °C |
| Fuel type | 0x51 | A | 0–100% |
| DTCs | Mode 03 | — | — |
| VIN | Mode 09 | — | — |

**Notes:**
- A, B are the high and low bytes of the response data.
- Mode 01 contains ~200 standardized PIDs, but most vehicles only implement 40–80 of them.
- Mode 03: stored diagnostic trouble codes (DTCs).
- Mode 09: vehicle information (VIN, calibration ID).
- Mode 0A: permanent DTCs.
- Mode 22: manufacturer-specific extended PIDs (e.g., battery temp, SOC for EVs).

---

## Accuracy Considerations

Accuracy depends on **where the data comes from, not the protocol itself**:

- **Real car via ELM327/CAN adapter**: The values you read are exactly what the ECU reports — same precision the dashboard and factory scan tools use. RPM and speed are essentially exact (sensor-limited, typically <1% error); temperature and MAF readings have the sensor's own tolerance (usually ±1–3 °C, ±2% flow). The bottleneck isn't OBD2, it's your adapter's polling rate — cheap Bluetooth ELM327 clones often lag at 2–10 Hz, too slow for fast-changing signals like RPM during rapid acceleration.
- **Simulated ECU (Arduino/ESP32 emulator)**: Accuracy is only as good as your synthetic data model. Basic simulators just send `random()` values, which is fine for testing your OBD2 reader's parsing logic but tells you nothing about real vehicle behavior. Better simulators (like ECUSim or ELM327-emulator) let you script realistic PID sequences or replay logged CAN traffic, which is far more useful for demo/testing purposes.

---

## Recommended Car Models for Maximum PID Coverage

For **maximum PID coverage with highest accuracy**, go with a **2008+ Ford** or a **GM (Chevrolet/Buick) CAN-based vehicle** — these two manufacturers expose the broadest set of enhanced, manufacturer-specific PIDs beyond the standard OBD2 set, going well past emissions data into body, chassis, and comfort systems.

### Manufacturer Comparison for PID Depth

| Manufacturer | Standard PIDs | Enhanced/Manufacturer PIDs | Notes |
|---|---|---|---|
| Ford | 20–40 (emissions-focused) | 200–300 via enhanced Ford interface (ABS, airbag, BCM, ICM) | Widest enhanced coverage; needs FORScan |
| GM (Chevy/Buick/GMC) | 40–80 | Broad OEM module support (engine, transmission, chassis) | Well documented by OBDLink's enhanced diagnostics |
| Toyota/Lexus | 40–60 | Moderate, needs Techstream/OBD Fusion | Reliable standard PIDs, decent enhanced access |
| Hyundai/Kia | 40–60 | Good enhanced support via Carista/Infocar | CAN mandatory 2012+, common in India, good for hobbyist work |
| BMW | 40–60 | Strong via BimmerLink/Carista (2008+) | Excellent documentation in hobbyist community |
| VW/Audi/Skoda | 40–60 | Strong via Carista/VCDS | Well-reverse-engineered PIDs, huge hobbyist community |

### Protocol Generation

- **Pre-2008 vehicles** may use J1850 or ISO 9141/14230, not CAN at all — skip these entirely since your goal is CAN bus specifically.
- **2008 onward** is when CAN (ISO 15765, 500 kbps, 11-bit ID) became mandatory across all OBD2-compliant vehicles sold in the US, and most global markets shortly after. This is your hard cutoff for authentic CAN bus work.
- Even among CAN vehicles, **most only implement 40–80 of the ~200 standardized Mode 01 PIDs** — no car exposes everything, since PIDs are tied to the sensors and subsystems actually installed.

---

## How to Build the Simulation

### Path 1 — Simulate the ECU side (no real car needed)

Use an ESP32 or Arduino Uno + MCP2515 CAN controller module. Flash it with an open-source emulator like `coniferconifer/ESP32-ECU-emulator` or `sugiuraii/ECUSim`, which respond to standard Mode 01 PID requests over CAN at 500 kbps. Then connect a second CAN node (another Arduino, or a genuine ELM327 dongle) to query it and log responses. This lets you test your entire OBD2 reading pipeline on a breadboard.

### Path 2 — Software-only simulation (fastest for you)

Use `Ircama/ELM327-emulator` (Python) — it emulates a full ELM327 device over a virtual serial/TCP port, so you can point standard OBD2 libraries (e.g., Python's `python-OBD`) at it without any hardware. This is ideal for quickly testing PID parsing logic, dashboard UIs, or data-logging code before touching real CAN hardware.

### Path 3 — Real car data (highest accuracy)

Buy a genuine ELM327 (USB/Bluetooth) adapter (~₹500–1500), plug into your car's OBD2 port (mandatory in India on all post-2020 BS6 vehicles), and use `python-OBD` or `SavvyCAN` to log real PIDs. For raw CAN frames instead of decoded PIDs, use an MCP2515-based CAN shield directly to sniff the bus (useful for reverse-engineering manufacturer-specific PIDs beyond standard Mode 01).

---

## Suggested Minimal Setup

For your background, the fastest working prototype: ESP32 + MCP2515 shield running `ECUSim` firmware (feeds fake RPM/speed/temp over CAN) → a second ESP32 or genuine ELM327 as the "scan tool" reading PIDs → log to serial/CSV → visualize in Python/MATLAB. This mirrors real automotive diagnostic tool architecture and gives you full control over signal timing to test edge cases (like your DSP background would appreciate — sampling rate vs PID response latency is directly analogous to sampling theorem tradeoffs).

---

## Practical Recommendation for Your Simulation

Since you're **simulating** the ECU (not connecting to a real car first), the actual physical car matters less than which **PID set you choose to emulate** in your ESP32/Arduino firmware. Here's the optimal strategy:

1. **Emulate standard Mode 01 PIDs first** (RPM, speed, coolant temp, throttle, MAF, fuel level) — these are universal across every CAN-based OBD2 vehicle regardless of brand, so your simulator stays broadly "compatible" and testable against any real scan tool.
2. **Layer in Ford or GM enhanced PIDs second** if you want to demonstrate depth — their enhanced PID documentation is the most publicly available and well-documented for reverse engineering, unlike proprietary-locked brands like Tesla.
3. **Avoid EV/hybrid-only platforms** (Tesla, etc.) for a first project — battery SOC, motor controller data, and regen braking parameters use heavily locked-down, poorly documented Mode 22 requests that vary wildly and aren't well suited for a clean simulation demo.

If down the line you want to test against a **real car** for validation, a 2015+ Hyundai/Kia or GM vehicle gives you the best mix of easy availability in India, solid standard PID accuracy (factory sensor tolerances, same as dashboard-grade), and enough enhanced-PID documentation online to extend your simulator credibly without needing proprietary dealer tools.

---

## References

- OBD-II PIDs - Wikipedia
- OBD2 PID Overview - CS Selectronics
- OBDLink Enhanced Diagnostics
- ELM327-OBD-Simulator - GitHub
- ECUSim - GitHub
- ESP32-ECU-emulator - GitHub