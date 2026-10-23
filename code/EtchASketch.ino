#include <Arduino.h>

#define BAUDRATE 115200

// Knob A (X-axis)
#define SWA 7
#define DTA 2
#define CLKA 6

// Knob B (Y-axis)
#define SWB 5
#define DTB 3
#define CLKB 4
#define PWRB 10

// Must match main.py:  MAX_X = CANVAS_SIZE - RES_SIZE
//                      MAX_Y = CANVAS_SIZE + DOCK_H - RES_SIZE
#define MAX_X 795
#define MAX_Y 895
#define STEP 10

// Resend the current state this often even if nothing changed, so the
// laptop can always sync, even if it missed the first packet.
#define HEARTBEAT_MS 500

int posX = 400;
int posY = 400;

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

// Debounced push buttons. "held" is sent raw; Python detects the presses.
struct Button {
  uint8_t pin;
  bool stable;
  bool lastRaw;
  unsigned long rawChangedMs;
};
Button btnX = {SWA, false, false, 0};  // X push: pen/eraser up/down
Button btnY = {SWB, false, false, 0};  // Y push: click dock button

int prevX = -1;
int prevY = -1;
bool prevXHeld = false;
bool prevYHeld = false;
unsigned long lastSendMs = 0;

bool updateButton(Button &b) {
  bool raw = (digitalRead(b.pin) == LOW);
  if (raw != b.lastRaw) {
    b.lastRaw = raw;
    b.rawChangedMs = millis();
  }
  if (millis() - b.rawChangedMs >= 20) {  // stable for 20 ms
    b.stable = b.lastRaw;
  }
  return b.stable;
}

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
  // --- 1. Knob A (X) ---
  stateA = ((stateA << 2) | (digitalRead(CLKA) << 1) | digitalRead(DTA)) & 0x0F;
  subStepA += KNOB_DIR[stateA];
  if (subStepA >= 4) {
    posX = constrain(posX + STEP, 0, MAX_X);
    subStepA = 0;
  } else if (subStepA <= -4) {
    posX = constrain(posX - STEP, 0, MAX_X);
    subStepA = 0;
  }

  // --- 2. Knob B (Y) ---
  stateB = ((stateB << 2) | (digitalRead(CLKB) << 1) | digitalRead(DTB)) & 0x0F;
  subStepB += KNOB_DIR[stateB];
  if (subStepB >= 4) {
    posY = constrain(posY + STEP, 0, MAX_Y);
    subStepB = 0;
  } else if (subStepB <= -4) {
    posY = constrain(posY - STEP, 0, MAX_Y);
    subStepB = 0;
  }

  // --- 3. Push buttons (raw held state, debounced) ---
  bool xHeld = updateButton(btnX);
  bool yHeld = updateButton(btnY);

  // --- 4. Serial output (on change, plus a heartbeat) ---
  bool changed = (posX != prevX || posY != prevY ||
                  xHeld != prevXHeld || yHeld != prevYHeld);
  if (changed || millis() - lastSendMs >= HEARTBEAT_MS) {
    char buf[64];
    sprintf(buf, "{x = %d, y = %d, LBut = %d, RBut = %d}", posX, posY, xHeld, yHeld);
    Serial.println(buf);

    prevX = posX;
    prevY = posY;
    prevXHeld = xHeld;
    prevYHeld = yHeld;
    lastSendMs = millis();
  }

  delayMicroseconds(500);
}
