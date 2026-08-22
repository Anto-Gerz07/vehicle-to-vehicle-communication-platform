#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>
#include <WiFi.h>
#include <esp_now.h>
#include <TinyGPS++.h>
#include <SPI.h>
#include <LoRa.h>
// Removed Adafruit_MPU6050 for MPU6500 raw I2C compatibility
#include <esp_idf_version.h>
#include <Fonts/FreeSans9pt7b.h>

// LoRa VSPI Pins
#define LORA_SCK 18
#define LORA_MISO 19
#define LORA_MOSI 23
#define LORA_SS 5
#define LORA_RST 13
#define LORA_DIO0 4

/*
 * V2V Hardware Node - Hybrid PC Bridge & Transceiver
 */

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1 
#define SCREEN_ADDRESS 0x3C

Adafruit_SH1106G display = Adafruit_SH1106G(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// MPU6500 on secondary I2C bus (Wire1)
#define MPU_SDA 32
#define MPU_SCL 33
TwoWire I2CMPU = TwoWire(1);

// GPS NEO-6M on UART2
#define RXD2 16
#define TXD2 17
HardwareSerial GPS(2);
TinyGPSPlus gps;

void initMPU6500() {
  I2CMPU.beginTransmission(0x68);
  I2CMPU.write(0x6B); // Power management
  I2CMPU.write(0x00); // Wake up
  I2CMPU.endTransmission();
  
  // Set accel range to +/- 2g for MAXIMUM sensitivity (was 8g)
  I2CMPU.beginTransmission(0x68);
  I2CMPU.write(0x1C);
  I2CMPU.write(0x00); 
  I2CMPU.endTransmission();
  
  // Set gyro range to +/- 250 deg/s for MAXIMUM sensitivity (was 500)
  I2CMPU.beginTransmission(0x68);
  I2CMPU.write(0x1B);
  I2CMPU.write(0x00);
  I2CMPU.endTransmission();
  
  // Set DLPF to ~41Hz for faster reaction to potholes (was 21Hz)
  I2CMPU.beginTransmission(0x68);
  I2CMPU.write(0x1A);
  I2CMPU.write(0x03);
  I2CMPU.endTransmission();
}

#define LED_GREEN  27
#define LED_YELLOW 25
#define LED_RED    26
#define BUZZER_PIN 14

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
  float latitude;
  float longitude;
};
#pragma pack(pop)

VehicleStatePacket myState;
VehicleStatePacket receivedAlert;

unsigned long lastSerialUpdate = 0;
unsigned long alertReceivedTime = 0;
const unsigned long ALERT_DISPLAY_TIME = 3500; 

enum DisplayState { STATE_BOOT, STATE_WAITING, STATE_TRACKING, STATE_WARNING, STATE_STANDALONE };
DisplayState currentState = STATE_BOOT;

// Global Sensor State for Standalone Mode
float currentRoll = 0.0;
float currentPitch = 0.0;

// Smooth Animation Variables
float currentSpeedDisplay = 0.0;
float currentBarWidth = 0.0;
unsigned long bootTime = 0;

bool lora_ok = false;
unsigned long last_lora_tx = 0;

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
  GPS.begin(9600, SERIAL_8N1, RXD2, TXD2);
  
  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);
  if (!LoRa.begin(433E6)) {
    Serial.println("LoRa initialization failed! Check wiring.");
    lora_ok = false;
  } else {
    Serial.println("LoRa initialized successfully.");
    LoRa.receive(); // Put radio into continuous receive mode
    lora_ok = true;
  }
  
  if(!display.begin(SCREEN_ADDRESS, true)) {
    Serial.println(F("SH1106 allocation failed"));
    for(;;);
  }
  
  I2CMPU.begin(MPU_SDA, MPU_SCL);
  initMPU6500();
  Serial.println("MPU6500 initialized via raw I2C.");
  
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_YELLOW, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_YELLOW, LOW);
  digitalWrite(LED_RED, LOW);
  noTone(BUZZER_PIN);
  
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
  myState.latitude = 0.0;
  myState.longitude = 0.0;
  
  bootTime = millis();
  currentState = STATE_BOOT;
}

// Linear interpolation for smooth animations
float smoothLerp(float a, float b, float t) {
  return a + t * (b - a);
}

void drawStateBoot(unsigned long currentMillis) {
  // Cinematic Boot Logo (Geometric V2V)
  display.drawRect(24, 8, 80, 32, SH110X_WHITE);
  display.drawLine(24, 8, 104, 40, SH110X_WHITE);
  display.drawLine(24, 40, 104, 8, SH110X_WHITE);
  
  display.setFont(&FreeSans9pt7b);
  display.setTextColor(SH110X_WHITE);
  display.setCursor(44, 30);
  display.print("V2V");
  
  display.setFont();
  display.setCursor(44, 46);
  display.print("SYSTEM");
  
  // Clean Loading Bar
  float progress = constrain((currentMillis - bootTime) / 5000.0, 0.0, 1.0);
  int barW = (int)(progress * 100);
  display.drawRoundRect(14, 56, 100, 6, 2, SH110X_WHITE);
  display.fillRoundRect(14, 56, barW, 6, 2, SH110X_WHITE);
  
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
  display.drawRoundRect(14, 40, 100, 6, 3, SH110X_WHITE);
  display.fillRoundRect(14 + w, 40, 10, 6, 3, SH110X_WHITE);
}

void drawStateStandalone(unsigned long currentMillis) {
  display.setFont();
  display.setCursor(0, 0);
  display.print(F("STANDALONE V2V NODE"));
  display.drawLine(0, 10, 128, 10, SH110X_WHITE);
  
  display.setFont(&FreeSans9pt7b);
  display.setCursor(0, 30);
  if (gps.speed.isValid()) {
    display.print((int)gps.speed.kmph());
    display.setFont();
    display.print(F(" km/h"));
  } else {
    display.setFont();
    display.print(F("SEARCHING SATS..."));
  }
  
  display.setFont();
  display.setCursor(0, 42);
  display.print(F("SATS: "));
  display.print(gps.satellites.isValid() ? gps.satellites.value() : 0);
  
  // Right Side: Artificial Horizon (Inclinometer)
  int cx = 100;
  int cy = 34;
  int r = 16;
  display.drawCircle(cx, cy, r, SH110X_WHITE);
  
  // Pitch shifts the line up/down, Roll rotates it
  float pitchScale = 0.3; // pixels per degree
  int yOffset = constrain((int)(currentPitch * pitchScale), -r + 2, r - 2);
  
  float rollRad = currentRoll * PI / 180.0;
  int lineHalfLength = 12; // Length of the horizon line from center
  
  int x1 = cx - (int)(lineHalfLength * cos(rollRad)) + (int)(yOffset * sin(rollRad));
  int y1 = cy + (int)(lineHalfLength * sin(rollRad)) + (int)(yOffset * cos(rollRad));
  
  int x2 = cx + (int)(lineHalfLength * cos(rollRad)) + (int)(yOffset * sin(rollRad));
  int y2 = cy - (int)(lineHalfLength * sin(rollRad)) + (int)(yOffset * cos(rollRad));
  
  display.drawLine(x1, y1, x2, y2, SH110X_WHITE);
  // Center dot
  display.drawPixel(cx, cy, SH110X_WHITE);
  
  // Status Footer
  display.drawRoundRect(0, 52, 128, 12, 3, SH110X_WHITE);
  display.setCursor(12, 54);
  display.print(F("UNTETHERED MODE"));
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
  display.drawLine(0, 10, 128, 10, SH110X_WHITE);
  
  // Icon
  display.drawBitmap(2, 14, icon_car, 16, 16, SH110X_WHITE);
  
  // Speed Number
  display.setFont(&FreeSans9pt7b);
  display.setCursor(25, 34);
  int displaySpeed = (int)currentSpeedDisplay;
  display.print(displaySpeed); // No leading zeros!
  
  // Unit
  display.setFont();
  display.setCursor(75, 26);
  display.print(F("km/h"));
  
  // Status Footer
  display.setCursor(0, 54);
  if (myState.event == 0) {
    display.print(F("Status: [ NORMAL ]"));
  } else if (myState.event == 1) {
    display.print(F("! OVERSPEED WARN !"));
  } else if (myState.event == 2) {
    display.print(F("!! LOSS OF TRACTN"));
  } else if (myState.event == 4) {
    display.print(F("!! CRASH DETECT !!"));
  } else if (myState.event == 5) {
    display.print(F("!! POTHOLE / BUMP"));
  } else if (myState.event == 8) {
    display.print(F("!! EMERGENCY SIREN"));
  } else if (myState.event == 9) {
    display.print(F("!! HARSH BRAKING"));
  } else {
    display.print(F("Status: [ ALERT ]"));
  }
}

void drawStateWarning(unsigned long currentMillis) {
  bool flash = (currentMillis / 150) % 2 == 0;
  
  // Determine if it's a local crash or a received crash
  uint8_t activeEvent = 0;
  char activeId = '?';
  bool isLocal = false;
  
  if (myState.event == 4 || myState.event == 5 || myState.event == 8) {
    activeEvent = myState.event;
    activeId = myState.vehicle_id;
    isLocal = true;
  } else {
    activeEvent = receivedAlert.event;
    activeId = receivedAlert.vehicle_id;
  }
  
  bool isSevere = (activeEvent == 4 || activeEvent == 5 || activeEvent == 8);
  
  // Full-Screen Hijack for Severe Alerts
  if (isSevere) {
    display.fillScreen(flash ? SH110X_WHITE : SH110X_BLACK);
    display.setTextColor(flash ? SH110X_BLACK : SH110X_WHITE);
    
    display.setFont(); // Use default font for scaling
    display.setTextSize(3); // 3x scale!
    
    if (activeEvent == 4) {
      display.setCursor(10, 15);
      display.print(F("CRASH!"));
    } else if (activeEvent == 5) {
      display.setCursor(10, 15);
      display.print(F("HAZARD"));
    } else if (activeEvent == 8) {
      display.setTextSize(2); // Slightly smaller to fit 'EMERGENCY'
      display.setCursor(10, 20);
      display.print(F("EMERGENCY"));
    }
    
    display.setTextSize(1); // Reset scale
    
    display.setFont();
    display.setCursor(20, 45);
    if (isLocal) {
      display.print(F("EVACUATE VEHICLE"));
    } else if (activeEvent == 8) {
      display.setCursor(10, 45); // Shift left a bit
      display.print(F("VEHICLE BEHIND"));
    } else {
      display.print(F("CAR "));
      display.print(activeId);
      display.print(F(" AHEAD"));
    }
    
    // Reset colors for next frame safety
    display.setTextColor(SH110X_WHITE);
    return;
  }
  
  // Standard Minor Warning (Overspeed, Hard Braking)
  if (flash) {
    display.fillScreen(SH110X_WHITE);
    display.setTextColor(SH110X_BLACK);
  } else {
    display.setTextColor(SH110X_WHITE);
  }
  
  display.setFont(&FreeSans9pt7b);
  display.setCursor(26, 18);
  display.print(F("WARNING!"));
  if (!flash) display.drawBitmap(5, 5, icon_warning, 16, 16, SH110X_WHITE);
  
  display.setFont();
  display.setCursor(0, 26);
  if (isLocal) {
    display.print(F("FROM: LOCAL SENSOR"));
  } else {
    display.print(F("FROM: Car "));
    display.print(activeId);
  }
  
  if (flash) display.drawLine(0, 36, 128, 36, SH110X_BLACK);
  else display.drawLine(0, 36, 128, 36, SH110X_WHITE);
  
  display.setCursor(0, 42);
  if (activeEvent == 1) display.print(F(">>> OVERSPEED <<<"));
  else if (activeEvent == 2) display.print(F(">>> LOSS OF TRACTN"));
  else if (activeEvent == 9) display.print(F(">>> HARD BRAKING"));
  else { display.print(F("EVENT: ")); display.print(activeEvent); }
  
  // Hazard footer
  if (!flash) display.fillRoundRect(0, 52, 128, 12, 3, SH110X_WHITE);
  else display.drawRoundRect(0, 52, 128, 12, 3, SH110X_BLACK);
  
  if (!flash) display.setTextColor(SH110X_BLACK);
  display.setCursor(18, 54);
  display.print(F("HAZARD DETECTED"));
  display.setTextColor(SH110X_WHITE);
}

void loop() {
  unsigned long currentMillis = millis();
  
  // Handle LoRa Reception
  if (lora_ok) {
    int packetSize = LoRa.parsePacket();
    if (packetSize) {
      Serial.print("LoRa Rx! Size: ");
      Serial.println(packetSize);
      if (packetSize == sizeof(VehicleStatePacket)) {
        VehicleStatePacket incoming;
        LoRa.readBytes((uint8_t*)&incoming, sizeof(incoming));
        if (incoming.event > 0 && incoming.vehicle_id != myState.vehicle_id) {
          memcpy(&receivedAlert, &incoming, sizeof(incoming));
          alertReceivedTime = millis();
          currentState = STATE_WARNING;
        }
      } else {
        Serial.println("LoRa packet size mismatch!");
      }
    }
  }
  
  // Determine event for Buzzer/LEDs (prioritize incoming warning over normal local state)
  uint8_t activeEventBuzzer = myState.event;
  if (currentState == STATE_WARNING && receivedAlert.event != 0) {
    activeEventBuzzer = receivedAlert.event;
  }
  
  // Update Status LEDs & Buzzer (Continuous Evaluation)
  if (activeEventBuzzer == 8) { // AMBULANCE PATTERN
    bool flash = (currentMillis / 100) % 2 == 0;
    digitalWrite(LED_RED, flash ? HIGH : LOW);
    digitalWrite(LED_YELLOW, flash ? LOW : HIGH);
    digitalWrite(LED_GREEN, LOW);
    if (flash) tone(BUZZER_PIN, 1000); // High siren
    else tone(BUZZER_PIN, 700);        // Low siren
  } else if (activeEventBuzzer == 4 || activeEventBuzzer == 9) { // CRASH / HARSH_BRAKING
    digitalWrite(LED_RED, HIGH);
    digitalWrite(LED_YELLOW, LOW);
    digitalWrite(LED_GREEN, LOW);
    if ((currentMillis / 50) % 2 == 0) tone(BUZZER_PIN, 2000); // Fast aggressive beep
    else noTone(BUZZER_PIN);
  } else if (activeEventBuzzer == 1 || activeEventBuzzer == 5 || activeEventBuzzer == 2) { // OVERSPEED / HAZARD / TRACTN
    digitalWrite(LED_RED, LOW);
    digitalWrite(LED_YELLOW, HIGH);
    digitalWrite(LED_GREEN, LOW);
    if ((currentMillis / 200) % 2 == 0) tone(BUZZER_PIN, 1000); // Slower warning beep
    else noTone(BUZZER_PIN);
  } else { // NORMAL
    digitalWrite(LED_RED, LOW);
    digitalWrite(LED_YELLOW, LOW);
    digitalWrite(LED_GREEN, HIGH);
    noTone(BUZZER_PIN);
  }
  
  // 1. Handle Serial Data Non-Blocking
  while (Serial.available() >= sizeof(VehicleStatePacket) + 2) {
    if (Serial.read() == 0xAA) {
      if (Serial.peek() == 0x55) {
        Serial.read(); // Consume 0x55
        
        VehicleStatePacket packet;
        if (Serial.readBytes((char*)&packet, sizeof(VehicleStatePacket)) == sizeof(VehicleStatePacket)) {
          memcpy(&myState, &packet, sizeof(VehicleStatePacket));
          lastSerialUpdate = currentMillis;
          
          // Inject real GPS coordinates before broadcasting
          if (gps.location.isValid()) {
            myState.latitude = gps.location.lat();
            myState.longitude = gps.location.lng();
          } else {
            myState.latitude = 0.0;
            myState.longitude = 0.0;
          }
          
          // Broadcast via ESP-NOW (Temporarily disabled for LoRa testing)
          // esp_now_send(broadcastAddress, (uint8_t *) &myState, sizeof(myState));
          
          // Broadcast via LoRa (Throttled to 5Hz to prevent locking up the radio)
          if (lora_ok && (currentMillis - last_lora_tx > 200 || myState.event > 0)) {
            last_lora_tx = currentMillis;
            LoRa.beginPacket();
            LoRa.write((uint8_t*)&myState, sizeof(myState));
            LoRa.endPacket();
            LoRa.receive(); // Return to receive mode!
            Serial.println("LoRa Tx");
          }
        }
      }
    }
  }
  
  // 2. State Machine Logic
  if (currentState != STATE_BOOT) {
    bool localSevere = (myState.event == 4 || myState.event == 5 || myState.event == 8);
    
    if (localSevere) {
      currentState = STATE_WARNING;
    } else if (currentMillis - alertReceivedTime < ALERT_DISPLAY_TIME && alertReceivedTime != 0) {
      currentState = STATE_WARNING;
    } else if (currentMillis - lastSerialUpdate > 5000) {
      // Auto-switch to standalone if no PC for 5 seconds
      currentState = STATE_STANDALONE;
    } else if (lastSerialUpdate != 0) {
      currentState = STATE_TRACKING;
    } else {
      currentState = STATE_WAITING;
    }
  }
  
  // Standalone Broadcasting (10 Hz)
  static unsigned long lastStandaloneBroadcast = 0;
  if (currentState == STATE_STANDALONE && currentMillis - lastStandaloneBroadcast > 100) {
    lastStandaloneBroadcast = currentMillis;
    myState.speed_x100 = gps.speed.isValid() ? (int16_t)(gps.speed.mps() * 100) : 0;
    myState.heading = gps.course.isValid() ? (int16_t)gps.course.deg() : 0;
    myState.latitude = gps.location.isValid() ? gps.location.lat() : 0.0;
    myState.longitude = gps.location.isValid() ? gps.location.lng() : 0.0;
    // esp_now_send(broadcastAddress, (uint8_t *) &myState, sizeof(myState));
    
    // Broadcast via LoRa
    if (lora_ok) {
      LoRa.beginPacket();
      LoRa.write((uint8_t*)&myState, sizeof(myState));
      LoRa.endPacket();
      LoRa.receive(); // Return to receive mode!
      Serial.println("LoRa Tx");
    }
  }
  
  // Constantly feed the GPS parser
  while (GPS.available() > 0) {
    gps.encode(GPS.read());
  }

  // 3. Handle Sensors (Send to PC)
  static unsigned long lastMpuUpdate = 0;
  if (currentMillis - lastMpuUpdate > 50) { // 20 Hz
    lastMpuUpdate = currentMillis;
    
    I2CMPU.beginTransmission(0x68);
    I2CMPU.write(0x3B);
    I2CMPU.endTransmission(false);
    I2CMPU.requestFrom((uint16_t)0x68, (uint8_t)14, true);
    
    if (I2CMPU.available() >= 14) {
      int16_t rax = (I2CMPU.read() << 8) | I2CMPU.read();
      int16_t ray = (I2CMPU.read() << 8) | I2CMPU.read();
      int16_t raz = (I2CMPU.read() << 8) | I2CMPU.read();
      I2CMPU.read(); I2CMPU.read(); // Skip temp
      int16_t rgx = (I2CMPU.read() << 8) | I2CMPU.read();
      int16_t rgy = (I2CMPU.read() << 8) | I2CMPU.read();
      int16_t rgz = (I2CMPU.read() << 8) | I2CMPU.read();
      
      // Accel 2g scale -> m/s^2 (1g = 9.80665, 2g = 16384 LSB/g)
      float ax = (rax / 16384.0) * 9.80665;
      float ay = (ray / 16384.0) * 9.80665;
      float az = (raz / 16384.0) * 9.80665;
      
      // Gyro 250 deg/s scale -> rad/s (1 deg = 0.0174533 rad, 250deg/s = 131.0 LSB/deg)
      float gx = (rgx / 131.0) * 0.0174533;
      float gy = (rgy / 131.0) * 0.0174533;
      float gz = (rgz / 131.0) * 0.0174533;
      
      currentRoll = atan2(ay, sqrt(ax*ax + az*az)) * 180.0 / PI;
      currentPitch = atan2(-ax, sqrt(ay*ay + az*az)) * 180.0 / PI;
      
      Serial.print("MPU:");
      Serial.print(ax); Serial.print(",");
      Serial.print(ay); Serial.print(",");
      Serial.print(az); Serial.print(",");
      Serial.print(gx); Serial.print(",");
      Serial.print(gy); Serial.print(",");
      Serial.println(gz);
      
      if (gps.location.isValid()) {
        Serial.print("GPS:");
        Serial.print(gps.location.lat(), 6);
        Serial.print(",");
        Serial.print(gps.location.lng(), 6);
        Serial.print(",");
        Serial.print(gps.speed.isValid() ? gps.speed.kmph() : 0.0);
        Serial.print(",");
        Serial.print(gps.course.isValid() ? gps.course.deg() : 0.0);
        Serial.print(",");
        Serial.print(gps.altitude.isValid() ? gps.altitude.meters() : 0.0);
        Serial.print(",");
        Serial.println(gps.satellites.isValid() ? gps.satellites.value() : 0);
      } else {
        if (millis() > 5000 && gps.charsProcessed() < 10) {
          Serial.println("GPS_ERR:NO_DATA");
        } else {
          Serial.print("GPS_ERR:NO_LOCK:");
          Serial.println(gps.satellites.isValid() ? gps.satellites.value() : 0);
        }
      }
    }
  }
  
  // 4. Render Current State
  display.clearDisplay();
  
  switch (currentState) {
    case STATE_BOOT:      drawStateBoot(currentMillis); break;
    case STATE_WAITING:   drawStateWaiting(currentMillis); break;
    case STATE_STANDALONE: drawStateStandalone(currentMillis); break;
    case STATE_TRACKING:  drawStateTracking(currentMillis); break;
    case STATE_WARNING:   drawStateWarning(currentMillis); break;
  }
  
  display.display();
}
