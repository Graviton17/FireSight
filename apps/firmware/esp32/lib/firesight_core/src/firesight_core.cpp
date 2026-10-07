#include "firesight_core.hpp"

#include <cmath>
#include <cstring>

namespace firesight::core {

namespace {
constexpr float kKelvinOffset = 273.15f;
constexpr float kMinContractC = -40.0f;
constexpr float kMaxContractC = 125.0f;

// Unsigned subtraction keeps these comparisons correct across millis() wrap-around.
bool elapsed(uint32_t now_ms, uint32_t since_ms, uint32_t span_ms) {
  return static_cast<uint32_t>(now_ms - since_ms) >= span_ms;
}
}  // namespace

float ntcResistanceOhm(float node_mv, const NtcParams& params) {
  if (node_mv <= params.rail_margin_mv || node_mv >= params.supply_mv - params.rail_margin_mv) {
    return NAN;
  }
  return params.fixed_ohm * node_mv / (params.supply_mv - node_mv);
}

float ntcTemperatureC(float node_mv, const NtcParams& params) {
  const float resistance = ntcResistanceOhm(node_mv, params);
  if (std::isnan(resistance)) {
    return NAN;
  }
  const float nominal_k = params.nominal_c + kKelvinOffset;
  const float inverse_k =
      1.0f / nominal_k + std::log(resistance / params.nominal_ohm) / params.beta;
  const float celsius = 1.0f / inverse_k - kKelvinOffset;
  if (celsius < kMinContractC || celsius > kMaxContractC) {
    return NAN;
  }
  return celsius;
}

float Ewma::update(float sample) {
  if (!primed_) {
    value_ = sample;
    primed_ = true;
  } else {
    value_ += alpha_ * (sample - value_);
  }
  return value_;
}

void WindowMean::add(float sample) {
  sum_ += sample;
  ++count_;
}

float WindowMean::take(float fallback) {
  if (count_ == 0) {
    return fallback;
  }
  const float mean = static_cast<float>(sum_ / count_);
  sum_ = 0.0;
  count_ = 0;
  return mean;
}

bool Debouncer::update(bool pressed, uint32_t now_ms) {
  if (pressed != raw_) {
    raw_ = pressed;
    changed_at_ms_ = now_ms;
  }
  if (raw_ != stable_ && elapsed(now_ms, changed_at_ms_, settle_ms_)) {
    stable_ = raw_;
    return stable_;
  }
  return false;
}

void Silence::start(uint32_t now_ms) {
  active_ = true;
  started_ms_ = now_ms;
}

bool Silence::active(uint32_t now_ms) const {
  return active_ && !elapsed(now_ms, started_ms_, duration_ms_);
}

void LocalAlarm::onHeartbeat(bool ok, bool server_alarm) {
  if (ok) {
    failures_ = 0;
    last_server_alarm_ = server_alarm;
    // The server has adopted the alarm; from here it drives the buzzer.
    if (server_alarm) {
      reason_ = LocalReason::kNone;
    }
    return;
  }
  if (failures_ < UINT8_MAX) {
    ++failures_;
  }
  // Losing the server must never silence an alarm it had already raised.
  if (standalone() && last_server_alarm_ && reason_ == LocalReason::kNone) {
    reason_ = LocalReason::kServerAlarmKept;
  }
}

void LocalAlarm::update(uint32_t now_ms, float gas_smoothed, float temp_c, bool gas_ready) {
  if (!standalone()) {
    gas_high_ = false;
    heat_high_ = false;
    return;
  }
  if (latched()) {
    return;
  }

  if (gas_ready && gas_smoothed >= config_.gas_extreme_raw) {
    if (!gas_high_) {
      gas_high_ = true;
      gas_since_ms_ = now_ms;
    } else if (elapsed(now_ms, gas_since_ms_, config_.gas_hold_ms)) {
      reason_ = LocalReason::kGasExtreme;
      return;
    }
  } else {
    gas_high_ = false;
  }

  // The thermistor needs no warm-up, so heat is checked even while the MQ-2 warms.
  if (!std::isnan(temp_c) && temp_c >= config_.heat_extreme_c) {
    if (!heat_high_) {
      heat_high_ = true;
      heat_since_ms_ = now_ms;
    } else if (elapsed(now_ms, heat_since_ms_, config_.heat_hold_ms)) {
      reason_ = LocalReason::kHeat;
    }
  } else {
    heat_high_ = false;
  }
}

const char* localReasonName(LocalReason reason) {
  switch (reason) {
    case LocalReason::kGasExtreme:
      return "gas_extreme";
    case LocalReason::kHeat:
      return "heat";
    case LocalReason::kServerAlarmKept:
      return "server_alarm_kept";
    case LocalReason::kNone:
      break;
  }
  return "none";
}

DeviceState parseDeviceState(const char* text) {
  if (text == nullptr) {
    return DeviceState::kUnknown;
  }
  if (std::strcmp(text, "WARMUP") == 0) return DeviceState::kWarmup;
  if (std::strcmp(text, "NORMAL") == 0) return DeviceState::kNormal;
  if (std::strcmp(text, "CHECKING") == 0) return DeviceState::kChecking;
  if (std::strcmp(text, "WARNING") == 0) return DeviceState::kWarning;
  if (std::strcmp(text, "ALARM") == 0) return DeviceState::kAlarm;
  return DeviceState::kUnknown;
}

const char* deviceStateName(DeviceState state) {
  switch (state) {
    case DeviceState::kWarmup:
      return "WARMUP";
    case DeviceState::kNormal:
      return "NORMAL";
    case DeviceState::kChecking:
      return "CHECKING";
    case DeviceState::kWarning:
      return "WARNING";
    case DeviceState::kAlarm:
      return "ALARM";
    case DeviceState::kUnknown:
      break;
  }
  return "UNKNOWN";
}

LedMode ledModeFor(bool warmup_done, bool server_reachable, DeviceState state,
                   bool local_latched) {
  if (local_latched || state == DeviceState::kAlarm) return LedMode::kAlarm;
  if (!server_reachable) return LedMode::kFault;
  if (!warmup_done || state == DeviceState::kWarmup) return LedMode::kWarmup;
  if (state == DeviceState::kChecking || state == DeviceState::kWarning) return LedMode::kChecking;
  return LedMode::kNormal;
}

bool ledLevel(LedMode mode, uint32_t now_ms) {
  switch (mode) {
    case LedMode::kWarmup:  // slow 1 Hz blink
      return (now_ms % 1000) < 500;
    case LedMode::kNormal:  // short heartbeat flash every 2 s
      return (now_ms % 2000) < 100;
    case LedMode::kChecking: {  // double flash every second
      const uint32_t phase = now_ms % 1000;
      return phase < 100 || (phase >= 200 && phase < 300);
    }
    case LedMode::kAlarm:  // fast 5 Hz blink
      return (now_ms % 200) < 100;
    case LedMode::kFault:  // solid: no server
      return true;
  }
  return false;
}

}  // namespace firesight::core
