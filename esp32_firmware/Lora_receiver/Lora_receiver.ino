#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>
#include <Fonts/FreeSans9pt7b.h>
#include <SPI.h>
#include <LoRa.h>

// --- LoRa Pins ---
#define ss 5
#define rst 14
#define dio0 26

// --- OLED Pins & Settings ---
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1 
#define SCREEN_ADDRESS 0x3C

Adafruit_SH1106G display = Adafruit_SH1106G(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// --- MPU6050 Pins & Settings ---
#define MPU_SDA 32
#define MPU_SCL 33
TwoWire I2CMPU = TwoWire(1);

bool initMPU6050() {
  I2CMPU.beginTransmission(0x68);
  I2CMPU.write(0x75); // WHO_AM_I register
  I2CMPU.endTransmission(false);
  I2CMPU.requestFrom((uint16_t)0x68, (uint8_t)1, true);
  uint8_t whoami = I2CMPU.read();
  
  if (whoami != 0x68 && whoami != 0x70) { // 0x68 for 6050, 0x70 for 6500
    Serial.print("MPU Error! WHO_AM_I = 0x");
    Serial.println(whoami, HEX);
    return false;
  }

  I2CMPU.beginTransmission(0x68);
  I2CMPU.write(0x6B); // Power management
  I2CMPU.write(0x00); // Wake up
  I2CMPU.endTransmission();
  
  // Set accel range to +/- 2g
  I2CMPU.beginTransmission(0x68);
  I2CMPU.write(0x1C);
  I2CMPU.write(0x00); 
  I2CMPU.endTransmission();
  
  // Set gyro range to +/- 250 deg/s
  I2CMPU.beginTransmission(0x68);
  I2CMPU.write(0x1B);
  I2CMPU.write(0x00);
  I2CMPU.endTransmission();
  
  // Set DLPF to ~41Hz
  I2CMPU.beginTransmission(0x68);
  I2CMPU.write(0x1A);
  I2CMPU.write(0x03);
  I2CMPU.endTransmission();
  return true;
}

// --- Status LEDs and Buzzer ---
// Note: LED_RED and BUZZER_PIN moved to avoid LoRa pin conflicts
#define LED_GREEN  27
#define LED_YELLOW 25
#define LED_RED    2
#define BUZZER_PIN 15

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

unsigned long lastLoRaUpdate = 0;
unsigned long alertReceivedTime = 0;
const unsigned long ALERT_DISPLAY_TIME = 3500; 

enum DisplayState { STATE_BOOT, STATE_WAITING, STATE_TRACKING, STATE_WARNING };
DisplayState currentState = STATE_BOOT;

// Smooth Animation Variables
float currentSpeedDisplay = 0.0;
unsigned long bootTime = 0;

void setup() {
  Serial.begin(115200);
  
  Wire.begin(); // default 21 (SDA), 22 (SCL)
  Wire.setClock(400000); // 400kHz Fast I2C for OLED
  
  if(!display.begin(SCREEN_ADDRESS, true)) {
    Serial.println(F("SH1106 allocation failed"));
    for(;;);
  }
  
  I2CMPU.begin(MPU_SDA, MPU_SCL);
  if (!initMPU6050()) {
    display.clearDisplay();
    display.setFont(&FreeSans9pt7b);
    display.setTextColor(SH110X_WHITE);
    display.setCursor(0,20);
    display.print("MPU Fail!");
    display.display();
    while (1);
  }
  Serial.println("MPU6050 initialized via raw I2C.");

  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_YELLOW, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  
  // Setting buzzer to simple HIGH/LOW logic (100% MAX voltage)
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW); // Start silent

  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_YELLOW, LOW);
  digitalWrite(LED_RED, LOW);

  // Setup LoRa
  LoRa.setPins(ss, rst, dio0);
  if (!LoRa.begin(433E6)) {
    display.clearDisplay();
    display.setFont(&FreeSans9pt7b);
    display.setTextColor(SH110X_WHITE);
    display.setCursor(0,20);
    display.print("LoRa Fail!");
    display.display();
    while (1);
  }

  // Enable hardware CRC to drop corrupted noise packets
  LoRa.enableCrc();
  
  myState.vehicle_id = '-';
  myState.speed_x100 = 0;
  myState.accel_x100 = 0;
  myState.event = 0; 
  
  bootTime = millis();
  currentState = STATE_BOOT;
  Serial.println("LoRa V2V Receiver Booting...");
}

// Linear interpolation for smooth animations
float smoothLerp(float a, float b, float t) {
  return a + t * (b - a);
}

void drawStateBoot(unsigned long currentMillis) {
  display.setFont(&FreeSans9pt7b);
  display.setTextColor(SH110X_WHITE);
  display.setCursor(44, 30);
  display.print("V2V");
  
  display.setFont();
  display.setCursor(44, 46);
  display.print("LORA RX");
  
  float progress = constrain((currentMillis - bootTime) / 3000.0, 0.0, 1.0);
  int barW = (int)(progress * 100);
  display.drawRoundRect(14, 56, 100, 6, 2, SH110X_WHITE);
  display.fillRoundRect(14, 56, barW, 6, 2, SH110X_WHITE);
  
  if (progress >= 1.0) {
    currentState = STATE_WAITING;
  }
}

void drawStateWaiting(unsigned long currentMillis) {
  display.setFont(); 
  display.setTextColor(SH110X_WHITE);
  display.setCursor(20, 20);
  display.println(F("Waiting for LoRa..."));
  
  int w = (currentMillis / 15) % 100;
  display.drawRoundRect(14, 40, 100, 6, 3, SH110X_WHITE);
  display.fillRoundRect(14 + w, 40, 10, 6, 3, SH110X_WHITE);
}

void drawStateTracking(unsigned long currentMillis) {
  float targetSpeed = (myState.speed_x100 / 100.0) * 3.6;
  currentSpeedDisplay = smoothLerp(currentSpeedDisplay, targetSpeed, 0.15);
  
  display.setFont();
  display.setTextColor(SH110X_WHITE);
  display.setCursor(0, 0);
  display.print(F("ID: "));
  display.print(myState.vehicle_id);
  display.setCursor(80, 0);
  display.print(F("LORA: OK"));
  display.drawLine(0, 10, 128, 10, SH110X_WHITE);
  
  display.drawBitmap(2, 14, icon_car, 16, 16, SH110X_WHITE);
  
  display.setFont(&FreeSans9pt7b);
  display.setCursor(25, 34);
  int displaySpeed = (int)currentSpeedDisplay;
  display.print(displaySpeed); 
  
  display.setFont();
  display.setCursor(75, 26);
  display.print(F("km/h"));
  
  display.setCursor(0, 54);
  display.print(F("Status: [ NORMAL ]"));
}

void drawStateWarning(unsigned long currentMillis) {
  bool flash = (currentMillis / 150) % 2 == 0;
  
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
  
  if (isSevere) {
    display.fillScreen(flash ? SH110X_WHITE : SH110X_BLACK);
    display.setTextColor(flash ? SH110X_BLACK : SH110X_WHITE);
    
    display.setFont(); 
    display.setTextSize(3); 
    
    if (activeEvent == 4) {
      display.setCursor(10, 15);
      display.print(F("CRASH!"));
    } else if (activeEvent == 5) {
      display.setCursor(10, 15);
      display.print(F("HAZARD"));
    } else if (activeEvent == 8) {
      display.setTextSize(2); 
      display.setCursor(10, 20);
      display.print(F("EMERGENCY"));
    }
    
    display.setTextSize(1); 
    display.setFont();
    display.setCursor(20, 45);
    
    if (isLocal) {
      display.print(F("EVACUATE VEHICLE"));
    } else if (activeEvent == 8) {
      display.setCursor(10, 45); 
      display.print(F("VEHICLE BEHIND"));
    } else {
      display.print(F("CAR "));
      display.print(activeId);
      display.print(F(" AHEAD"));
    }
    
    display.setTextColor(SH110X_WHITE);
    return;
  }
  
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
  
  if (!flash) display.fillRoundRect(0, 52, 128, 12, 3, SH110X_WHITE);
  else display.drawRoundRect(0, 52, 128, 12, 3, SH110X_BLACK);
  
  if (!flash) display.setTextColor(SH110X_BLACK);
  display.setCursor(18, 54);
  display.print(F("HAZARD DETECTED"));
  display.setTextColor(SH110X_WHITE);
}

void loop() {
  unsigned long currentMillis = millis();
  
  // 1. Process incoming LoRa packets
  int packetSize = LoRa.parsePacket();
  if (packetSize == sizeof(VehicleStatePacket)) {
    VehicleStatePacket incoming;
    int bytesRead = LoRa.readBytes((uint8_t*)&incoming, sizeof(incoming));
    if (bytesRead == sizeof(incoming)) {
      // Software Sanity Check: Drop corrupted packets that bypass hardware CRC
      if ((incoming.vehicle_id == 'A' || incoming.vehicle_id == 'B') && incoming.event <= 10) {
        memcpy(&myState, &incoming, sizeof(incoming));
        lastLoRaUpdate = currentMillis;
        
        if (myState.event > 0) {
        memcpy(&receivedAlert, &incoming, sizeof(incoming));
        alertReceivedTime = currentMillis;
        currentState = STATE_WARNING;
      }
      
      Serial.print("LORA RX -> ID: ");
      Serial.print(incoming.vehicle_id);
      Serial.print(" | Event: ");
      Serial.print(incoming.event);
        Serial.print(" | RSSI: ");
        Serial.println(LoRa.packetRssi());
      } else {
        Serial.print("LORA RX: Dropped corrupted packet (ID: ");
        Serial.print(incoming.vehicle_id);
        Serial.println(")");
      }
    }
  }

  // 2. Determine Event for Buzzer/LEDs based on received alert or local state
  uint8_t activeEventBuzzer = myState.event;
  if (currentState == STATE_WARNING && receivedAlert.event != 0) {
    activeEventBuzzer = receivedAlert.event;
  }
  
  // Update Status LEDs & Buzzer
  if (currentState != STATE_BOOT && currentState != STATE_WAITING) {
    if (activeEventBuzzer == 8) { // AMBULANCE PATTERN
      bool flash = (currentMillis / 100) % 2 == 0;
      digitalWrite(LED_RED, flash ? HIGH : LOW);
      digitalWrite(LED_YELLOW, flash ? LOW : HIGH);
      digitalWrite(LED_GREEN, LOW);
      digitalWrite(BUZZER_PIN, HIGH); // Constant HIGH
    } else if (activeEventBuzzer == 4 || activeEventBuzzer == 9) { // CRASH / HARSH_BRAKING
      digitalWrite(LED_RED, HIGH);
      digitalWrite(LED_YELLOW, LOW);
      digitalWrite(LED_GREEN, LOW);
      if ((currentMillis / 50) % 2 == 0) digitalWrite(BUZZER_PIN, HIGH);
      else digitalWrite(BUZZER_PIN, LOW);
    } else if (activeEventBuzzer == 1 || activeEventBuzzer == 5 || activeEventBuzzer == 2) { // OVERSPEED / HAZARD / TRACTN
      digitalWrite(LED_RED, LOW);
      digitalWrite(LED_YELLOW, HIGH);
      digitalWrite(LED_GREEN, LOW);
      if ((currentMillis / 200) % 2 == 0) digitalWrite(BUZZER_PIN, HIGH);
      else digitalWrite(BUZZER_PIN, LOW);
    } else { // NORMAL
      digitalWrite(LED_RED, LOW);
      digitalWrite(LED_YELLOW, LOW);
      digitalWrite(LED_GREEN, HIGH);
      digitalWrite(BUZZER_PIN, LOW);
    }
  } else {
    // Turn off in boot/waiting state
    digitalWrite(LED_RED, LOW);
    digitalWrite(LED_YELLOW, LOW);
    digitalWrite(LED_GREEN, LOW);
    digitalWrite(BUZZER_PIN, LOW);
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
      
      float ax = (rax / 16384.0) * 9.80665;
      float ay = (ray / 16384.0) * 9.80665;
      float az = (raz / 16384.0) * 9.80665;
      
      float gx = (rgx / 131.0) * 0.0174533;
      float gy = (rgy / 131.0) * 0.0174533;
      float gz = (rgz / 131.0) * 0.0174533;
      
      // Calculate Tilt (Roll & Pitch)
      float roll = atan2(ay, sqrt(ax*ax + az*az)) * 180.0 / PI;
      float pitch = atan2(-ax, sqrt(ay*ay + az*az)) * 180.0 / PI;
      
      // Tilt Warning Logic (Rollover Detection)
      if (abs(roll) > 55.0 || abs(pitch) > 55.0) {
        myState.event = 4; // 4 = CRASH / ROLLOVER event
      } else {
        if (myState.event == 4) myState.event = 0; // Clear it if upright
      }
      
      Serial.print("MPU:");
      Serial.print(ax); Serial.print(",");
      Serial.print(ay); Serial.print(",");
      Serial.print(az); Serial.print(",");
      Serial.print(gx); Serial.print(",");
      Serial.print(gy); Serial.print(",");
      Serial.println(gz);
    }
  }

  // 4. State Machine Logic
  if (currentState != STATE_BOOT) {
    bool localSevere = (myState.event == 4 || myState.event == 5 || myState.event == 8);
    
    if (localSevere) {
      currentState = STATE_WARNING;
    } else if (currentMillis - alertReceivedTime < ALERT_DISPLAY_TIME && alertReceivedTime != 0) {
      currentState = STATE_WARNING;
    } else if (currentMillis - lastLoRaUpdate > 5000) {
      // Auto-switch to waiting if no LoRa data for 5 seconds
      currentState = STATE_WAITING;
    } else if (lastLoRaUpdate != 0) {
      currentState = STATE_TRACKING;
    } else {
      currentState = STATE_WAITING;
    }
  }

  // 5. Render Current State (Throttled to ~30 FPS)
  static unsigned long lastDisplayUpdate = 0;
  if (currentMillis - lastDisplayUpdate > 33) {
    lastDisplayUpdate = currentMillis;
    display.clearDisplay();
    
    switch (currentState) {
      case STATE_BOOT:      drawStateBoot(currentMillis); break;
      case STATE_WAITING:   drawStateWaiting(currentMillis); break;
      case STATE_TRACKING:  drawStateTracking(currentMillis); break;
      case STATE_WARNING:   drawStateWarning(currentMillis); break;
    }
    
    display.display();
  }
}