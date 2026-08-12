#pragma once

#include <Arduino.h>
#include <DHT.h>

struct SensorReading {
  float mq3 = NAN;
  float mq136 = NAN;
  float ch2o = NAN;
  float temperature = NAN;
  float humidity = NAN;
  bool ch2oValid = false;
  bool dhtValid = false;
};

class Sensors {
 public:
  void begin();
  SensorReading read();

 private:
  bool readZe08(float& value);
  DHT dht_{27, DHT22};
  HardwareSerial ze08_{2};
  float lastCh2o_ = NAN;
};

