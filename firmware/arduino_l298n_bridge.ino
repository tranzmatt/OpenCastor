/**
 * arduino_l298n_bridge.ino — OpenCastor companion firmware
 *
 * Bridges the OpenCastor ArduinoSerialDriver (JSON line-protocol over USB
 * serial) to an L298N dual H-bridge motor driver.  A single Arduino controls
 * two DC motors and can optionally read an HC-SR04 ultrasonic sensor and
 * actuate a servo.
 *
 * Default wiring (matches config/presets/arduino_l298n.rcan.yaml):
 *   ENA  → Pin 5   (left motor speed, PWM)
 *   IN1  → Pin 6   (left motor dir A)
 *   IN2  → Pin 7   (left motor dir B)
 *   ENB  → Pin 10  (right motor speed, PWM)
 *   IN3  → Pin 8   (right motor dir A)
 *   IN4  → Pin 9   (right motor dir B)
 *   Trig → Pin 12  (HC-SR04 trigger, optional)
 *   Echo → Pin 11  (HC-SR04 echo,    optional)
 *   Servo→ Pin 3   (pan servo signal, optional)
 *
 * Protocol (one JSON object per line, 115200 baud):
 *
 *   Host → Arduino:
 *     {"cmd":"drive","left":150,"right":-100}   // PWM -255..255
 *     {"cmd":"stop"}
 *     {"cmd":"ping"}
 *     {"cmd":"sensor","id":"hcsr04"}
 *     {"cmd":"servo","pin":3,"angle":90}
 *
 *   Arduino → Host:
 *     {"ack":true}
 *     {"sensor":"hcsr04","distance_mm":342}
 *     {"error":"unknown command"}
 *
 * Flash with: Arduino IDE 2.x or arduino-cli
 *   arduino-cli compile --fqbn arduino:avr:uno firmware/arduino_l298n_bridge/
 *   arduino-cli upload  --fqbn arduino:avr:uno -p /dev/ttyACM0 firmware/arduino_l298n_bridge/
 *
 * Dependencies: ArduinoJson v7 (install via Library Manager)
 */

#include <ArduinoJson.h>
#include <Servo.h>

// ── Pin definitions (edit to match your wiring) ──────────────────────────────
const uint8_t PIN_ENA  = 5;    // Left  motor PWM
const uint8_t PIN_IN1  = 6;    // Left  motor dir A
const uint8_t PIN_IN2  = 7;    // Left  motor dir B
const uint8_t PIN_ENB  = 10;   // Right motor PWM
const uint8_t PIN_IN3  = 8;    // Right motor dir A
const uint8_t PIN_IN4  = 9;    // Right motor dir B
const uint8_t PIN_TRIG = 12;   // HC-SR04 trigger
const uint8_t PIN_ECHO = 11;   // HC-SR04 echo
const uint8_t PIN_SRV  = 3;    // Servo signal

// ── Constants ─────────────────────────────────────────────────────────────────
const unsigned long BAUD_RATE      = 115200;
const unsigned long STOP_TIMEOUT_MS = 1000;  // e-stop if no command for 1 s

// ── State ─────────────────────────────────────────────────────────────────────
Servo panServo;
unsigned long lastCmdMs = 0;
bool servoAttached = false;

// ── Forward declarations ───────────────────────────────────────────────────────
void driveMotors(int left, int right);
void stopMotors();
long measureDistanceMM();
void sendAck();
void sendError(const char* msg);

// ─────────────────────────────────────────────────────────────────────────────

void setup() {
    Serial.begin(BAUD_RATE);

    // Motor pins
    pinMode(PIN_ENA, OUTPUT);
    pinMode(PIN_IN1, OUTPUT);
    pinMode(PIN_IN2, OUTPUT);
    pinMode(PIN_ENB, OUTPUT);
    pinMode(PIN_IN3, OUTPUT);
    pinMode(PIN_IN4, OUTPUT);

    // HC-SR04
    pinMode(PIN_TRIG, OUTPUT);
    pinMode(PIN_ECHO, INPUT);
    digitalWrite(PIN_TRIG, LOW);

    stopMotors();
    lastCmdMs = millis();
}

void loop() {
    // ── Watchdog: stop motors if host goes silent ─────────────────────────────
    if (millis() - lastCmdMs > STOP_TIMEOUT_MS) {
        stopMotors();
    }

    // ── Read one line from host ───────────────────────────────────────────────
    if (!Serial.available()) return;

    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() == 0) return;

    lastCmdMs = millis();

    // ── Parse JSON ────────────────────────────────────────────────────────────
    StaticJsonDocument<256> doc;
    DeserializationError err = deserializeJson(doc, line);
    if (err) {
        sendError("json parse error");
        return;
    }

    const char* cmd = doc["cmd"] | "";

    // ── Dispatch ──────────────────────────────────────────────────────────────
    if (strcmp(cmd, "drive") == 0) {
        int left  = doc["left"]  | 0;
        int right = doc["right"] | 0;
        // Clamp to safe range
        left  = constrain(left,  -255, 255);
        right = constrain(right, -255, 255);
        driveMotors(left, right);
        sendAck();

    } else if (strcmp(cmd, "stop") == 0) {
        stopMotors();
        sendAck();

    } else if (strcmp(cmd, "ping") == 0) {
        sendAck();

    } else if (strcmp(cmd, "sensor") == 0) {
        const char* id = doc["id"] | "";
        if (strcmp(id, "hcsr04") == 0) {
            long dist = measureDistanceMM();
            StaticJsonDocument<64> resp;
            resp["sensor"]      = "hcsr04";
            resp["distance_mm"] = dist;
            serializeJson(resp, Serial);
            Serial.print('\n');
        } else {
            sendError("unknown sensor id");
        }

    } else if (strcmp(cmd, "servo") == 0) {
        int pin   = doc["pin"]   | PIN_SRV;
        int angle = doc["angle"] | 90;
        angle = constrain(angle, 0, 180);
        if (!servoAttached) {
            panServo.attach(pin);
            servoAttached = true;
        }
        panServo.write(angle);
        sendAck();

    } else {
        sendError("unknown command");
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Motor helpers
// ─────────────────────────────────────────────────────────────────────────────

void driveMotors(int left, int right) {
    // Left motor
    if (left >= 0) {
        digitalWrite(PIN_IN1, HIGH);
        digitalWrite(PIN_IN2, LOW);
    } else {
        digitalWrite(PIN_IN1, LOW);
        digitalWrite(PIN_IN2, HIGH);
        left = -left;
    }
    analogWrite(PIN_ENA, left);

    // Right motor
    if (right >= 0) {
        digitalWrite(PIN_IN3, HIGH);
        digitalWrite(PIN_IN4, LOW);
    } else {
        digitalWrite(PIN_IN3, LOW);
        digitalWrite(PIN_IN4, HIGH);
        right = -right;
    }
    analogWrite(PIN_ENB, right);
}

void stopMotors() {
    digitalWrite(PIN_IN1, LOW);
    digitalWrite(PIN_IN2, LOW);
    digitalWrite(PIN_IN3, LOW);
    digitalWrite(PIN_IN4, LOW);
    analogWrite(PIN_ENA, 0);
    analogWrite(PIN_ENB, 0);
}

// ─────────────────────────────────────────────────────────────────────────────
// HC-SR04 distance measurement
// ─────────────────────────────────────────────────────────────────────────────

long measureDistanceMM() {
    digitalWrite(PIN_TRIG, LOW);
    delayMicroseconds(2);
    digitalWrite(PIN_TRIG, HIGH);
    delayMicroseconds(10);
    digitalWrite(PIN_TRIG, LOW);

    long duration = pulseIn(PIN_ECHO, HIGH, 30000UL);  // 30 ms timeout (~5 m)
    if (duration == 0) return -1;  // timeout / no echo
    // Speed of sound ~343 m/s → 0.343 mm/µs; round-trip → divide by 2
    return (duration * 343L) / 2000L;
}

// ─────────────────────────────────────────────────────────────────────────────
// Response helpers
// ─────────────────────────────────────────────────────────────────────────────

void sendAck() {
    Serial.println("{\"ack\":true}");
}

void sendError(const char* msg) {
    StaticJsonDocument<128> doc;
    doc["error"] = msg;
    serializeJson(doc, Serial);
    Serial.print('\n');
}
