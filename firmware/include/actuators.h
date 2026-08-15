#pragma once

#include <Arduino.h>
#include <ESP32Servo.h>

class Actuators {
 public:
  using ServiceCallback = void (*)();

  void begin();
  void applySafeState(bool closeValve = true, bool homeFlaps = true,
                      int valveClosedAngle = 100, int safeHomeAngle = 60,
                      int rejectHomeAngle = 60);
  void valve(int angle);
  void safeFlap(int angle);
  void rejectFlap(int angle);
  void pump(bool on, uint32_t maximumMs = 0);
  void service();
  bool moveStepper(bool forward, uint32_t steps, uint32_t rate,
                   ServiceCallback serviceCallback = nullptr);
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
