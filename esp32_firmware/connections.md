# ESP32 V2V Hardware Node Connections

This document tracks the physical hardware wiring for your ESP32-S V2V node.

## Current Setup: OLED Dashboard & MPU6050
The ESP32 acts as a serial bridge transceiver. It uses a 0.96" OLED display to show live telemetry, and an MPU6050 IMU to detect physical rollovers, sending the accelerometer and gyroscope data back to the simulator.

| Component         | ESP32-S Pin          | Purpose                                   |
| :---              | :---                 | :---                                      |
| **OLED (I2C 0)**  | GPIO 21 (SDA)        | I2C Data Line for OLED                    |
| **OLED (I2C 0)**  | GPIO 22 (SCL)        | I2C Clock Line for OLED                   |
| **MPU (I2C 1)**   | GPIO 32 (SDA)        | Secondary I2C Data Line for MPU6050       |
| **MPU (I2C 1)**   | GPIO 33 (SCL)        | Secondary I2C Clock Line for MPU6050      |
| **LED Yellow**    | GPIO 25              | Status LED (Overspeed / Ambulance)        |
| **LED Red**       | GPIO 26              | Status LED (Harsh Brake / Crash)          |
| **VCC**           | 3.3V                 | Power for OLED and MPU6050                |
| **GND**           | GND                  | Common ground                             |

*(Note: The OLED uses the default I2C bus on pins 21/22. The MPU6050 uses a secondary hardware I2C bus (`Wire1`) assigned to pins 32/33 to keep the wiring physically separated.)*

## Planned Expansion
Later, you can add more hardware such as:
- LEDs / Buzzers for physical alerts
- GPS module for real coordinates
