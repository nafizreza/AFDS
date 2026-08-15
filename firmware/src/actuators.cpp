#include "actuators.h"

#include "board_config.h"

namespace {
void setEnable(bool enabled) {
  digitalWrite(Board::STEPPER_ENABLE,
               Board::STEPPER_ENABLE_ACTIVE_LOW ? !enabled : enabled);
}
}  // namespace

void Actuators::begin() {
  pinMode(Board::STEPPER_STEP, OUTPUT);
  pinMode(Board::STEPPER_DIR, OUTPUT);
  pinMode(Board::STEPPER_ENABLE, OUTPUT);
  pinMode(Board::PUMP_RELAY, OUTPUT);
  digitalWrite(Board::STEPPER_STEP, LOW);
  setEnable(false);
  digitalWrite(Board::PUMP_RELAY, Board::PUMP_ACTIVE_HIGH ? LOW : HIGH);
  valveServo_.setPeriodHertz(50);
  safeServo_.setPeriodHertz(50);
  rejectServo_.setPeriodHertz(50);
  valveServo_.attach(Board::FEEDER_VALVE_SERVO, 500, 2400);
  safeServo_.attach(Board::SAFE_FLAP_SERVO, 500, 2400);
  rejectServo_.attach(Board::REJECT_FLAP_SERVO, 500, 2400);
  applySafeState();
}

void Actuators::applySafeState(bool closeValve, bool homeFlaps,
                               int valveClosedAngle, int safeHomeAngle,
                               int rejectHomeAngle) {
  pump(false);
  stopStepper();
  disableStepper();
  if (closeValve) valve(valveClosedAngle);
  if (homeFlaps) {
    safeFlap(safeHomeAngle);
    rejectFlap(rejectHomeAngle);
  }
}

void Actuators::valve(int angle) { valveServo_.write(constrain(angle, 0, 180)); }
void Actuators::safeFlap(int angle) { safeServo_.write(constrain(angle, 0, 180)); }
void Actuators::rejectFlap(int angle) { rejectServo_.write(constrain(angle, 0, 180)); }

void Actuators::pump(bool on, uint32_t maximumMs) {
  pumpOn_ = on;
  digitalWrite(Board::PUMP_RELAY, Board::PUMP_ACTIVE_HIGH ? on : !on);
  pumpDeadline_ = on && maximumMs ? millis() + min(maximumMs, Defaults::MAX_PUMP_MS) : 0;
}

void Actuators::service() {
  if (pumpOn_ && pumpDeadline_ && static_cast<int32_t>(millis() - pumpDeadline_) >= 0) pump(false);
}

bool Actuators::moveStepper(bool forward, uint32_t steps, uint32_t rate,
                            ServiceCallback serviceCallback) {
  if (!steps || steps > Defaults::MAX_STEPPER_STEPS || rate < 10 || rate > 5000) return false;
  digitalWrite(Board::STEPPER_DIR, forward ? HIGH : LOW);
  setEnable(true);
  stepperEnabled_ = true;
  const uint32_t halfPeriodUs = 500000UL / rate;
  for (uint32_t i = 0; i < steps; ++i) {
    digitalWrite(Board::STEPPER_STEP, HIGH);
    delayMicroseconds(halfPeriodUs);
    digitalWrite(Board::STEPPER_STEP, LOW);
    delayMicroseconds(halfPeriodUs);
    service();
    if (serviceCallback) serviceCallback();
  }
  return true;
}

void Actuators::stopStepper() { digitalWrite(Board::STEPPER_STEP, LOW); }
void Actuators::disableStepper() { setEnable(false); stepperEnabled_ = false; }
