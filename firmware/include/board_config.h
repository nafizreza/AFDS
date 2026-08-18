#pragma once

#include <Arduino.h>

namespace Board {
constexpr uint8_t SAFE_FLAP_SERVO = 25;
constexpr uint8_t REJECT_FLAP_SERVO = 26;
constexpr uint8_t FEEDER_VALVE_SERVO = 32;  // User-confirmed SG90 pin.
constexpr uint8_t MQ3_ADC = 34;
constexpr uint8_t MQ136_ADC = 35;
constexpr uint8_t DHT22_PIN = 27;
constexpr uint8_t ZE08_RX = 16;
constexpr uint8_t ZE08_TX = 17;
constexpr uint8_t STEPPER_STEP = 18;
constexpr uint8_t STEPPER_DIR = 19;
constexpr uint8_t STEPPER_ENABLE = 23;
constexpr uint8_t PUMP_RELAY = 33;

constexpr bool STEPPER_ENABLE_ACTIVE_LOW = true;
constexpr bool PUMP_ACTIVE_HIGH = true;
constexpr uint32_t SERIAL_BAUD = 115200;
constexpr uint32_t HEARTBEAT_MS = 1000;
constexpr size_t MAX_INPUT_BYTES = 4096;
constexpr char PROTOCOL_VERSION[] = "1.0";
}  // namespace Board

namespace Defaults {
constexpr int VALVE_OPEN_ANGLE = 180;
constexpr int VALVE_CLOSED_ANGLE = 100;
constexpr int SAFE_HOME_ANGLE = 60;
constexpr int SAFE_DROP_ANGLE = 0;
constexpr int UNSAFE_HOME_ANGLE = 60;
constexpr int UNSAFE_DROP_ANGLE = 0;
constexpr uint32_t SERVO_SETTLE_MS = 700;
constexpr uint32_t FLAP_HOLD_MS = 1500;
constexpr uint32_t FLAP_SETTLE_MS = 500;
constexpr uint8_t FLAP_SHAKE_CYCLES = 4;
constexpr int FLAP_SHAKE_OFFSET_DEGREES = 10;
constexpr uint32_t FLAP_SHAKE_STEP_MS = 90;
constexpr uint32_t MAX_STEPPER_STEPS = 50000;
constexpr uint32_t MAX_PUMP_MS = 900000;
}  // namespace Defaults
