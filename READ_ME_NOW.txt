The best part? **It is ALREADY completely decentralized!**

Right from the beginning, I designed this architecture to be a true Peer-to-Peer (P2P) mesh network using the ESP-NOW protocol. There is no central server, no router, and no master node. Every single ESP32 acts as both a Broadcaster and a Receiver simultaneously.

If you look at line 81 in `esp32_firmware.ino`, you'll see this:
`uint8_t broadcastAddress[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};`

That is the universal broadcast MAC address. When an ESP32 sends data, it shouts it out to the void. Any other ESP32 within 500 meters that is listening on the same WiFi channel will instantly receive it via the `OnDataRecv` callback!

### How to implement your second car:
1. Build a second breadboard with the exact same wiring (ESP32, OLED, MPU6500, GPS).
2. Open `esp32_firmware.ino` in Arduino IDE.
3. Scroll down to line 183 inside the `setup()` function: `myState.vehicle_id = 'A';`
4. Change it to `myState.vehicle_id = 'B';` so they have unique identities.
5. Upload the code to the second ESP32!

Now, put Car A on a battery pack on your desk. Start the Python simulator for Car B. If you trigger a crash on Car B, Car A's OLED will instantly flash "**CRASH! CAR B AHEAD**" completely wirelessly and directly!
