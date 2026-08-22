# ESP32 V2V Hardware Node Connections

This document tracks the physical hardware wiring for your ESP32-S V2V node.

## Current Setup: OLED Dashboard & MPU6500
The ESP32 acts as a serial bridge transceiver. It uses a 1.3" OLED display (SH1106) to show live telemetry, and an MPU6500 IMU to detect physical rollovers, sending the accelerometer and gyroscope data back to the simulator.

| Component         | ESP32-S Pin          | Purpose                                   |
| :---              | :---                 | :---                                      |
| **OLED (I2C 0)**  | GPIO 21 (SDA)        | I2C Data Line for OLED                    |
| **OLED (I2C 0)**  | GPIO 22 (SCL)        | I2C Clock Line for OLED                   |
| **MPU (I2C 1)**   | GPIO 32 (SDA)        | Secondary I2C Data Line for MPU6500       |
| **MPU (I2C 1)**   | GPIO 33 (SCL)        | Secondary I2C Clock Line for MPU6500      |
| **GPS NEO-6M**    | GPIO 16 (RX2)        | UART2 RX for GPS                          |
| **GPS NEO-6M**    | GPIO 17 (TX2)        | UART2 TX for GPS                          |
| **LED Green**     | GPIO 27              | Status LED (Normal / Safe)                |
| **LED Yellow**    | GPIO 25              | Status LED (Overspeed / Ambulance)        |
| **LED Red**       | GPIO 26              | Status LED (Harsh Brake / Crash)          |
| **Buzzer**        | GPIO 14              | Passive buzzer for auditory alerts        |
| **GPS NEO-6M**    | 5V / VIN             | Power for GPS (Requires 5V for stability) |

| **VCC**           | 3.3V                 | Power for OLED and MPU6500                |
| **GND**           | GND                  | Common ground for all components          |

*(Note: The OLED uses the default I2C bus on pins 21/22. The MPU6500 uses a secondary hardware I2C bus (`Wire1`) assigned to pins 32/33.)*

## Future Expansion
Later, you can add more hardware such as:
- Additional physical sensors (LIDAR, ultrasonic)
