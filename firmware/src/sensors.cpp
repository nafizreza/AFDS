#include "sensors.h"

#include "board_config.h"

void Sensors::begin() {
  analogReadResolution(12);
  analogSetPinAttenuation(Board::MQ3_ADC, ADC_11db);
  analogSetPinAttenuation(Board::MQ136_ADC, ADC_11db);
  dht_.begin();
  ze08_.begin(9600, SERIAL_8N1, Board::ZE08_RX, Board::ZE08_TX);
}

SensorReading Sensors::read() {
  SensorReading result;
  result.mq3 = analogReadMilliVolts(Board::MQ3_ADC);
  result.mq136 = analogReadMilliVolts(Board::MQ136_ADC);
  result.temperature = dht_.readTemperature();
  result.humidity = dht_.readHumidity();
  result.dhtValid = isfinite(result.temperature) && isfinite(result.humidity);
  float ch2o = NAN;
  result.ch2oValid = readZe08(ch2o);
  if (result.ch2oValid) lastCh2o_ = ch2o;
  result.ch2o = result.ch2oValid ? ch2o : lastCh2o_;
  result.ch2oValid = isfinite(result.ch2o);
  return result;
}

bool Sensors::readZe08(float& value) {
  // ZE08-CH2O active-upload frame: FF 17 04 ppb-H ppb-L ... checksum.
  while (ze08_.available() >= 9) {
    if (ze08_.read() != 0xFF) continue;
    uint8_t frame[9] = {0xFF};
    const size_t read = ze08_.readBytes(frame + 1, 8);
    if (read != 8 || frame[1] != 0x17 || frame[2] != 0x04) continue;
    uint8_t sum = 0;
    for (int i = 1; i < 8; ++i) sum += frame[i];
    const uint8_t checksum = static_cast<uint8_t>(~sum + 1);
    if (checksum != frame[8]) continue;
    const uint16_t ppb = (static_cast<uint16_t>(frame[4]) << 8) | frame[5];
    value = ppb / 1000.0f;  // ppm reported to backend; calibrate thresholds on site.
    return true;
  }
  return false;
}

