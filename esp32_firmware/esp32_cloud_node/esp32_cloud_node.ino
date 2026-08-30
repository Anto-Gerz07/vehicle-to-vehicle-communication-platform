/*
 * ESP32 V2V Cloud Node - Emergency & Normal Vehicle Broadcaster
 * -------------------------------------------------------------
 * Hardware:
 *   - ESP32-S Node
 *   - NEO-6M GPS Module on UART2 (GPIO 16 RX, GPIO 17 TX)
 *   - SSD1306 0.96" OLED on I2C (GPIO 21 SDA, GPIO 22 SCL)
 *   - Status LEDs: Green (GPIO 27), Yellow/Blue (GPIO 25), Red (GPIO 26)
 *   - Buzzer: GPIO 14
 * 
 * Emergency Vehicle Mode:
 *   - Set IS_EMERGENCY_VEHICLE to true
 *   - Broadcasts location and heading with vehicle_type = "emergency"
 *   - On the web map, renders as a RED ARROW:
 *       * Flashes RED and BLUE when approaching behind any normal vehicle
 *       * Transitions to plain solid RED once it crosses/passes ahead
 *   - Plays emergency siren buzzer tones and LED lightbar strobe on physical hardware!
 */

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <TinyGPS++.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ==================== CONFIGURATION ====================
// 1. WiFi Hotspot / In-Vehicle WiFi Credentials
const char* WIFI_SSID     = "YOUR_WIFI_OR_HOTSPOT";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// 2. Emergency Vehicle Flag (Set to true for Ambulance/Police/Fire)
const bool  IS_EMERGENCY_VEHICLE = true; 

// 3. Unique Vehicle Identifier
const char* VEHICLE_ID    = "AMBULANCE_108"; // e.g. "AMBULANCE_01", "POLICE_04", "CAR_01"

// 4. Cloud Server URL
const char* SERVER_URL    = "https://v2v-map-platform.onrender.com/gps";
// For Local Testing: "http://192.168.1.100:8080/gps"
// =======================================================

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// GPS NEO-6M on UART2
#define RXD2 16
#define TXD2 17
HardwareSerial GPS(2);
TinyGPSPlus gps;

// Status LEDs & Buzzer (refer connections.md)
#define LED_GREEN  27
#define LED_BLUE   25 // Or Yellow
#define LED_RED    26
#define BUZZER_PIN 14
#define BUTTON_PIN 0  // BOOT button for manual hazard drop

unsigned long lastSendTime = 0;
const unsigned long SEND_INTERVAL_MS = 1000; // 1 Hz GPS update

void setup() {
  Serial.begin(115200);
  GPS.begin(9600, SERIAL_8N1, RXD2, TXD2);
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_BLUE, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_BLUE, LOW);
  digitalWrite(LED_RED, LOW);
  noTone(BUZZER_PIN);

  // Initialize OLED
  if (display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(5, 5);
    display.println(IS_EMERGENCY_VEHICLE ? "🚨 EMERGENCY NODE" : "🚗 V2V VEHICLE NODE");
    display.setCursor(5, 22);
    display.print("ID: "); display.println(VEHICLE_ID);
    display.setCursor(5, 40);
    display.println("Connecting WiFi...");
    display.display();
  }

  // Connect to WiFi
  Serial.print("Connecting to WiFi: ");
  Serial.println(WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi Connected! Local IP: " + WiFi.localIP().toString());
    digitalWrite(LED_GREEN, HIGH);
  } else {
    Serial.println("\nWiFi searching in background...");
  }
}

void sendTelemetry(int eventCode = 0) {
  if (WiFi.status() != WL_CONNECTED) {
    WiFi.reconnect();
    return;
  }

  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");

  float lat = gps.location.isValid() ? gps.location.lat() : 12.8406;
  float lng = gps.location.isValid() ? gps.location.lng() : 80.1534;
  float speed = gps.speed.isValid() ? gps.speed.kmph() : (IS_EMERGENCY_VEHICLE ? 65.0 : 0.0);
  float heading = gps.course.isValid() ? gps.course.deg() : 0.0;
  int sats = gps.satellites.isValid() ? gps.satellites.value() : 0;
  String status = gps.location.isValid() ? "LOCKED" : "NO_LOCK";

  String json = "{";
  json += "\"vehicle_id\":\"" + String(VEHICLE_ID) + "\",";
  json += "\"vehicle_type\":\"" + String(IS_EMERGENCY_VEHICLE ? "emergency" : "normal") + "\",";
  json += "\"is_emergency\":" + String(IS_EMERGENCY_VEHICLE ? "true" : "false") + ",";
  json += "\"lat\":" + String(lat, 6) + ",";
  json += "\"lng\":" + String(lng, 6) + ",";
  json += "\"speed\":" + String(speed, 1) + ",";
  json += "\"heading\":" + String(heading, 1) + ",";
  json += "\"sats\":" + String(sats) + ",";
  json += "\"status\":\"" + status + "\"";

  if (eventCode > 0) {
    json += ",\"event\":" + String(eventCode);
  }
  json += "}";

  int httpCode = http.POST(json);
  if (httpCode > 0) {
    Serial.printf("[HTTP %d] %s\n", httpCode, json.c_str());
  } else {
    Serial.printf("[HTTP ERROR] %s\n", http.errorToString(httpCode).c_str());
  }
  http.end();
}

void updateHardwareSirenLights() {
  if (!IS_EMERGENCY_VEHICLE) return;

  // Strobe alternating Red and Blue LEDs with high-low siren tone
  unsigned long ms = millis();
  bool phase = (ms / 150) % 2 == 0;
  digitalWrite(LED_RED, phase ? HIGH : LOW);
  digitalWrite(LED_BLUE, phase ? LOW : HIGH);
  digitalWrite(LED_GREEN, LOW);

  // High-low alternating siren on buzzer
  if ((ms / 350) % 2 == 0) {
    tone(BUZZER_PIN, 950);
  } else {
    tone(BUZZER_PIN, 650);
  }
}

void updateOledDisplay() {
  display.clearDisplay();
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.print(IS_EMERGENCY_VEHICLE ? "EMERGENCY: " : "CAR: ");
  display.print(VEHICLE_ID);
  display.drawLine(0, 10, 128, 10, SSD1306_WHITE);

  display.setCursor(0, 20);
  display.print("Speed: ");
  if (gps.speed.isValid()) {
    display.print((int)gps.speed.kmph());
    display.print(" km/h");
  } else {
    display.print(IS_EMERGENCY_VEHICLE ? "65 km/h" : "0 km/h");
  }

  display.setCursor(0, 35);
  display.print("Course: ");
  display.print(gps.course.isValid() ? (int)gps.course.deg() : 0);
  display.print((char)247);

  display.setCursor(0, 50);
  display.print("WiFi: ");
  display.print(WiFi.status() == WL_CONNECTED ? "ONLINE" : "SEARCH");
  display.setCursor(75, 50);
  display.print("Sats: ");
  display.print(gps.satellites.isValid() ? gps.satellites.value() : 0);

  display.display();
}

void loop() {
  // Feed GPS parser
  while (GPS.available() > 0) {
    gps.encode(GPS.read());
  }

  // Update physical lightbar and siren if emergency vehicle
  if (IS_EMERGENCY_VEHICLE) {
    updateHardwareSirenLights();
  }

  // Check BOOT button to manually broadcast hazard (Event 5 = Pothole)
  if (digitalRead(BUTTON_PIN) == LOW) {
    delay(50);
    if (digitalRead(BUTTON_PIN) == LOW) {
      Serial.println("[MANUAL HAZARD REPORTED]");
      sendTelemetry(5);
      delay(800);
    }
  }

  // Send GPS to Cloud every 1s
  unsigned long now = millis();
  if (now - lastSendTime >= SEND_INTERVAL_MS) {
    lastSendTime = now;
    sendTelemetry(0);
    updateOledDisplay();
  }
}
