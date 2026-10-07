#include "sensors.hpp"

#include <Arduino.h>

#include <cmath>

#include "config.hpp"
#include "pins.hpp"

namespace firesight {

namespace {
bool due(uint32_t now_ms, uint32_t last_ms, uint32_t period_ms) {
  return static_cast<uint32_t>(now_ms - last_ms) >= period_ms;
}
}  // namespace

Sensors::Sensors() : mq2_smoothed_(config::kMq2EwmaAlpha), ntc_smoothed_(config::kNtcEwmaAlpha) {
  ntc_params_.fixed_ohm = config::kNtcFixedOhm;
  ntc_params_.nominal_ohm = config::kNtcNominalOhm;
  ntc_params_.beta = config::kNtcBeta;
  ntc_params_.supply_mv = config::kNtcSupplyMv;
}

void Sensors::begin(uint32_t now_ms) {
  boot_ms_ = now_ms;
  analogReadResolution(12);
  // 11 dB attenuation lets the ADC read up to ~3.1 V (the MQ-2 divider tops out at 3.0 V).
  analogSetPinAttenuation(pins::kMq2Adc, ADC_11db);
  analogSetPinAttenuation(pins::kFlameAnalog, ADC_11db);
  analogSetPinAttenuation(pins::kHeatNtc, ADC_11db);
  pinMode(pins::kFlameDigital, INPUT);

  sampleMq2();
  sampleNtc();
  sampleFlame();
  last_mq2_ms_ = last_ntc_ms_ = last_flame_ms_ = now_ms;
}

void Sensors::update(uint32_t now_ms) {
  if (due(now_ms, last_mq2_ms_, config::kMq2SamplePeriodMs)) {
    last_mq2_ms_ = now_ms;
    sampleMq2();
  }
  if (due(now_ms, last_ntc_ms_, config::kNtcSamplePeriodMs)) {
    last_ntc_ms_ = now_ms;
    sampleNtc();
  }
  if (due(now_ms, last_flame_ms_, config::kFlameSamplePeriodMs)) {
    last_flame_ms_ = now_ms;
    sampleFlame();
  }
}

bool Sensors::gasReady(uint32_t now_ms) const {
  return due(now_ms, boot_ms_, config::kMq2WarmupMs);
}

SensorWindow Sensors::takeWindow(uint32_t now_ms) {
  SensorWindow window;
  const float mean = mq2_window_.take(mq2_smoothed_.value());
  window.mq2 = static_cast<uint16_t>(constrain(lroundf(mean), 0L, 4095L));
  window.temp_c = temp_c_;
  window.flame_ir = flame_seen_;
  window.flame_ir_raw = flame_raw_;
  window.warmup_done = gasReady(now_ms);
  flame_seen_ = false;
  return window;
}

void Sensors::sampleMq2() {
  uint32_t sum = 0;
  for (uint8_t i = 0; i < config::kMq2OversampleCount; ++i) {
    sum += analogRead(pins::kMq2Adc);
  }
  const float raw = static_cast<float>(sum) / config::kMq2OversampleCount;
  mq2_smoothed_.update(raw);
  mq2_window_.add(raw);
}

void Sensors::sampleNtc() {
  uint32_t sum_mv = 0;
  for (uint8_t i = 0; i < config::kNtcOversampleCount; ++i) {
    sum_mv += analogReadMilliVolts(pins::kHeatNtc);
  }
  const float node_mv = static_cast<float>(sum_mv) / config::kNtcOversampleCount;
  const float celsius = core::ntcTemperatureC(node_mv, ntc_params_);
  if (std::isnan(celsius)) {
    // Report the fault as null rather than a made-up value (report FR-17).
    ntc_smoothed_.reset();
    temp_c_ = NAN;
    return;
  }
  temp_c_ = ntc_smoothed_.update(celsius);
}

void Sensors::sampleFlame() {
  const bool level_high = digitalRead(pins::kFlameDigital) == HIGH;
  if (level_high != config::kFlameActiveLow) {
    flame_seen_ = true;
  }
  flame_raw_ = static_cast<uint16_t>(analogRead(pins::kFlameAnalog));
}

}  // namespace firesight
