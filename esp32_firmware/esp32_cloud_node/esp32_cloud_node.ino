/*
 * ESP32 V2V Cloud Node - Multi-Vehicle GPS & Hazard Broadcaster
 * -------------------------------------------------------------
 * Hardware:
 *   - ESP32-S Node
 *   - NEO-6M GPS Module on UART2 (GPIO 16 RX, GPIO 17 TX)
 *   - SSD1306 0.96" OLED on I2C (GPIO 21 SDA, GPIO 22 SCL)
 *   - Status LEDs: Green (GPIO 27), Yellow (GPIO 25), Red (GPIO 26)
 *   - Buzzer: GPIO 14
 * 
 * Function:
 *   - Connects to WiFi hotspot or vehicle WiFi
 *   - Reads live GPS coordinates and course heading
 *   - Sends HTTP POST telemetry to your cloud-hosted map server (/gps)
 *   - Supports reporting potholes, speed bumps, and emergency events
 */

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <TinyGPS++.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ==================== CONFIGURATION ====================
// 1. Enter your WiFi Credentials (or Phone Hotspot)
const char* WIFI_SSID     = "YOUR_WIFI_OR_HOTSPOT_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// 2. Set Unique Vehicle / Node Identifier for this ESP32
const char* VEHICLE_ID    = "CAR_01"; 

// 3. Your Cloud Server URL (Render, Railway, Cloudflare Tunnel, or Local IP)
// Examples:
// Cloud: "https://v2v-map-server.onrender.com/gps"
// Local: "http://192.168.1.100:8080/gps"
const char* SERVER_URL    = "http://192.168.1.100:8080/gps";
// =======================================================

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// GPS on UART2
#define RXD2 16
#define TXD2 17
HardwareSerial GPS(2);
TinyGPSPlus gps;

// Status Indicators (refer connections.md)
#define LED_GREEN  27
#define LED_YELLOW 25
#define LED_RED    26
#define BUZZER_PIN 14

// Hazard Report Button (Optional physical push button to report pothole/hazard)
#define BUTTON_PIN 0 // BOOT button on ESP32 can be pressed to drop a hazard!

unsigned long lastSendTime = 0;
const unsigned long SEND_INTERVAL_MS = 1000; // 1 Hz GPS reporting

void setup() {
  Serial.begin(115200);
  GPS.begin(9600, SERIAL_8N1, RXD2, TXD2);
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_YELLOW, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_YELLOW, LOW);
  digitalWrite(LED_RED, LOW);

  // Initialize OLED
  if (display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(10, 10);
    display.println("V2V CLOUD NODE");
    display.setCursor(10, 26);
    display.print("Node: "); display.println(VEHICLE_ID);
    display.setCursor(10, 42);
    display.println("Connecting WiFi...");
    display.display();
  }

  // Connect to WiFi
  Serial.print("Connecting to WiFi: ");
  Serial.println(WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 25) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi Connected!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    digitalWrite(LED_GREEN, HIGH);
  } else {
    Serial.println("\nWiFi connection failed, will retry in loop.");
    digitalWrite(LED_YELLOW, HIGH);
  }
}

void sendGpsDataToServer(int eventCode = 0) {
  if (WiFi.status() != WL_CONNECTED) {
    WiFi.reconnect();
    return;
  }

  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");

  // Format GPS JSON payload
  float lat = gps.location.isValid() ? gps.location.lat() : 12.8406;
  float lng = gps.location.isValid() ? gps.location.lng() : 80.1534;
  float speed = gps.speed.isValid() ? gps.speed.kmph() : 0.0;
  float heading = gps.course.isValid() ? gps.course.deg() : 0.0;
  int sats = gps.satellites.isValid() ? gps.satellites.value() : 0;
  String status = gps.location.isValid() ? "LOCKED" : "SEARCHING";

  String jsonPayload = "{";
  jsonPayload += "\"vehicle_id\":\"" + String(VEHICLE_ID) + "\",";
  jsonPayload += "\"lat\":" + String(lat, 6) + ",";
  jsonPayload += "\"lng\":" + String(lng, 6) + ",";
  jsonPayload += "\"speed\":" + String(speed, 1) + ",";
  jsonPayload += "\"heading\":" + String(heading, 1) + ",";
  jsonPayload += "\"sats\":" + String(sats) + ",";
  jsonPayload += "\"status\":\"" + status + "\"";
  
  if (eventCode > 0) {
    jsonPayload += ",\"event\":" + String(eventCode);
  }
  jsonPayload += "}";

  int httpCode = http.POST(jsonPayload);

  if (httpCode > 0) {
    Serial.printf("[HTTP] POST %d -> %s\n", httpCode, jsonPayload.c_str());
    digitalWrite(LED_GREEN, HIGH);
    digitalWrite(LED_RED, LOW);
  } else {
    Serial.printf("[HTTP] POST failed, error: %s\n", http.errorToString(httpCode).c_str());
    digitalWrite(LED_RED, HIGH);
  }

  http.end();
}

void updateOledDisplay() {
  display.clearDisplay();
  
  // Header
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.print("ID: "); display.print(VEHICLE_ID);
  display.setCursor(75, 0);
  display.print(WiFi.status() == WL_CONNECTED ? "CLOUD:OK" : "NO WIFI");
  display.drawLine(0, 10, 128, 10, SSD1306_WHITE);

  // Speed
  display.setCursor(0, 20);
  display.print("Speed: ");
  if (gps.speed.isValid()) {
    display.print((int)gps.speed.kmph());
    display.print(" km/h");
  } else {
    display.print("0 km/h");
  }

  // Course Heading & Satellites
  display.setCursor(0, 35);
  display.print("Heading: ");
  display.print(gps.course.isValid() ? (int)gps.course.deg() : 0);
  display.print((char)247); // Degree symbol

  display.setCursor(0, 50);
  display.print("Sats: ");
  display.print(gps.satellites.isValid() ? gps.satellites.value() : 0);
  display.setCursor(65, 50);
  display.print(gps.location.isValid() ? "[LOCKED]" : "[SEARCH]");

  display.display();
}

void loop() {
  // Feed the TinyGPS++ parser with raw UART NMEA bytes
  while (GPS.available() > 0) {
    gps.encode(GPS.read());
  }

  // Check if BOOT button pressed to manually report a Pothole (Event 5)
  if (digitalRead(BUTTON_PIN) == LOW) {
    delay(50); // Debounce
    if (digitalRead(BUTTON_PIN) == LOW) {
      Serial.println("[BUTTON] Reporting POTHOLE hazard to cloud!");
      tone(BUZZER_PIN, 1500, 200);
      sendGpsDataToServer(5); // Event 5 = Pothole
      delay(800);
    }
  }

  // Periodically send GPS telemetry to cloud server
  unsigned long now = millis();
  if (now - lastSendTime >= SEND_INTERVAL_MS) {
    lastSendTime = now;
    sendGpsDataToServer(0);
    updateOledDisplay();
  }
}

