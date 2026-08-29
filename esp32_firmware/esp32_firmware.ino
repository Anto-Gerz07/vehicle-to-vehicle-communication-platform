#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <WiFi.h>
#include <esp_now.h>
#include <TinyGPS++.h>
#include <SD.h>
#include <SPI.h>

#define SD_CS 5

// Removed Adafruit_MPU6050 for MPU6500 raw I2C compatibility
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

void logBlackbox(VehicleStatePacket state);

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
    
    // Log incoming telemetry to blackbox SD
    logBlackbox(incoming);
  }
}

void logBlackbox(VehicleStatePacket state) {
  File logFile = SD.open("/blackbox.csv", FILE_APPEND);
  if (logFile) {
    logFile.print(millis());
    logFile.print(",");
    logFile.print(state.vehicle_id);
    logFile.print(",");
    logFile.print(state.latitude, 6);
    logFile.print(",");
    logFile.print(state.longitude, 6);
    logFile.print(",");
    logFile.print(state.speed_x100 / 100.0);
    logFile.print(",");
    logFile.print(state.accel_x100 / 100.0);
    logFile.print(",");
    logFile.println(state.event);
    logFile.close();
  }
}

void setup() {
  Serial.begin(115200);
  GPS.begin(9600, SERIAL_8N1, RXD2, TXD2);
  
  if (!SD.begin(SD_CS)) {
    Serial.println(F("SD Card Mount Failed"));
  } else {
    Serial.println(F("SD Card Mount Successful"));
    File testFile = SD.open("/blackbox.csv");
    if (!testFile || testFile.size() == 0) {
      if (testFile) testFile.close();
      File logFile = SD.open("/blackbox.csv", FILE_WRITE);
      if (logFile) {
        logFile.println(F("timestamp_ms,vehicle_id,lat,lon,speed,accel,event"));
        logFile.close();
      }
    } else {
      testFile.close();
    }
  }

  if(!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
    Serial.println(F("SSD1306 allocation failed"));
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
  digitalWrite(BUZZER_PIN, LOW);

  digitalWrite(LED_GREEN, LOW);
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
  display.setFont();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(4);
  display.setCursor(28, 16);
  display.print("V2V");
  
  float progress = constrain((currentMillis - bootTime) / 5000.0, 0.0, 1.0);
  if (progress >= 1.0) {
    currentState = STATE_WAITING;
  }
}

void drawStateWaiting(unsigned long currentMillis) {
  display.setFont(); 
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(2);
  display.setCursor(22, 24);
  display.print(F("WAITING"));
}

void drawStateStandalone(unsigned long currentMillis) {
  display.setFont();
  display.setTextColor(SSD1306_WHITE);
  
  int displaySpeed = gps.speed.isValid() ? (int)gps.speed.kmph() : 0;
  if (displaySpeed < 10) {
    display.setTextSize(5);
    display.setCursor(45, 12);
  } else if (displaySpeed < 100) {
    display.setTextSize(5);
    display.setCursor(30, 12);
  } else {
    display.setTextSize(4);
    display.setCursor(20, 16);
  }
  display.print(displaySpeed);
  
  display.setTextSize(1);
  display.setCursor(102, 45);
  display.print(F("km/h"));
  
  // Minimalist SAT status at bottom
  display.setFont();
  display.setCursor(5, 55);
  display.print(F("SATS: "));
  display.print(gps.satellites.isValid() ? gps.satellites.value() : 0);
  
  // Standalone dot indicator top left
  display.fillCircle(4, 4, 3, SSD1306_WHITE);
}

void drawStateTracking(unsigned long currentMillis) {
  float targetSpeed = (myState.speed_x100 / 100.0) * 3.6;
  currentSpeedDisplay = smoothLerp(currentSpeedDisplay, targetSpeed, 0.15);
  
  display.setFont();
  display.setTextColor(SSD1306_WHITE);
  
  int displaySpeed = (int)currentSpeedDisplay;
  if (displaySpeed < 10) {
    display.setTextSize(5);
    display.setCursor(45, 12);
  } else if (displaySpeed < 100) {
    display.setTextSize(5);
    display.setCursor(30, 12);
  } else {
    display.setTextSize(4);
    display.setCursor(20, 16);
  }
  display.print(displaySpeed); 
  
  display.setTextSize(1);
  display.setCursor(102, 45);
  display.print(F("km/h"));
  
  // Minimalist status indicator (dot in top right)
  display.fillCircle(120, 8, 3, SSD1306_WHITE);
}

void drawStateWarning(unsigned long currentMillis) {
  bool flash = (currentMillis / 150) % 2 == 0;
  
  uint8_t activeEvent = 0;
  if (myState.event == 4 || myState.event == 5 || myState.event == 8) {
    activeEvent = myState.event;
  } else {
    activeEvent = receivedAlert.event;
  }
  
  display.fillScreen(flash ? SSD1306_WHITE : SSD1306_BLACK);
  display.setTextColor(flash ? SSD1306_BLACK : SSD1306_WHITE);
  display.setFont();
  
  if (activeEvent == 4) {
    display.setTextSize(3);
    display.setCursor(10, 20);
    display.print(F("CRASH!"));
  } else if (activeEvent == 5 || activeEvent == 2) {
    display.setTextSize(3);
    display.setCursor(10, 20);
    display.print(F("HAZARD"));
  } else if (activeEvent == 8) {
    display.setTextSize(2);
    display.setCursor(10, 24);
    display.print(F("EMERGENCY"));
  } else if (activeEvent == 1) {
    display.setTextSize(2);
    display.setCursor(10, 24);
    display.print(F("OVERSPEED"));
  } else if (activeEvent == 9) {
    display.setTextSize(3);
    display.setCursor(18, 20);
    display.print(F("BRAKE"));
  } else {
    display.setTextSize(3);
    display.setCursor(10, 20);
    display.print(F("ALERT!"));
  }
}

void loop() {
  unsigned long currentMillis = millis();
  

  
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
    // Distinct slow pulsating beep for ambulance
    if ((currentMillis / 400) % 2 == 0) digitalWrite(BUZZER_PIN, HIGH);
    else digitalWrite(BUZZER_PIN, LOW);
  } else if (activeEventBuzzer == 4 || activeEventBuzzer == 9) { // CRASH / HARSH_BRAKING
    digitalWrite(LED_RED, HIGH);
    digitalWrite(LED_YELLOW, LOW);
    digitalWrite(LED_GREEN, LOW);
    // Urgent fast continuous beeping
    if ((currentMillis / 100) % 2 == 0) digitalWrite(BUZZER_PIN, HIGH);
    else digitalWrite(BUZZER_PIN, LOW);
  } else if (activeEventBuzzer == 1) { // OVERSPEED
    digitalWrite(LED_RED, LOW);
    digitalWrite(LED_YELLOW, HIGH);
    digitalWrite(LED_GREEN, LOW);
    // Warning double-beep pattern
    int cycle = currentMillis % 1000;
    if (cycle < 100 || (cycle > 200 && cycle < 300)) digitalWrite(BUZZER_PIN, HIGH);
    else digitalWrite(BUZZER_PIN, LOW);
  } else if (activeEventBuzzer == 5 || activeEventBuzzer == 2) { // HAZARD / TRACTN
    digitalWrite(LED_RED, LOW);
    digitalWrite(LED_YELLOW, HIGH);
    digitalWrite(LED_GREEN, LOW);
    // Slow steady warning beep
    if ((currentMillis / 500) % 2 == 0) digitalWrite(BUZZER_PIN, HIGH);
    else digitalWrite(BUZZER_PIN, LOW);
  } else { // NORMAL
    digitalWrite(LED_RED, LOW);
    digitalWrite(LED_YELLOW, LOW);
    digitalWrite(LED_GREEN, HIGH);
    digitalWrite(BUZZER_PIN, LOW);
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
          
          // Broadcast via ESP-NOW
          esp_now_send(broadcastAddress, (uint8_t *) &myState, sizeof(myState));
          
          // Log local telemetry to blackbox SD
          logBlackbox(myState);
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
  if (currentState == STATE_STANDALONE && currentMillis - lastStandaloneBroadcast > 200) {
    lastStandaloneBroadcast = currentMillis;
    myState.speed_x100 = gps.speed.isValid() ? (int16_t)(gps.speed.mps() * 100) : 0;
    myState.heading = gps.course.isValid() ? (int16_t)gps.course.deg() : 0;
    myState.latitude = gps.location.isValid() ? gps.location.lat() : 0.0;
    myState.longitude = gps.location.isValid() ? gps.location.lng() : 0.0;
    esp_now_send(broadcastAddress, (uint8_t *) &myState, sizeof(myState));
    logBlackbox(myState);
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
