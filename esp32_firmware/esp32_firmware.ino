#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <WiFi.h>
#include <esp_now.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <esp_idf_version.h>
#include <Fonts/FreeSans9pt7b.h>

/*
 * V2V Hardware Node - Hybrid PC Bridge & Transceiver
 */

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1 
#define SCREEN_ADDRESS 0x3C

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// MPU6050 on secondary I2C bus (Wire1)
#define MPU_SDA 32
#define MPU_SCL 33
TwoWire I2CMPU = TwoWire(1);
Adafruit_MPU6050 mpu;

// --- Status LEDs ---
#define LED_YELLOW 25
#define LED_RED    26

// --- Custom Bitmaps (16x16) ---
const unsigned char icon_car[] PROGMEM = {
  0x00, 0x00, 0x00, 0x00, 0xf0, 0x0f, 0x08, 0x10, 0x04, 0x20, 0x82, 0x41,
  0x7e, 0x7e, 0x81, 0x81, 0x81, 0x81, 0xff, 0xff, 0x81, 0x81, 0x42, 0x42,
  0x3c, 0x3c, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
};
const unsigned char icon_warning[] PROGMEM = {
  0x00, 0x00, 0x80, 0x01, 0xc0, 0x03, 0x40, 0x02, 0x60, 0x06, 0x60, 0x06,
  0x30, 0x0c, 0x30, 0x0c, 0x38, 0x1c, 0x18, 0x18, 0x18, 0x18, 0x0c, 0x30,
  0x00, 0x00, 0x0c, 0x30, 0xff, 0xff, 0x00, 0x00
};
const unsigned char icon_siren[] PROGMEM = {
  0x00, 0x00, 0xe0, 0x07, 0xf0, 0x0f, 0xf8, 0x1f, 0xf8, 0x1f, 0x1c, 0x38,
  0x1c, 0x38, 0x1c, 0x38, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
};

uint8_t broadcastAddress[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

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
};
#pragma pack(pop)

VehicleStatePacket myState;
VehicleStatePacket receivedAlert;

unsigned long lastSerialUpdate = 0;
unsigned long alertReceivedTime = 0;
const unsigned long ALERT_DISPLAY_TIME = 3500; 

enum DisplayState { STATE_BOOT, STATE_WAITING, STATE_TRACKING, STATE_WARNING, STATE_DISCONNECTED };
DisplayState currentState = STATE_BOOT;

// Smooth Animation Variables
float currentSpeedDisplay = 0.0;
float currentBarWidth = 0.0;
unsigned long bootTime = 0;

#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5, 0, 0)
void OnDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
#else
void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
#endif
  // Silent success/fail
}

#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5, 0, 0)
void OnDataRecv(const esp_now_recv_info_t *info, const uint8_t *incomingData, int len) {
#else
void OnDataRecv(const uint8_t * mac, const uint8_t *incomingData, int len) {
#endif
  if (len == sizeof(VehicleStatePacket)) {
    VehicleStatePacket incoming;
    memcpy(&incoming, incomingData, sizeof(incoming));
    
    // Trigger on any event > 0, except our own
    if (incoming.event > 0 && incoming.vehicle_id != myState.vehicle_id) {
      memcpy(&receivedAlert, &incoming, sizeof(incoming));
      alertReceivedTime = millis();
      currentState = STATE_WARNING;
    }
  }
}

void setup() {
  Serial.begin(115200);
  
  if(!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
    Serial.println(F("SSD1306 allocation failed"));
    for(;;);
  }
  
  I2CMPU.begin(MPU_SDA, MPU_SCL);
  if (!mpu.begin(0x68, &I2CMPU)) {
    Serial.println("Failed to find MPU6050 chip");
  } else {
    mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    mpu.setGyroRange(MPU6050_RANGE_500_DEG);
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
  }
  
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  
  pinMode(LED_YELLOW, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  digitalWrite(LED_YELLOW, LOW);
  digitalWrite(LED_RED, LOW);
  
  if (esp_now_init() != ESP_OK) {
    display.clearDisplay();
    display.setFont(&FreeSans9pt7b);
    display.setCursor(0,20);
    display.print("ESP-NOW Fail");
    display.display();
    return;
  }
  
  esp_now_register_send_cb(OnDataSent);
  esp_now_register_recv_cb(OnDataRecv);
  
  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr, broadcastAddress, 6);
  peerInfo.channel = 0; 
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK) return;

  myState.vehicle_id = '-';
  myState.speed_x100 = 0;
  myState.accel_x100 = 0;
  myState.event = 0; 
  
  bootTime = millis();
  currentState = STATE_BOOT;
}

// Linear interpolation for smooth animations
float smoothLerp(float a, float b, float t) {
  return a + t * (b - a);
}

void drawStateBoot(unsigned long currentMillis) {
  display.setFont(&FreeSans9pt7b);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(16, 25);
  display.print(F("V2V SYSTEM"));
  
  display.drawRoundRect(14, 40, 100, 8, 4, SSD1306_WHITE);
  
  float progress = constrain((currentMillis - bootTime) / 1000.0, 0.0, 1.0);
  int barW = (int)(progress * 96);
  display.fillRoundRect(16, 42, barW, 4, 2, SSD1306_WHITE);
  
  if (progress >= 1.0) {
    currentState = STATE_WAITING;
  }
}

void drawStateWaiting(unsigned long currentMillis) {
  display.setFont(); // Use default font for small text
  display.setCursor(20, 20);
  display.println(F("Waiting for PC..."));
  
  // Pulsing animation
  int w = (currentMillis / 15) % 100;
  display.drawRoundRect(14, 40, 100, 6, 3, SSD1306_WHITE);
  display.fillRoundRect(14 + w, 40, 10, 6, 3, SSD1306_WHITE);
}

void drawStateDisconnected() {
  display.drawBitmap(56, 10, icon_warning, 16, 16, SSD1306_WHITE);
  display.setFont();
  display.setCursor(18, 35);
  display.println(F("PC DISCONNECTED"));
  display.drawRoundRect(14, 50, 100, 6, 3, SSD1306_WHITE);
}

void drawStateTracking(unsigned long currentMillis) {
  float targetSpeed = (myState.speed_x100 / 100.0) * 3.6;
  currentSpeedDisplay = smoothLerp(currentSpeedDisplay, targetSpeed, 0.15);
  
  // Header
  display.setFont();
  display.setCursor(0, 0);
  display.print(F("ID: "));
  display.print(myState.vehicle_id);
  display.setCursor(80, 0);
  display.print(F("V2V: ON"));
  display.drawLine(0, 10, 128, 10, SSD1306_WHITE);
  
  // Icon
  display.drawBitmap(2, 14, icon_car, 16, 16, SSD1306_WHITE);
  
  // Speed Number
  display.setFont(&FreeSans9pt7b);
  display.setCursor(25, 28);
  int displaySpeed = (int)currentSpeedDisplay;
  if (displaySpeed < 10) display.print("00");
  else if (displaySpeed < 100) display.print("0");
  display.print(displaySpeed);
  
  // Unit
  display.setFont();
  display.setCursor(75, 20);
  display.print(F("km/h"));
  
  // Smooth Speed Bar
  display.drawRoundRect(0, 42, 128, 6, 3, SSD1306_WHITE);
  float targetBarWidth = map(constrain(displaySpeed, 0, 160), 0, 160, 0, 124);
  currentBarWidth = smoothLerp(currentBarWidth, targetBarWidth, 0.2);
  display.fillRoundRect(2, 44, (int)currentBarWidth, 2, 1, SSD1306_WHITE);
  
  // Status Footer
  display.setCursor(0, 54);
  if (myState.event == 0) {
    display.print(F("Status: [ NORMAL ]"));
  } else if (myState.event == 1) {
    display.print(F("! OVERSPEED WARN !"));
  } else if (myState.event == 4) {
    display.print(F("!! CRASH DETECT !!"));
  } else if (myState.event == 8) {
    display.print(F("!! EMERGENCY SIREN"));
  } else {
    display.print(F("Status: [ ALERT ]"));
  }
}

void drawStateWarning(unsigned long currentMillis) {
  bool flash = (currentMillis / 150) % 2 == 0;
  
  if (flash) {
    display.fillScreen(SSD1306_WHITE);
    display.setTextColor(SSD1306_BLACK);
  } else {
    display.setTextColor(SSD1306_WHITE);
  }
  
  display.setFont(&FreeSans9pt7b);
  display.setCursor(26, 18);
  if (receivedAlert.event == 8) {
    display.print(F("SIREN!"));
    if (!flash) display.drawBitmap(5, 5, icon_siren, 16, 16, SSD1306_WHITE);
  } else {
    display.print(F("WARNING!"));
    if (!flash) display.drawBitmap(5, 5, icon_warning, 16, 16, SSD1306_WHITE);
  }
  
  display.setFont();
  display.setCursor(0, 26);
  display.print(F("FROM: Car "));
  display.print(receivedAlert.vehicle_id);
  
  if (flash) display.drawLine(0, 36, 128, 36, SSD1306_BLACK);
  else display.drawLine(0, 36, 128, 36, SSD1306_WHITE);
  
  display.setCursor(0, 42);
  if (receivedAlert.event == 1) display.print(F(">>> OVERSPEED <<<"));
  else if (receivedAlert.event == 2) display.print(F(">>> HARD BRAKING"));
  else if (receivedAlert.event == 4) display.print(F(">>> CRASH ALERT!"));
  else if (receivedAlert.event == 8) display.print(F(">>> YIELD NOW!"));
  else { display.print(F("EVENT: ")); display.print(receivedAlert.event); }
  
  // Hazard footer
  if (!flash) display.fillRoundRect(0, 52, 128, 12, 3, SSD1306_WHITE);
  else display.drawRoundRect(0, 52, 128, 12, 3, SSD1306_BLACK);
  
  if (!flash) display.setTextColor(SSD1306_BLACK);
  display.setCursor(18, 54);
  display.print(F("HAZARD DETECTED"));
  display.setTextColor(SSD1306_WHITE);
}

void loop() {
  unsigned long currentMillis = millis();
  
  // 1. Handle Serial Data Non-Blocking
  while (Serial.available() >= sizeof(VehicleStatePacket) + 2) {
    if (Serial.read() == 0xAA) {
      if (Serial.peek() == 0x55) {
        Serial.read(); // Consume 0x55
        
        VehicleStatePacket packet;
        if (Serial.readBytes((char*)&packet, sizeof(VehicleStatePacket)) == sizeof(VehicleStatePacket)) {
          memcpy(&myState, &packet, sizeof(VehicleStatePacket));
          lastSerialUpdate = currentMillis;
          
          // Update Status LEDs
          if (myState.event == 2 || myState.event == 4) { // HARSH_BRAKING / CRASH
            digitalWrite(LED_RED, HIGH);
            digitalWrite(LED_YELLOW, LOW);
          } else if (myState.event == 8) { // AMBULANCE
            digitalWrite(LED_RED, LOW);
            bool blink = (currentMillis / 250) % 2 == 0;
            digitalWrite(LED_YELLOW, blink ? HIGH : LOW);
          } else if (myState.event == 1) { // OVERSPEED
            digitalWrite(LED_RED, LOW);
            digitalWrite(LED_YELLOW, HIGH);
          } else { // NORMAL
            digitalWrite(LED_RED, LOW);
            digitalWrite(LED_YELLOW, LOW);
          }
          
          // Broadcast via ESP-NOW
          esp_now_send(broadcastAddress, (uint8_t *) &myState, sizeof(myState));
        }
      }
    }
  }
  
  // 2. State Machine Logic
  if (currentState != STATE_BOOT) {
    if (currentMillis - alertReceivedTime < ALERT_DISPLAY_TIME && alertReceivedTime != 0) {
      currentState = STATE_WARNING;
    } else if (currentMillis - lastSerialUpdate > 2000 && lastSerialUpdate != 0) {
      currentState = STATE_DISCONNECTED;
    } else if (lastSerialUpdate != 0) {
      currentState = STATE_TRACKING;
    } else {
      currentState = STATE_WAITING;
    }
  }
  
  // 3. Handle MPU6050 (Send to PC)
  static unsigned long lastMpuUpdate = 0;
  if (currentMillis - lastMpuUpdate > 50) { // 20 Hz
    lastMpuUpdate = currentMillis;
    sensors_event_t a, g, temp;
    mpu.getEvent(&a, &g, &temp);
    
    Serial.print("MPU:");
    Serial.print(a.acceleration.x); Serial.print(",");
    Serial.print(a.acceleration.y); Serial.print(",");
    Serial.print(a.acceleration.z); Serial.print(",");
    Serial.print(g.gyro.x); Serial.print(",");
    Serial.print(g.gyro.y); Serial.print(",");
    Serial.println(g.gyro.z);
  }
  
  // 4. Render Current State
  display.clearDisplay();
  
  switch (currentState) {
    case STATE_BOOT:      drawStateBoot(currentMillis); break;
    case STATE_WAITING:   drawStateWaiting(currentMillis); break;
    case STATE_DISCONNECTED: drawStateDisconnected(); break;
    case STATE_TRACKING:  drawStateTracking(currentMillis); break;
    case STATE_WARNING:   drawStateWarning(currentMillis); break;
  }
  
  display.display();
}
