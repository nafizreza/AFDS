#pragma once

#include <ArduinoJson.h>

struct CommandFrame {
  String messageId;
  String sessionId;
  String cycleId;
  String command;
  JsonObjectConst payload;
};

bool readCommand(CommandFrame& frame, JsonDocument& document);
void sendAcknowledgement(const CommandFrame& frame, bool accepted, const char* reason = nullptr);
void sendEvent(const CommandFrame& frame, const char* eventName, JsonObjectConst payload = JsonObjectConst());
void sendError(const CommandFrame& frame, const char* code, const char* message);
void sendHeartbeat(bool pumpOn, bool stepperEnabled, bool sensorStreaming);
void sendSensorData(const String& messageId, const String& sessionId, const String& cycleId,
                    float mq3, float mq136, float ch2o, float temperature, float humidity,
                    uint32_t sequence, bool validCh2o, bool validDht);

