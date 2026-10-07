#pragma once

#include <cmath>
#include <cstdint>

#include "firesight_core.hpp"

namespace firesight {

// One heartbeat's worth of readings.
struct SensorWindow {
  uint16_t mq2 = 0;          // mean raw ADC counts since the last window
  float temp_c = NAN;        // NTC temperature, NaN on a wiring fault
  bool flame_ir = false;     // flame DO seen active at any point in the window
  uint16_t flame_ir_raw = 0; // latest flame AO reading
  bool warmup_done = false;
};

// Samples every sensor without blocking. Call update() on every loop pass.
class Sensors {
 public:
  Sensors();
  void begin(uint32_t now_ms);
  void update(uint32_t now_ms);

  // Hands back the readings collected since the previous call and starts a new window.
  SensorWindow takeWindow(uint32_t now_ms);

  float gasSmoothed() const { return mq2_smoothed_.value(); }
  bool gasReady(uint32_t now_ms) const;
  float tempC() const { return temp_c_; }

 private:
  void sampleMq2();
  void sampleNtc();
  void sampleFlame();

  core::NtcParams ntc_params_;
  core::Ewma mq2_smoothed_;
  core::Ewma ntc_smoothed_;
  core::WindowMean mq2_window_;
  float temp_c_ = NAN;
  bool flame_seen_ = false;
  uint16_t flame_raw_ = 0;
  uint32_t boot_ms_ = 0;
  uint32_t last_mq2_ms_ = 0;
  uint32_t last_ntc_ms_ = 0;
  uint32_t last_flame_ms_ = 0;
};

}  // namespace firesight
