# ESP32 V2V Hardware Node Connections

This document tracks the physical hardware wiring for your ESP32-S V2V node.

## Current Setup: OLED Dashboard & MPU6500
The ESP32 acts as a serial bridge transceiver. It uses a 0.96" OLED display (SSD1306) to show live telemetry, and an MPU6500 IMU to detect physical rollovers, sending the accelerometer and gyroscope data back to the simulator.

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

## LoRa Nodes (Sender & Receiver)

If you are using the LoRa Sender and Receiver nodes to bridge ESP-NOW data over long distances:

### LoRa Sender Node (Intermediate Bridge)
The Sender node requires a LoRa module and acts as a bridge. It does not need the OLED, Buzzer, or LEDs.
| Component         | ESP32-S Pin          | Purpose                                   |
| :---              | :---                 | :---                                      |
| **LoRa NSS**      | GPIO 5               | SPI Chip Select for LoRa                  |
| **LoRa RST**      | GPIO 14              | Reset for LoRa                            |
| **LoRa DIO0**     | GPIO 26              | Interrupt for LoRa                        |
| **LoRa MOSI**     | GPIO 23              | Standard VSPI MOSI                        |
| **LoRa MISO**     | GPIO 19              | Standard VSPI MISO                        |
| **LoRa SCK**      | GPIO 18              | Standard VSPI SCK                         |

### LoRa Receiver Node (Remote Dashboard)
The Receiver node acts like the standard dashboard but receives data via LoRa instead of ESP-NOW. 
**Note:** To avoid pin conflicts with the LoRa module, the Buzzer and Red LED pins have been reassigned on this node.

| Component         | ESP32-S Pin          | Purpose                                   |
| :---              | :---                 | :---                                      |
| **OLED (I2C 0)**  | GPIO 21 (SDA)        | I2C Data Line for OLED                    |
| **OLED (I2C 0)**  | GPIO 22 (SCL)        | I2C Clock Line for OLED                   |
| **LED Green**     | GPIO 27              | Status LED (Normal / Safe)                |
| **LED Yellow**    | GPIO 25              | Status LED (Overspeed / Ambulance)        |
| **LED Red**       | **GPIO 2**           | Status LED (Harsh Brake / Crash) - *MOVED*|
| **Buzzer**        | **GPIO 15**          | Passive buzzer for auditory alerts - *MOVED*|
| **MPU (I2C 1)**   | GPIO 32 (SDA)        | Secondary I2C Data Line for MPU6050       |
| **MPU (I2C 1)**   | GPIO 33 (SCL)        | Secondary I2C Clock Line for MPU6050      |
| **LoRa NSS**      | GPIO 5               | SPI Chip Select for LoRa                  |
| **LoRa RST**      | GPIO 14              | Reset for LoRa                            |
| **LoRa DIO0**     | GPIO 26              | Interrupt for LoRa                        |
| **LoRa MOSI**     | GPIO 23              | Standard VSPI MOSI                        |
| **LoRa MISO**     | GPIO 19              | Standard VSPI MISO                        |
| **LoRa SCK**      | GPIO 18              | Standard VSPI SCK                         |
