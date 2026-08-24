#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <SPI.h>
#include <LoRa.h>
#include <esp_idf_version.h>

// Define the pins used by the LoRa transceiver module
#define ss 5
#define rst 14
#define dio0 26

#pragma pack(push, 1)
struct VehicleStatePacket {
  char vehicle_id;
  uint16_t seq;
  uint32_t timestamp;
  int16_t speed_x100;
  int16_t accel_x100;
  int16_t heading;
  uint8_t event;
  uint8_t confidence;
  float latitude;
  float longitude;
};
#pragma pack(pop)

volatile bool newPacketAvailable = false;
VehicleStatePacket latestPacket;
unsigned long lastLoRaSend = 0;
const unsigned long LORA_SEND_INTERVAL = 200; // Max 5Hz to avoid channel congestion

#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5, 0, 0)
void OnDataRecv(const esp_now_recv_info_t *info, const uint8_t *incomingData, int len) {
#else
void OnDataRecv(const uint8_t * mac, const uint8_t *incomingData, int len) {
#endif
  if (len == sizeof(VehicleStatePacket)) {
    memcpy((void*)&latestPacket, incomingData, sizeof(latestPacket));
    newPacketAvailable = true;
  }
}

void setup() {
  Serial.begin(115200);
  while (!Serial)
    ;

  Serial.println("LoRa V2V Transmitter (Bridge) Booting...");

  // Setup WiFi in Station Mode for ESP-NOW
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  
  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW Init Failed");
    return;
  }
  esp_now_register_recv_cb(OnDataRecv);
  Serial.println("ESP-NOW Ready");

  // Setup LoRa transceiver module
  LoRa.setPins(ss, rst, dio0);

  // Initialize LoRa at 433 MHz
  if (!LoRa.begin(433E6)) {
    Serial.println("Starting LoRa failed! Check wiring.");
    while (1)
      ;
  }

  // Enable hardware CRC to drop corrupted noise packets
  LoRa.enableCrc();

  // Optional: Set transmission power to max (20dBm) for testing range
  LoRa.setTxPower(20);
  Serial.println("LoRa Ready!");
}

void loop() {
  // If we have a new ESP-NOW packet and enough time has passed to send via LoRa
  if (newPacketAvailable && (millis() - lastLoRaSend >= LORA_SEND_INTERVAL)) {
    VehicleStatePacket packetToSend;
    
    // Safely copy the packet data out of the volatile shared buffer
    noInterrupts();
    memcpy(&packetToSend, (const void*)&latestPacket, sizeof(VehicleStatePacket));
    newPacketAvailable = false;
    interrupts();

    Serial.print("Forwarding ESP-NOW Packet -> ID: ");
    Serial.print(packetToSend.vehicle_id);
    Serial.print(" | Event: ");
    Serial.println(packetToSend.event);

    // Send the raw binary packet over LoRa
    LoRa.beginPacket();
    LoRa.write((uint8_t*)&packetToSend, sizeof(VehicleStatePacket));
    LoRa.endPacket();

    lastLoRaSend = millis();
  }
}