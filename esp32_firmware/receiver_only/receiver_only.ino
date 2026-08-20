// V2V - Reactive Rover with Advanced OLED UI, RSSI Distance & TTC

#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Arduino.h>
#include <WiFi.h>
#include <Wire.h>
#include <esp_now.h>
#include <esp_idf_version.h>
#include <Fonts/FreeSans9pt7b.h>
#include <math.h>

// --- Brownout Bypass Libraries ---
#include "soc/rtc_cntl_reg.h"
#include "soc/soc.h"

// --- OLED Settings ---
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
#define SCREEN_ADDRESS 0x3C
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
bool oledWorking = false;

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

// --- Motor Pins ---
#define IN1 32
#define IN2 33
#define ENA 4
#define IN3 18
#define IN4 19
#define ENB 25

const int PWM_FREQ = 5000;
const int PWM_RES = 8;
const int CH_LEFT = 0;
const int CH_RIGHT = 1;

// --- Buzzer Pin ---
#define BUZZER_PIN 27

// --- Speed Profile & Dynamics ---
const int NORMAL_SPEED = 200;
const int BRAKE_SPEED = 80;
const int YIELD_SPEED = 150; // Speed for hard right turn

int targetSpeed = 0;
float currentSpeed = 0;

const float RAMP_ACCEL = 3.0f;
const float RAMP_DECEL_NORM = 5.0f;
const float RAMP_DECEL_HARSH = 25.0f;
float rampStep = RAMP_ACCEL;

float steerBias = 0.0f;

// --- Distance & TTC Config ---
#define HEADING_THRESHOLD_DEG 45.0f
#define TTC_ALARM_SECONDS     2.0f
#define EMA_ALPHA 0.2f

int lastRssi = -100;
float estimatedDistance = -1.0f;
float smoothedDistance  = -1.0f;
float receiverHeading = 0.0f; // Assume rover heading is 0 relative for now

// --- Data Packet ---
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

VehicleStatePacket latestPacket;
volatile unsigned long lastRecvTime = 0;
uint16_t lastSeq = 0;
uint8_t  droppedPackets = 0;

enum DisplayState { STATE_BOOT, STATE_WAITING, STATE_SCANNING, STATE_WARNING, STATE_CRITICAL_TTC, STATE_LOST };
DisplayState currentState = STATE_BOOT;

// Ambulance Yielding Logic
bool yielding = false;
unsigned long yieldStartTime = 0;
const unsigned long AMBULANCE_PHASE_1_MS = 1000; // Drift right
const unsigned long AMBULANCE_PHASE_2_MS = 2000; // Straighten out (left)

unsigned long bootTime = 0;

// --- Helpers ---
float headingDivergence(float h1, float h2) {
  float diff = fabs(h1 - h2);
  if (diff > 180.0f) diff = 360.0f - diff;
  return diff;
}

float calcTTC(float dist_m, float local_speed_ms, float remote_speed_ms) {
  float closing = local_speed_ms - remote_speed_ms;
  if (closing > 0.1f) return dist_m / closing;
  return 9999.0f;
}

// --- Motor Control Helper Functions ---
#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5, 0, 0)
  #define PWM_WRITE_LEFT(speed)  ledcWrite(ENA, speed)
  #define PWM_WRITE_RIGHT(speed) ledcWrite(ENB, speed)
#else
  #define PWM_WRITE_LEFT(speed)  ledcWrite(CH_LEFT, speed)
  #define PWM_WRITE_RIGHT(speed) ledcWrite(CH_RIGHT, speed)
#endif

void leftForward(int speed) {
  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);
  PWM_WRITE_LEFT(speed);
}
void leftStop() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, LOW);
  PWM_WRITE_LEFT(0);
}
void rightForward(int speed) {
  digitalWrite(IN3, HIGH);
  digitalWrite(IN4, LOW);
  PWM_WRITE_RIGHT(speed);
}
void rightStop() {
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, LOW);
  PWM_WRITE_RIGHT(0);
}

void stopAll() {
  leftStop();
  rightStop();
}

// --- ESP-NOW Callback ---
#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5, 0, 0)
void OnDataRecv(const esp_now_recv_info_t *info, const uint8_t *incomingData, int len) {
  if (len == sizeof(VehicleStatePacket)) {
    memcpy(&latestPacket, incomingData, sizeof(latestPacket));
    lastRecvTime = millis();

    if (lastSeq > 0 && latestPacket.seq > lastSeq + 1) {
      droppedPackets = min((int)droppedPackets + (latestPacket.seq - lastSeq - 1), 255);
    }
    lastSeq = latestPacket.seq;

    if (info->rx_ctrl != NULL) {
      lastRssi = info->rx_ctrl->rssi;
      float rawDist = pow(10.0f, (-45.0f - lastRssi) / (10.0f * 2.5f));
      if (smoothedDistance < 0) smoothedDistance = rawDist;
      smoothedDistance = (1.0f - EMA_ALPHA) * smoothedDistance + EMA_ALPHA * rawDist;
      estimatedDistance = smoothedDistance;
    }
  }
}
#else
void OnDataRecv(const uint8_t *mac, const uint8_t *incomingData, int len) {
  if (len == sizeof(VehicleStatePacket)) {
    memcpy(&latestPacket, incomingData, sizeof(latestPacket));
    lastRecvTime = millis();
    if (lastSeq > 0 && latestPacket.seq > lastSeq + 1) {
      droppedPackets = min((int)droppedPackets + (latestPacket.seq - lastSeq - 1), 255);
    }
    lastSeq = latestPacket.seq;
    estimatedDistance = -1.0f; 
  }
}
#endif

// --- Drawing Functions ---
void drawStateBoot(unsigned long ms) {
  display.setFont(&FreeSans9pt7b);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(16, 25);
  display.print(F("V2V ROVER"));

  display.drawRoundRect(14, 40, 100, 8, 4, SSD1306_WHITE);
  float progress = constrain((ms - bootTime) / 1500.0f, 0.0f, 1.0f);
  display.fillRoundRect(16, 42, (int)(progress * 96), 4, 2, SSD1306_WHITE);
  if (progress >= 1.0f) currentState = STATE_SCANNING;
}

void drawStateWaiting(unsigned long ms) {
  display.setFont();
  display.setCursor(16, 20);
  display.println(F("Waiting for signal..."));
  int w = (ms / 15) % 100;
  display.drawRoundRect(14, 40, 100, 6, 3, SSD1306_WHITE);
  display.fillRoundRect(14 + w, 40, 10, 6, 3, SSD1306_WHITE);
}

void drawStateLost() {
  display.drawBitmap(56, 10, icon_warning, 16, 16, SSD1306_WHITE);
  display.setFont();
  display.setCursor(30, 35);
  display.println(F("SIGNAL LOST"));
  display.drawRoundRect(14, 50, 100, 6, 3, SSD1306_WHITE);
}

void drawStateScanning(unsigned long ms) {
  display.setFont();
  display.setCursor(0, 0);

  if (droppedPackets > 3) display.print(F("NET: WEAK [!]"));
  else display.print(F("NETWORK: ACTIVE"));
  display.drawLine(0, 10, 128, 10, SSD1306_WHITE);

  display.drawBitmap(2, 14, icon_car, 16, 16, SSD1306_WHITE);

  display.setFont(&FreeSans9pt7b);
  display.setCursor(25, 28);
  display.print(F("SCANNING"));

  display.setFont();
  display.setCursor(25, 38);
  if (latestPacket.event > 0 && estimatedDistance > 30.0f) display.print(F("Threat: FAR"));
  else display.print(F("Clear"));

  int radius = (ms / 20) % 25;
  display.drawCircle(105, 30, radius, SSD1306_WHITE);
  if (radius > 12) display.drawCircle(105, 30, radius - 12, SSD1306_WHITE);

  display.setCursor(0, 56);
  if (estimatedDistance >= 0) {
    display.print(F("~"));
    display.print((int)estimatedDistance);
    display.print(F("m "));
    display.print(lastRssi);
    display.print(F("dBm"));
  } else {
    display.print(F("[ SECURE ]"));
  }
}

void drawStateWarning(unsigned long ms) {
  bool flash = (ms / 150) % 2 == 0;

  if (flash) {
    display.fillScreen(SSD1306_WHITE);
    display.setTextColor(SSD1306_BLACK);
  } else {
    display.setTextColor(SSD1306_WHITE);
  }

  display.setFont(&FreeSans9pt7b);
  display.setCursor(26, 18);
  if (latestPacket.event == 8) {
    display.print(F("SIREN!"));
    if (!flash) display.drawBitmap(5, 5, icon_siren, 16, 16, SSD1306_WHITE);
  } else {
    display.print(F("WARNING!"));
    if (!flash) display.drawBitmap(5, 5, icon_warning, 16, 16, SSD1306_WHITE);
  }

  display.setFont();
  display.setCursor(0, 26);
  display.print(F("Car "));
  display.print(latestPacket.vehicle_id);
  if (estimatedDistance >= 0) {
    display.print(F(" ~")); display.print((int)estimatedDistance); display.print(F("m"));
  }

  if (flash) display.drawLine(0, 36, 128, 36, SSD1306_BLACK);
  else       display.drawLine(0, 36, 128, 36, SSD1306_WHITE);

  display.setCursor(0, 42);
  if      (latestPacket.event == 2) display.print(F(">>> HARD BRAKING"));
  else if (latestPacket.event == 4) display.print(F(">>> CRASH ALERT!"));
  else if (latestPacket.event == 8) display.print(F(">>> YIELD NOW!"));

  if (!flash) display.fillRoundRect(0, 52, 128, 12, 3, SSD1306_WHITE);
  else        display.drawRoundRect(0, 52, 128, 12, 3, SSD1306_BLACK);

  if (!flash) display.setTextColor(SSD1306_BLACK);
  display.setCursor(12, 54);
  display.print(F("HAZARD DETECTED"));
  display.setTextColor(SSD1306_WHITE);
}

void drawStateCriticalTTC(unsigned long ms) {
  bool flash = (ms / 80) % 2 == 0;
  display.fillScreen(flash ? SSD1306_WHITE : SSD1306_BLACK);
  display.setTextColor(flash ? SSD1306_BLACK : SSD1306_WHITE);

  display.setFont(&FreeSans9pt7b);
  display.setCursor(10, 20);
  display.print(F("COLLISION!"));

  display.setFont();
  display.setCursor(10, 30);
  display.print(F("TTC < 2s — BRAKE NOW!"));

  if (estimatedDistance >= 0) {
    display.setCursor(10, 45);
    display.print(F("Dist: ~")); display.print((int)estimatedDistance); display.print(F("m"));
  }
}

// --- Main Setup ---
void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

  Serial.begin(115200);
  Wire.begin(21, 22);

  if (display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
    oledWorking = true;
  }

  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);

#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5, 0, 0)
  ledcAttach(ENA, PWM_FREQ, PWM_RES);
  ledcAttach(ENB, PWM_FREQ, PWM_RES);
#else
  ledcSetup(CH_LEFT, PWM_FREQ, PWM_RES);
  ledcAttachPin(ENA, CH_LEFT);
  ledcSetup(CH_RIGHT, PWM_FREQ, PWM_RES);
  ledcAttachPin(ENB, CH_RIGHT);
#endif
  stopAll();

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);

  if (esp_now_init() != ESP_OK) {
    if (oledWorking) {
      display.clearDisplay();
      display.setFont(&FreeSans9pt7b);
      display.setCursor(0, 20);
      display.print("ESP-NOW Fail");
      display.display();
    }
    return;
  }

  esp_now_register_recv_cb(OnDataRecv);
  bootTime = millis();
  currentState = STATE_BOOT;
}

// --- Logic loops ---
void updateRoverDynamics(unsigned long ms) {
  // 1. Process State Machine into Motor Target Speed & Steering
  if (currentState == STATE_BOOT) {
    yielding = false;
    targetSpeed = 0;
    rampStep = RAMP_DECEL_HARSH;
    steerBias = 0.0f;
  } else if (currentState == STATE_CRITICAL_TTC || (currentState == STATE_WARNING && latestPacket.event == 4)) {
    // Critical or Crash
    yielding = false;
    targetSpeed = 0;
    currentSpeed = 0.0f; // hard instant stop
    rampStep = RAMP_DECEL_HARSH;
    steerBias = 0.0f;
  } else if (currentState == STATE_WARNING && latestPacket.event == 2) {
    // Harsh Brake
    yielding = false;
    targetSpeed = 0;
    rampStep = RAMP_DECEL_HARSH;
    steerBias = 0.0f;
  } else if (currentState == STATE_WARNING && latestPacket.event == 8) {
    // Ambulance
    if (!yielding) {
      yielding = true;
      yieldStartTime = ms;
    }
    if (ms - yieldStartTime < AMBULANCE_PHASE_1_MS) {
      // Phase 1: Drift right into the next lane
      targetSpeed = YIELD_SPEED;
      rampStep = RAMP_ACCEL;
      steerBias = 0.6f; 
    } else if (ms - yieldStartTime < AMBULANCE_PHASE_2_MS) {
      // Phase 2: Straighten out (drift left)
      targetSpeed = YIELD_SPEED;
      rampStep = RAMP_ACCEL;
      steerBias = -0.6f; 
    } else {
      // Phase 3: Stop in the new lane and yield
      targetSpeed = 0;
      rampStep = RAMP_DECEL_NORM;
      steerBias = 0.0f;
    }
  } else {
    // SCANNING (Normal Driving)
    yielding = false;
    targetSpeed = NORMAL_SPEED;
    rampStep = RAMP_ACCEL;
    steerBias = 0.0f;
  }

  // 2. Apply Speed Ramping
  if (currentSpeed < targetSpeed) {
    currentSpeed = min((float)targetSpeed, currentSpeed + rampStep);
  } else if (currentSpeed > targetSpeed) {
    currentSpeed = max((float)targetSpeed, currentSpeed - rampStep);
  }

  // 3. Apply Motors
  int spd = round(currentSpeed);
  if (spd <= 0) {
    stopAll();
  } else {
    int leftSpd = constrain((int)(spd * (1.0f + steerBias)), 0, 255);
    int rightSpd = constrain((int)(spd * (1.0f - steerBias)), 0, 255);
    
    // For hard right turn (steerBias = 1.0f), rightSpd is 0, leftSpd is clamped to 255
    // But since steerBias affects both, if speed is 150, left is 255 and right is 0
    leftForward(leftSpd);
    rightForward(rightSpd);
  }

  // 4. Update Buzzer
  if (currentState == STATE_WARNING || currentState == STATE_CRITICAL_TTC) {
    if (latestPacket.event == 8) { // Ambulance
      unsigned long phase = ms % 1200;
      bool on = (phase < 300) || (phase >= 450 && phase < 750);
      digitalWrite(BUZZER_PIN, on ? HIGH : LOW);
    } else if (latestPacket.event == 4 || currentState == STATE_CRITICAL_TTC) { // Crash / Critical
      unsigned long phase = ms % 200;
      digitalWrite(BUZZER_PIN, phase < 100 ? HIGH : LOW);
    } else if (latestPacket.event == 2) { // Harsh Brake
      unsigned long phase = ms % 400;
      bool on = (phase < 80) || (phase >= 140 && phase < 220);
      digitalWrite(BUZZER_PIN, on ? HIGH : LOW);
    } else { // Normal Brake
      unsigned long phase = ms % 800;
      digitalWrite(BUZZER_PIN, phase < 150 ? HIGH : LOW);
    }
  } else {
    digitalWrite(BUZZER_PIN, LOW);
  }
}

// --- Main Loop ---
void loop() {
  unsigned long ms = millis();

  // Evaluate Network/Safety State
  if (currentState != STATE_BOOT) {
    if (lastRecvTime != 0 && ms - lastRecvTime > 5000) {
      currentState = STATE_SCANNING;
    } else if (lastRecvTime != 0) {
      float remoteSpeed_ms = latestPacket.speed_x100 / 100.0f;
      float remoteHeading  = (float)latestPacket.heading;
      float adaptiveThreshold = max(30.0f, remoteSpeed_ms * 3.6f * 1.5f);
      
      float hdiv = headingDivergence(receiverHeading, remoteHeading);
      bool sameDirection = (hdiv <= HEADING_THRESHOLD_DEG);

      float ttc = 9999.0f;
      if (sameDirection && estimatedDistance >= 0) {
        // Assume receiver speed is proportional to current PWM for TTC if needed, or 0
        float mySpeed_ms = (currentSpeed / 255.0f) * 4.0f; // Roughly max 4m/s
        ttc = calcTTC(estimatedDistance, mySpeed_ms, remoteSpeed_ms); 
      }

      if (sameDirection && ttc < TTC_ALARM_SECONDS) {
        currentState = STATE_CRITICAL_TTC;
      } else if (latestPacket.event > 1 && sameDirection) {
        // Threat detected (ignoring overspeed = 1)
        if (estimatedDistance >= 0 && estimatedDistance > adaptiveThreshold) {
          currentState = STATE_SCANNING; // Too far
        } else {
          currentState = STATE_WARNING;
        }
      } else {
        currentState = STATE_SCANNING;
      }
    } else {
      currentState = STATE_SCANNING;
    }
  }

  // Update hardware based on state
  updateRoverDynamics(ms);

  // Update OLED (~25fps)
  static unsigned long lastDisplayUpdate = 0;
  if (oledWorking && (ms - lastDisplayUpdate >= 40)) {
    lastDisplayUpdate = ms;
    display.clearDisplay();

    switch (currentState) {
      case STATE_BOOT:         drawStateBoot(ms);         break;
      case STATE_WAITING:      drawStateWaiting(ms);      break;
      case STATE_LOST:         drawStateLost();           break;
      case STATE_SCANNING:     drawStateScanning(ms);     break;
      case STATE_WARNING:      drawStateWarning(ms);      break;
      case STATE_CRITICAL_TTC: drawStateCriticalTTC(ms);  break;
    }
    
    display.display();
  }

  delay(1); // Prevent watchdog
}