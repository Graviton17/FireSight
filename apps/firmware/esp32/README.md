# FireSight ESP32 Firmware

This PlatformIO project targets an ESP32 DevKit using Arduino C++. `include/pins.hpp` contains the report's initial pin map: MQ-2 ADC on GPIO34, DHT11 on GPIO4, buzzer on GPIO18, status LED on GPIO19, and silence button on GPIO27.

Implement network, sensor, actuator, and safety-fallback services as separate C++ modules under `src/`. Keep the `loop()` non-blocking: the device must continue sampling and honouring the silence button while Wi-Fi reconnects.
