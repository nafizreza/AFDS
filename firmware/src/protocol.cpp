#include "protocol.h"

#include "board_config.h"

namespace {
void baseEnvelope(JsonDocument& doc, const char* type, const String& messageId,
                  const String& sessionId = "", const String& cycleId = "") {
  doc["protocolVersion"] = Board::PROTOCOL_VERSION;
  doc["type"] = type;
  doc["messageId"] = messageId;
  if (sessionId.length()) doc["sessionId"] = sessionId;
  else doc["sessionId"] = nullptr;
  if (cycleId.length()) doc["cycleId"] = cycleId;
  else doc["cycleId"] = nullptr;
  doc["deviceMillis"] = millis();
}

void writeJson(JsonDocument& doc) {
  serializeJson(doc, Serial);
  Serial.write('\n');
}
}  // namespace

bool readCommand(CommandFrame& frame, JsonDocument& document) {
  static String input;
  while (Serial.available()) {
    const char c = static_cast<char>(Serial.read());
    if (c == '\r') continue;
    if (c != '\n') {
      if (input.length() < Board::MAX_INPUT_BYTES) input += c;
      else input = "";
      continue;
    }
    if (!input.length()) continue;
    const DeserializationError error = deserializeJson(document, input);
    input = "";
    if (error || document["type"] != "command" || document["protocolVersion"] != Board::PROTOCOL_VERSION) {
      return false;
    }
    frame.messageId = document["messageId"] | "";
    frame.sessionId = document["sessionId"] | "";
    frame.cycleId = document["cycleId"] | "";
    frame.command = document["command"] | "";
    frame.payload = document["payload"].as<JsonObjectConst>();
    return frame.messageId.length() && frame.command.length();
  }
  return false;
}

void sendAcknowledgement(const CommandFrame& frame, bool accepted, const char* reason) {
  JsonDocument doc;
  baseEnvelope(doc, "acknowledgement", frame.messageId, frame.sessionId, frame.cycleId);
  doc["accepted"] = accepted;
  doc["command"] = frame.command;
  if (reason) doc["reason"] = reason;
  writeJson(doc);
}

void sendEvent(const CommandFrame& frame, const char* eventName, JsonObjectConst payload) {
  JsonDocument doc;
  baseEnvelope(doc, "event", frame.messageId, frame.sessionId, frame.cycleId);
  doc["event"] = eventName;
  if (!payload.isNull()) doc["payload"] = payload;
  writeJson(doc);
}

void sendError(const CommandFrame& frame, const char* code, const char* message) {
  JsonDocument doc;
  baseEnvelope(doc, "error", frame.messageId, frame.sessionId, frame.cycleId);
  doc["code"] = code;
  doc["message"] = message;
  writeJson(doc);
}

void sendHeartbeat(bool pumpOn, bool stepperEnabled, bool sensorStreaming) {
  JsonDocument doc;
  baseEnvelope(doc, "heartbeat", "HEARTBEAT");
  JsonObject payload = doc["payload"].to<JsonObject>();
  payload["pump"] = pumpOn ? "ON" : "OFF";
  payload["stepper"] = stepperEnabled ? "ENABLED" : "DISABLED";
  payload["sensorStream"] = sensorStreaming ? "ON" : "OFF";
  writeJson(doc);
}

void sendSensorData(const String& messageId, const String& sessionId, const String& cycleId,
                    float mq3, float mq136, float ch2o, float temperature, float humidity,
                    uint32_t sequence, bool validCh2o, bool validDht) {
  JsonDocument doc;
  baseEnvelope(doc, "sensor_data", messageId, sessionId, cycleId);
  JsonObject payload = doc["payload"].to<JsonObject>();
  payload["sequence"] = sequence;
  payload["deviceMillis"] = millis();
  payload["mq3"] = mq3;
  payload["mq136"] = mq136;
  payload["ch2o"] = validCh2o ? ch2o : nullptr;
  payload["temperature"] = validDht ? temperature : nullptr;
  payload["humidity"] = validDht ? humidity : nullptr;
  JsonObject quality = payload["quality"].to<JsonObject>();
  quality["ch2oValid"] = validCh2o;
  quality["dhtValid"] = validDht;
  writeJson(doc);
}
