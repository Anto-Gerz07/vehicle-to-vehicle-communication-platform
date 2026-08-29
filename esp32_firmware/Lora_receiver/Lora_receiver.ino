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
  
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

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
  display.setFont(); // Use default font for perfect scaling
  display.setTextColor(SH110X_WHITE);
  display.setTextSize(4);
  display.setCursor(28, 16);
  display.print("V2V");
  
  float progress = constrain((currentMillis - bootTime) / 3000.0, 0.0, 1.0);
  if (progress >= 1.0) {
    currentState = STATE_WAITING;
  }
}

void drawStateWaiting(unsigned long currentMillis) {
  display.setFont(); 
  display.setTextColor(SH110X_WHITE);
  display.setTextSize(2);
  display.setCursor(22, 24);
  display.print(F("WAITING"));
}

void drawStateTracking(unsigned long currentMillis) {
  float targetSpeed = (myState.speed_x100 / 100.0) * 3.6;
  currentSpeedDisplay = smoothLerp(currentSpeedDisplay, targetSpeed, 0.15);
  
  display.setFont();
  display.setTextColor(SH110X_WHITE);
  
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
  display.fillCircle(120, 8, 3, SH110X_WHITE);
}

void drawStateWarning(unsigned long currentMillis) {
  bool flash = (currentMillis / 150) % 2 == 0;
  
  uint8_t activeEvent = 0;
  if (myState.event == 4 || myState.event == 5 || myState.event == 8) {
    activeEvent = myState.event;
  } else {
    activeEvent = receivedAlert.event;
  }
  
  display.fillScreen(flash ? SH110X_WHITE : SH110X_BLACK);
  display.setTextColor(flash ? SH110X_BLACK : SH110X_WHITE);
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