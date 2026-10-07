#pragma once

// Hardware-independent FireSight node logic. Nothing here may include Arduino
// headers, so `pio test -e native` can run it on the development machine.

#include <cstdint>

namespace firesight::core {

// ---------------------------------------------------------------------------
// NTC thermistor (3V3 -> fixed resistor -> ADC node -> NTC -> GND)
// ---------------------------------------------------------------------------

struct NtcParams {
  float fixed_ohm = 10000.0f;
  float nominal_ohm = 10000.0f;
  float nominal_c = 25.0f;
  float beta = 3950.0f;
  float supply_mv = 3300.0f;
  // Readings this close to either rail mean an open or shorted thermistor.
  float rail_margin_mv = 20.0f;
};

// Returns NaN when the node voltage shows an open or shorted thermistor.
float ntcResistanceOhm(float node_mv, const NtcParams& params);

// Returns NaN on a wiring fault or a result outside the contract's -40..125 C.
float ntcTemperatureC(float node_mv, const NtcParams& params);

// ---------------------------------------------------------------------------
// Signal helpers
// ---------------------------------------------------------------------------

class Ewma {
 public:
  explicit Ewma(float alpha) : alpha_(alpha) {}
  float update(float sample);
  void reset() { primed_ = false; }
  bool primed() const { return primed_; }
  float value() const { return value_; }

 private:
  float alpha_;
  float value_ = 0.0f;
  bool primed_ = false;
};

// Accumulates samples between two heartbeats and hands back their mean.
class WindowMean {
 public:
  void add(float sample);
  bool empty() const { return count_ == 0; }
  // Returns the mean and starts a new window. Returns `fallback` when empty.
  float take(float fallback);

 private:
  double sum_ = 0.0;
  uint32_t count_ = 0;
};

// ---------------------------------------------------------------------------
// Push button (active LOW, internal pull-up)
// ---------------------------------------------------------------------------

class Debouncer {
 public:
  explicit Debouncer(uint32_t settle_ms) : settle_ms_(settle_ms) {}
  // `pressed` is the raw level already converted to "is pressed".
  // Returns true exactly once per press, when the press has been stable.
  bool update(bool pressed, uint32_t now_ms);

 private:
  uint32_t settle_ms_;
  bool raw_ = false;
  bool stable_ = false;
  uint32_t changed_at_ms_ = 0;
};

// ---------------------------------------------------------------------------
// Local silence period started by the node button
// ---------------------------------------------------------------------------

class Silence {
 public:
  explicit Silence(uint32_t duration_ms) : duration_ms_(duration_ms) {}
  void start(uint32_t now_ms);
  bool active(uint32_t now_ms) const;
  void clear() { active_ = false; }

 private:
  uint32_t duration_ms_;
  uint32_t started_ms_ = 0;
  bool active_ = false;
};

// ---------------------------------------------------------------------------
// Local fallback alarm (report FR-10): the node alarms on its own when the
// server is unreachable, and keeps an alarm the server had already raised.
// ---------------------------------------------------------------------------

struct FallbackConfig {
  uint8_t fail_limit = 3;           // missed heartbeats before standalone mode
  float gas_extreme_raw = 3200.0f;  // smoothed MQ-2 ADC counts (TUNE)
  uint32_t gas_hold_ms = 15000;     // extreme gas held this long (TUNE)
  float heat_extreme_c = 57.0f;     // NTC temperature (TUNE)
  uint32_t heat_hold_ms = 10000;    // heat held this long (TUNE)
};

enum class LocalReason : uint8_t { kNone, kGasExtreme, kHeat, kServerAlarmKept };

class LocalAlarm {
 public:
  explicit LocalAlarm(const FallbackConfig& config) : config_(config) {}

  // Call after every heartbeat attempt. `server_alarm` is the reply's state == ALARM.
  void onHeartbeat(bool ok, bool server_alarm);

  // Call on every loop pass. `temp_c` may be NaN (sensor fault).
  void update(uint32_t now_ms, float gas_smoothed, float temp_c, bool gas_ready);

  bool standalone() const { return failures_ >= config_.fail_limit; }
  bool latched() const { return reason_ != LocalReason::kNone; }
  LocalReason reason() const { return reason_; }
  uint8_t failures() const { return failures_; }

 private:
  FallbackConfig config_;
  uint8_t failures_ = 0;
  bool last_server_alarm_ = false;
  LocalReason reason_ = LocalReason::kNone;
  bool gas_high_ = false;
  uint32_t gas_since_ms_ = 0;
  bool heat_high_ = false;
  uint32_t heat_since_ms_ = 0;
};

const char* localReasonName(LocalReason reason);

// The node never sounds while silenced; otherwise it obeys the server or its
// own fallback latch, whichever asks for sound.
inline bool buzzerOn(bool server_buzzer, bool local_latched, bool silenced) {
  return (server_buzzer || local_latched) && !silenced;
}

// ---------------------------------------------------------------------------
// Device state reported by the server, and the status LED pattern for it
// ---------------------------------------------------------------------------

enum class DeviceState : uint8_t { kUnknown, kWarmup, kNormal, kChecking, kWarning, kAlarm };

DeviceState parseDeviceState(const char* text);
const char* deviceStateName(DeviceState state);

enum class LedMode : uint8_t { kWarmup, kNormal, kChecking, kAlarm, kFault };

LedMode ledModeFor(bool warmup_done, bool server_reachable, DeviceState state,
                   bool local_latched);

// Returns whether the LED should be lit at `now_ms` for the given mode.
bool ledLevel(LedMode mode, uint32_t now_ms);

}  // namespace firesight::core
