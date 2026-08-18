#include <Arduino.h>
#include <ArduinoJson.h>

#include "actuators.h"
#include "board_config.h"
#include "protocol.h"
#include "sensors.h"

Actuators actuators;
Sensors sensors;

struct SensorStream {
  bool active = false;
  uint32_t intervalMs = 1000;
  uint32_t nextAt = 0;
  uint32_t sequence = 0;
  String messageId;
  String sessionId;
  String cycleId;
} stream;

uint32_t heartbeatAt = 0;

void serviceRuntime() {
  actuators.service();
  const uint32_t now = millis();
  if (static_cast<int32_t>(now - heartbeatAt) >= 0) {
    sendHeartbeat(actuators.pumpOn(), actuators.stepperEnabled(), stream.active);
    heartbeatAt = now + Board::HEARTBEAT_MS;
  }
}

void responsiveDelay(uint32_t durationMs) {
  const uint32_t startedAt = millis();
  while (millis() - startedAt < durationMs) {
    serviceRuntime();
    delay(5);
  }
}

void writeSortingFlaps(bool safeRoute, int selectedAngle, int oppositeAngle) {
  if (safeRoute) {
    actuators.safeFlap(selectedAngle);
    actuators.rejectFlap(oppositeAngle);
  } else {
    actuators.rejectFlap(selectedAngle);
    actuators.safeFlap(oppositeAngle);
  }
}

void oscillateOppositeFlap(bool safeRoute, int dropAngle, int oppositeHomeAngle,
                           int offsetDegrees, uint8_t cycles, uint32_t stepMs) {
  const int oppositeShakeAngle = constrain(oppositeHomeAngle + offsetDegrees, 0, 180);
  for (uint8_t cycle = 0; cycle < cycles; ++cycle) {
    writeSortingFlaps(safeRoute, dropAngle, oppositeShakeAngle);
    responsiveDelay(stepMs);
    writeSortingFlaps(safeRoute, dropAngle, oppositeHomeAngle);
    responsiveDelay(stepMs);
  }
}

int payloadInt(const CommandFrame& frame, const char* key, int fallback) {
  return frame.payload[key].is<int>() ? frame.payload[key].as<int>() : fallback;
}

void runSortingSequence(const CommandFrame& frame, bool safeRoute) {
  const int dropAngle = payloadInt(
      frame, "angle", safeRoute ? Defaults::SAFE_DROP_ANGLE : Defaults::UNSAFE_DROP_ANGLE);
  const int selectedHomeAngle = payloadInt(
      frame, "homeAngle", safeRoute ? Defaults::SAFE_HOME_ANGLE : Defaults::UNSAFE_HOME_ANGLE);
  const int oppositeHomeAngle = payloadInt(
      frame, "oppositeHomeAngle", safeRoute ? Defaults::UNSAFE_HOME_ANGLE : Defaults::SAFE_HOME_ANGLE);
  const int offsetDegrees = constrain(
      payloadInt(frame, "shakeOffsetDegrees", Defaults::FLAP_SHAKE_OFFSET_DEGREES), 1, 45);
  const uint8_t cycles = static_cast<uint8_t>(constrain(
      payloadInt(frame, "shakeCycles", Defaults::FLAP_SHAKE_CYCLES), 1, 10));
  const uint32_t stepMs = static_cast<uint32_t>(constrain(
      payloadInt(frame, "shakeStepMs", Defaults::FLAP_SHAKE_STEP_MS), 20, 1000));

  writeSortingFlaps(safeRoute, dropAngle, oppositeHomeAngle);
  responsiveDelay(payloadInt(frame, "holdMs", Defaults::FLAP_HOLD_MS));
  oscillateOppositeFlap(safeRoute, dropAngle, oppositeHomeAngle, offsetDegrees, cycles, stepMs);
  writeSortingFlaps(safeRoute, selectedHomeAngle, oppositeHomeAngle);
}

void sampleAndSend(const String& messageId, const String& sessionId, const String& cycleId) {
  const SensorReading reading = sensors.read();
  sendSensorData(messageId, sessionId, cycleId, reading.mq3, reading.mq136, reading.ch2o,
                 reading.temperature, reading.humidity, ++stream.sequence,
                 reading.ch2oValid, reading.dhtValid);
}

void completeSimple(const CommandFrame& frame, const char* event, uint32_t settleMs = 0) {
  if (settleMs) delay(settleMs);
  sendEvent(frame, event);
}

void handleCommand(const CommandFrame& frame) {
  const String command = frame.command;
  sendAcknowledgement(frame, true);

  if (command == "GET_STATUS") {
    JsonDocument details;
    JsonObject payload = details.to<JsonObject>();
    payload["pump"] = actuators.pumpOn() ? "ON" : "OFF";
    payload["stepper"] = actuators.stepperEnabled() ? "ENABLED" : "DISABLED";
    payload["sensorStream"] = stream.active ? "ON" : "OFF";
    sendEvent(frame, "GET_STATUS_COMPLETED", payload);
  } else if (command == "INITIALIZE") {
    actuators.applySafeState();
    completeSimple(frame, "INITIALIZED", Defaults::SERVO_SETTLE_MS);
  } else if (command == "SET_SAFE_STATE") {
    actuators.applySafeState(
        frame.payload["closeValve"] | true, frame.payload["homeFlaps"] | true,
        payloadInt(frame, "valveClosedAngle", Defaults::VALVE_CLOSED_ANGLE),
        payloadInt(frame, "safeHomeAngle", Defaults::SAFE_HOME_ANGLE),
        payloadInt(frame, "unsafeHomeAngle", Defaults::UNSAFE_HOME_ANGLE));
    completeSimple(frame, "SAFE_STATE_APPLIED",
                   payloadInt(frame, "settleMs", Defaults::SERVO_SETTLE_MS));
  } else if (command == "VALVE_OPEN" || command == "VALVE_CLOSE") {
    const bool open = command == "VALVE_OPEN";
    actuators.valve(payloadInt(frame, "angle", open ? Defaults::VALVE_OPEN_ANGLE : Defaults::VALVE_CLOSED_ANGLE));
    completeSimple(frame, open ? "VALVE_OPEN_COMPLETED" : "VALVE_CLOSE_COMPLETED",
                   payloadInt(frame, "settleMs", Defaults::SERVO_SETTLE_MS));
  } else if (command == "FEED_ONE") {
    const uint32_t stepsForward = payloadInt(frame, "stepsForward", 1600);
    const uint32_t stepsReverse = payloadInt(frame, "stepsReverse", 1600);
    const uint32_t rate = payloadInt(frame, "stepRate", 600);
    if (!actuators.moveStepper(true, stepsForward, rate, serviceRuntime)) { sendError(frame, "INVALID_MOTION", "Invalid feeder parameters"); return; }
    delay(payloadInt(frame, "settleMs", 450));
    serviceRuntime();
    if (!actuators.moveStepper(false, stepsReverse, rate, serviceRuntime)) { sendError(frame, "INVALID_MOTION", "Invalid reverse parameters"); return; }
    actuators.disableStepper();
    completeSimple(frame, "FEED_COMPLETED");
  } else if (command == "STEPPER_MOVE") {
    const bool forward = String(frame.payload["direction"] | "FORWARD") != "REVERSE";
    if (!actuators.moveStepper(forward, payloadInt(frame, "steps", 0), payloadInt(frame, "stepRate", 600), serviceRuntime)) { sendError(frame, "INVALID_MOTION", "Steps or rate outside safe bounds"); return; }
    actuators.disableStepper();
    completeSimple(frame, "STEPPER_MOVE_COMPLETED");
  } else if (command == "STEPPER_STOP") {
    actuators.stopStepper(); completeSimple(frame, "STEPPER_STOPPED");
  } else if (command == "STEPPER_DISABLE") {
    actuators.disableStepper(); completeSimple(frame, "STEPPER_DISABLED");
  } else if (command == "SAFE_FLAP_TEST") {
    actuators.safeFlap(payloadInt(frame, "angle", Defaults::SAFE_DROP_ANGLE));
    responsiveDelay(payloadInt(frame, "holdMs", Defaults::FLAP_HOLD_MS));
    actuators.safeFlap(payloadInt(frame, "homeAngle", Defaults::SAFE_HOME_ANGLE));
    completeSimple(frame, "SAFE_FLAP_COMPLETED",
                   payloadInt(frame, "settleMs", Defaults::FLAP_SETTLE_MS));
  } else if (command == "UNSAFE_FLAP_TEST") {
    actuators.rejectFlap(payloadInt(frame, "angle", Defaults::UNSAFE_DROP_ANGLE));
    responsiveDelay(payloadInt(frame, "holdMs", Defaults::FLAP_HOLD_MS));
    actuators.rejectFlap(payloadInt(frame, "homeAngle", Defaults::UNSAFE_HOME_ANGLE));
    completeSimple(frame, "UNSAFE_FLAP_COMPLETED",
                   payloadInt(frame, "settleMs", Defaults::FLAP_SETTLE_MS));
  } else if (command == "SORT_SAFE") {
    runSortingSequence(frame, true);
    completeSimple(frame, "SORT_SAFE_COMPLETED",
                   payloadInt(frame, "settleMs", Defaults::FLAP_SETTLE_MS));
  } else if (command == "SORT_UNSAFE") {
    runSortingSequence(frame, false);
    completeSimple(frame, "SORT_UNSAFE_COMPLETED",
                   payloadInt(frame, "settleMs", Defaults::FLAP_SETTLE_MS));
  } else if (command == "SAFE_FLAP_HOME") {
    actuators.safeFlap(payloadInt(frame, "angle", Defaults::SAFE_HOME_ANGLE)); completeSimple(frame, "SAFE_FLAP_HOME_COMPLETED", Defaults::FLAP_SETTLE_MS);
  } else if (command == "UNSAFE_FLAP_HOME") {
    actuators.rejectFlap(payloadInt(frame, "angle", Defaults::UNSAFE_HOME_ANGLE)); completeSimple(frame, "UNSAFE_FLAP_HOME_COMPLETED", Defaults::FLAP_SETTLE_MS);
  } else if (command == "PUMP_ON") {
    actuators.pump(true, payloadInt(frame, "maximumSeconds", 180) * 1000UL); completeSimple(frame, "PUMP_STATUS");
  } else if (command == "PUMP_OFF") {
    actuators.pump(false); completeSimple(frame, "PUMP_STATUS");
  } else if (command == "PURGE_TIMED") {
    const uint32_t maximumSeconds = constrain(payloadInt(frame, "maximumSeconds", 180), 1, 900);
    const uint32_t seconds = constrain(payloadInt(frame, "durationSeconds", 30), 1, maximumSeconds);
    actuators.pump(true, maximumSeconds * 1000UL);
    const uint32_t start = millis();
    while (millis() - start < seconds * 1000UL) { serviceRuntime(); delay(5); }
    actuators.pump(false); completeSimple(frame, "PURGE_COMPLETED");
  } else if (command == "SENSOR_SNAPSHOT") {
    sampleAndSend(frame.messageId, frame.sessionId, frame.cycleId); completeSimple(frame, "SENSOR_SNAPSHOT_COMPLETED");
  } else if (command == "SENSOR_STREAM_START") {
    stream.active = true;
    stream.intervalMs = constrain(payloadInt(frame, "intervalMs", 1000), 50, 30000);
    stream.nextAt = millis(); stream.messageId = frame.messageId; stream.sessionId = frame.sessionId; stream.cycleId = frame.cycleId;
    completeSimple(frame, "SENSOR_STREAM_STARTED");
  } else if (command == "SENSOR_STREAM_STOP") {
    stream.active = false; completeSimple(frame, "SENSOR_STREAM_STOPPED");
  } else {
    sendError(frame, "UNKNOWN_COMMAND", "Command is not supported by this firmware");
  }
}

void setup() {
  Serial.begin(Board::SERIAL_BAUD);
  Serial.setTimeout(20);
  actuators.begin();
  sensors.begin();
  delay(800);
  sendHeartbeat(actuators.pumpOn(), actuators.stepperEnabled(), stream.active);
}

void loop() {
  serviceRuntime();
  JsonDocument document;
  CommandFrame frame;
  if (readCommand(frame, document)) handleCommand(frame);

  const uint32_t now = millis();
  if (stream.active && static_cast<int32_t>(now - stream.nextAt) >= 0) {
    sampleAndSend(stream.messageId, stream.sessionId, stream.cycleId);
    stream.nextAt = now + stream.intervalMs;
  }
}
