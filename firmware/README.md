# ESP32 firmware

This PlatformIO project is the hardware endpoint for AFDS protocol `1.0`. It controls the confirmed SG90 inlet valve on GPIO 32, two flap servos, the DRV8825 feeder, pump relay, MQ sensors, DHT22, and ZE08-CH2O UART sensor.

Before powering actuators, verify relay polarity, common ground, external servo power, DRV8825 current limit, and mechanical clearance. Flash with `pio run --target upload`, then set `AFDS_SERIAL_PORT` in the root `.env` file.

The firmware applies a safe startup state: pump off, stepper disabled, inlet closed, and both flaps home. GPIO assignments in `include/board_config.h` must match `config/hardware_pins.json`.

