#include <Arduino.h>

#define BAUDRATE 115200

// Knob A Pins (X-axis)
#define SWA 7
#define DTA 2
#define CLKA 6

// Knob B Pins (Y-axis)
#define SWB 5
#define DTB 3
#define CLKB 4
#define PWRB 10

int posX = 400;
int posY = 400;
bool pen = false;
bool reset = false;

// Quadrature lookup table to filter out switch bounce
const int8_t KNOB_DIR[] = {
   0, -1,  1,  0,
   1,  0,  0, -1,
  -1,  0,  0,  1,
   0,  1, -1,  0
};

uint8_t stateA = 0;
int8_t subStepA = 0;

uint8_t stateB = 0;
int8_t subStepB = 0;

// State tracking so we only send updates over Serial when something changes
int prevX = -1;
int prevY = -1;
bool prevPen = false;
bool prevReset = false;

unsigned long lastBtnATime = 0;

void setup() {
  Serial.begin(BAUDRATE);

  pinMode(DTA, INPUT_PULLUP);
  pinMode(CLKA, INPUT_PULLUP);
  pinMode(DTB, INPUT_PULLUP);
  pinMode(CLKB, INPUT_PULLUP);

  pinMode(SWA, INPUT_PULLUP);
  pinMode(SWB, INPUT_PULLUP);

  pinMode(PWRB, OUTPUT);
  digitalWrite(PWRB, HIGH);
}

void loop() {
  // --- 1. Read Knob A (X-axis) ---
  stateA = ((stateA << 2) | (digitalRead(CLKA) << 1) | digitalRead(DTA)) & 0x0F;
  subStepA += KNOB_DIR[stateA];

  if (subStepA >= 4) {
    posX = constrain(posX + 10, 0, 790);
    subStepA = 0;
  } else if (subStepA <= -4) {
    posX = constrain(posX - 10, 0, 790);
    subStepA = 0;
  }

  // --- 2. Read Knob B (Y-axis) ---
  stateB = ((stateB << 2) | (digitalRead(CLKB) << 1) | digitalRead(DTB)) & 0x0F;
  subStepB += KNOB_DIR[stateB];

  if (subStepB >= 4) {
    posY = constrain(posY + 10, 0, 790);
    subStepB = 0;
  } else if (subStepB <= -4) {
    posY = constrain(posY - 10, 0, 790);
    subStepB = 0;
  }

  // --- 3. Push Buttons ---
  if (digitalRead(SWA) == LOW && (millis() - lastBtnATime > 250)) {
    pen = !pen;
    lastBtnATime = millis();
  }

  reset = (digitalRead(SWB) == LOW);

  // --- 4. Serial Output (Send ONLY when values change) ---
  if (posX != prevX || posY != prevY || pen != prevPen || reset != prevReset) {
    char buf[64];
    sprintf(buf, "{x = %d, y = %d, LBut = %d, RBut = %d}", posX, posY, pen, reset);
    Serial.println(buf);

    prevX = posX;
    prevY = posY;
    prevPen = pen;
    prevReset = reset;
  }

  // Micro-delay to avoid saturating CPU cycles
  delayMicroseconds(500);
}