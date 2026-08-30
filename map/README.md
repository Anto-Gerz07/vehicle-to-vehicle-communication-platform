# 🚗 V2V Dynamic Navigation, Multi-Fleet & Emergency Vehicle Map

A real-time Vehicle-to-Vehicle (V2V) mapping and road safety telemetry platform designed for Linux Mint, Cloud Hosting (Render), and ESP32 embedded nodes.

---

## 🌟 Key Features

1. **🚨 Emergency Vehicle Broadcast & Dynamic Visuals**:
   - ESP32 nodes in emergency vehicles (Ambulance, Police, Fire) broadcast their live coordinates, speed, and heading.
   - **Flashing RED & BLUE Strobe Lightbar**: When the emergency vehicle is **BEHIND** any normal vehicle, its red arrow icon and radar aura rapidly flash alternating Red and Blue.
   - **Urgent HUD Alert**: Normal vehicles ahead receive an urgent siren audio chime and warning banner: *"🚨 EMERGENCY VEHICLE APPROACHING BEHIND! PLEASE YIELD"*.
   - **Plain Solid Red Arrow**: Once the emergency vehicle **crosses and moves ahead**, the strobe stops and it transitions to a solid plain red arrow.

2. **🛰️ Real-time Multi-Vehicle GPS Tracking**:
   - Ingests NEO-6M GPS coordinates from multiple ESP32s via USB Serial or HTTP POST `/gps`.
   - Each vehicle has its own rotating directional arrow marker (`0–360°`), breadcrumb trail, and live HUD telemetry.

3. **🕳️ Road Hazard Reporting & Touchscreen Virtual Keyboard**:
   - Report potholes, speed bumps, roadblocks, traffic, and custom hazards.
   - Digital on-screen QWERTY virtual touch keyboard for in-car touchscreens/tablets.

4. **👥 3-Vote Community Consensus Verification**:
   - Proximity detection triggers an interactive dialog: *"Is this hazard still present?"*
   - With **3 or more "No" votes**, the hazard is automatically removed from all maps in real time.

5. **🧪 Built-in Interactive Simulator**:
   - **"🚨 Spawn Ambulance Behind"**: Instantly places an emergency vehicle behind your car to watch the red/blue flashing strobe and hear the siren.
   - **"💨 Ambulance Passes Ahead"**: Animates the ambulance overtaking your car so you can watch it cross ahead and turn into solid plain red.
   - **"🚗 Start Test Drive"**: Smooth virtual loop drive past sample potholes and speed breakers.

---

## 🚀 Cloud Deployment (Render.com)

1. Push this repository to your GitHub:
   ```bash
   git add .
   git commit -m "Add emergency vehicle red/blue strobe and solid red transition"
   git push -u origin main
   ```
2. Go to **[dashboard.render.com](https://dashboard.render.com)** → **New Web Service** → Select your repo.
3. Render reads [`render.yaml`](../render.yaml) and automatically deploys your live server!

---

## 📡 ESP32 Emergency Vehicle Setup

Flash [`esp32_firmware/esp32_cloud_node/esp32_cloud_node.ino`](../esp32_firmware/esp32_cloud_node/esp32_cloud_node.ino) to the ESP32:

```cpp
const bool  IS_EMERGENCY_VEHICLE = true; // Set true for Ambulance/Police
const char* VEHICLE_ID           = "AMBULANCE_108";
const char* SERVER_URL           = "https://v2v-map-platform.onrender.com/gps";
```
