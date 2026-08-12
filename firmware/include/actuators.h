#pragma once

#include <Arduino.h>
#include <ESP32Servo.h>

class Actuators {
 public:
  void begin();
  void applySafeState(bool closeValve = true, bool homeFlaps = true);
  void valve(int angle);
  void safeFlap(int angle);
  void rejectFlap(int angle);
  void pump(bool on, uint32_t maximumMs = 0);
  void service();
  bool moveStepper(bool forward, uint32_t steps, uint32_t rate);
  void stopStepper();
  void disableStepper();
  bool pumpOn() const { return pumpOn_; }
  bool stepperEnabled() const { return stepperEnabled_; }

 private:
  Servo valveServo_;
  Servo safeServo_;
  Servo rejectServo_;
  bool pumpOn_ = false;
  bool stepperEnabled_ = false;
  uint32_t pumpDeadline_ = 0;
};

