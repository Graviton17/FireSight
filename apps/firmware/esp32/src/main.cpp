#include <Arduino.h>
#include <esp_system.h>
#include <esp_timer.h>

#include "config.hpp"
#include "firesight_core.hpp"
#include "heartbeat_client.hpp"
#include "pins.hpp"
#include "sensors.hpp"

namespace {

using firesight::core::DeviceState;

firesight::core::FallbackConfig fallbackConfig() {
  firesight::core::FallbackConfig config;
  config.fail_limit = firesight::config::kFallbackFailLimit;
  config.gas_extreme_raw = firesight::config::kFallbackGasExtremeRaw;
  config.gas_hold_ms = firesight::config::kFallbackGasHoldMs;
  config.heat_extreme_c = firesight::config::kFallbackHeatExtremeC;
  config.heat_hold_ms = firesight::config::kFallbackHeatHoldMs;
  return config;
}

firesight::Sensors sensors;
firesight::HeartbeatClient heartbeat;
firesight::core::LocalAlarm local_alarm(fallbackConfig());
firesight::core::Debouncer silence_button(firesight::config::kButtonSettleMs);
firesight::core::Silence silence(firesight::config::kSilenceMs);

bool server_buzzer = false;
DeviceState server_state = DeviceState::kUnknown;
bool server_seen = false;
bool buzzer_active = false;
uint32_t last_heartbeat_ms = 0;

void writeBuzzer(bool on) {
  const bool level = on == firesight::config::kBuzzerActiveHigh;
  digitalWrite(firesight::pins::kBuzzer, level ? HIGH : LOW);
}

uint32_t uptimeSeconds() { return static_cast<uint32_t>(esp_timer_get_time() / 1000000LL); }

void handleHeartbeatResult() {
  firesight::HeartbeatResult result;
  if (!heartbeat.takeResult(result)) {
    return;
  }
  const bool was_standalone = local_alarm.standalone();
  local_alarm.onHeartbeat(result.ok, result.ok && result.state == DeviceState::kAlarm);

  if (result.ok) {
    server_seen = true;
    server_buzzer = result.buzzer;
    server_state = result.state;
    if (was_standalone) {
      Serial.println("[net] server reachable again");
    }
  } else if (local_alarm.standalone()) {
    // A few missed replies keep the last command; standalone mode drops it, and the
    // local fallback (which keeps any server alarm) decides instead.
    server_buzzer = false;
    server_state = DeviceState::kUnknown;
    if (!was_standalone) {
      Serial.println("[net] server unreachable: standalone mode");
    }
  }

  Serial.printf("[hb] code=%d ok=%d state=%s buzzer=%d local=%s fails=%u\n", result.http_code,
                result.ok, firesight::core::deviceStateName(server_state), server_buzzer,
                firesight::core::localReasonName(local_alarm.reason()), local_alarm.failures());
}

void sendHeartbeatIfDue(uint32_t now) {
  if (static_cast<uint32_t>(now - last_heartbeat_ms) < firesight::config::kHeartbeatPeriodMs) {
    return;
  }
  last_heartbeat_ms = now;

  firesight::HeartbeatPayload payload;
  payload.sensors = sensors.takeWindow(now);
  payload.local_alarm = local_alarm.latched();
  payload.silenced = silence.active(now);
  payload.uptime_s = uptimeSeconds();
  heartbeat.send(payload);

  Serial.printf("[sense] mq2=%u smooth=%.0f temp=%.1f flame=%d flame_raw=%u warm=%d\n",
                payload.sensors.mq2, sensors.gasSmoothed(), payload.sensors.temp_c,
                payload.sensors.flame_ir, payload.sensors.flame_ir_raw,
                payload.sensors.warmup_done);
}

}  // namespace

void setup() {
  Serial.begin(firesight::config::kSerialBaud);
  pinMode(firesight::pins::kBuzzer, OUTPUT);
  writeBuzzer(false);
  pinMode(firesight::pins::kStatusLed, OUTPUT);
  pinMode(firesight::pins::kSilenceButton, INPUT_PULLUP);

  Serial.printf("\nFireSight node %s (%s), reset reason %d\n",
                firesight::config::kFirmwareVersion, firesight::config::kDeviceId,
                static_cast<int>(esp_reset_reason()));
  if (esp_reset_reason() == ESP_RST_BROWNOUT) {
    Serial.println("[power] brownout reset: use a stronger 5 V supply");
  }

  const uint32_t now = millis();
  sensors.begin(now);
  heartbeat.begin();
  last_heartbeat_ms = now;
  enableLoopWDT();
}

void loop() {
  const uint32_t now = millis();

  sensors.update(now);
  handleHeartbeatResult();
  local_alarm.update(now, sensors.gasSmoothed(), sensors.tempC(), sensors.gasReady(now));

  // The button only silences a buzzer that is sounding, so an early press can
  // never pre-mute a later alarm.
  const bool pressed = digitalRead(firesight::pins::kSilenceButton) == LOW;
  if (silence_button.update(pressed, now) && buzzer_active) {
    silence.start(now);
    Serial.println("[button] buzzer silenced");
  }

  const bool alarm_requested = server_buzzer || local_alarm.latched();
  if (!alarm_requested) {
    silence.clear();
  }
  buzzer_active = firesight::core::buzzerOn(server_buzzer, local_alarm.latched(),
                                            silence.active(now));
  writeBuzzer(buzzer_active);

  const bool server_reachable = server_seen && !local_alarm.standalone();
  const auto led_mode = firesight::core::ledModeFor(sensors.gasReady(now), server_reachable,
                                                    server_state, local_alarm.latched());
  digitalWrite(firesight::pins::kStatusLed,
               firesight::core::ledLevel(led_mode, now) ? HIGH : LOW);

  sendHeartbeatIfDue(now);
  delay(2);
}
