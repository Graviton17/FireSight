#include <unity.h>

#include <cmath>

#include "firesight_core.hpp"

using namespace firesight::core;

#define ASSERT_ENUM(expected, actual) \
  TEST_ASSERT_EQUAL_INT(static_cast<int>(expected), static_cast<int>(actual))

void setUp() {}
void tearDown() {}

// --- NTC -------------------------------------------------------------------

void test_ntc_reads_nominal_temperature_at_half_supply() {
  NtcParams params;
  // Equal resistances put the node at half the supply: 10 kOhm NTC = 25 C.
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 10000.0f, ntcResistanceOhm(1650.0f, params));
  TEST_ASSERT_FLOAT_WITHIN(0.05f, 25.0f, ntcTemperatureC(1650.0f, params));
}

void test_ntc_lower_voltage_means_hotter() {
  NtcParams params;
  TEST_ASSERT_TRUE(ntcTemperatureC(800.0f, params) > ntcTemperatureC(1650.0f, params));
}

void test_ntc_matches_beta_equation_at_60c() {
  NtcParams params;
  // R(60 C) = 10k * exp(3950 * (1/333.15 - 1/298.15)) ~= 2488 Ohm.
  const float r60 = 10000.0f * std::exp(3950.0f * (1.0f / 333.15f - 1.0f / 298.15f));
  const float node_mv = 3300.0f * r60 / (10000.0f + r60);
  TEST_ASSERT_FLOAT_WITHIN(0.2f, 60.0f, ntcTemperatureC(node_mv, params));
}

void test_ntc_open_or_short_is_nan() {
  NtcParams params;
  TEST_ASSERT_TRUE(std::isnan(ntcTemperatureC(0.0f, params)));     // NTC shorted
  TEST_ASSERT_TRUE(std::isnan(ntcTemperatureC(3300.0f, params)));  // NTC missing
}

// --- Filters -----------------------------------------------------------------

void test_ewma_starts_at_first_sample_then_smooths() {
  Ewma ewma(0.5f);
  TEST_ASSERT_EQUAL_FLOAT(100.0f, ewma.update(100.0f));
  TEST_ASSERT_EQUAL_FLOAT(150.0f, ewma.update(200.0f));
}

void test_window_mean_resets_after_take() {
  WindowMean window;
  window.add(10.0f);
  window.add(20.0f);
  TEST_ASSERT_EQUAL_FLOAT(15.0f, window.take(0.0f));
  TEST_ASSERT_TRUE(window.empty());
  TEST_ASSERT_EQUAL_FLOAT(7.0f, window.take(7.0f));
}

// --- Button and silence --------------------------------------------------------

void test_debouncer_fires_once_after_settling() {
  Debouncer button(40);
  TEST_ASSERT_FALSE(button.update(true, 0));
  TEST_ASSERT_FALSE(button.update(true, 30));
  TEST_ASSERT_TRUE(button.update(true, 41));
  TEST_ASSERT_FALSE(button.update(true, 500));  // held: no repeat
}

void test_debouncer_ignores_bounce() {
  Debouncer button(40);
  button.update(true, 0);
  button.update(false, 10);
  TEST_ASSERT_FALSE(button.update(true, 20));
  TEST_ASSERT_FALSE(button.update(true, 50));
  TEST_ASSERT_TRUE(button.update(true, 61));
}

void test_silence_expires() {
  Silence silence(300000);
  silence.start(1000);
  TEST_ASSERT_TRUE(silence.active(1000 + 299999));
  TEST_ASSERT_FALSE(silence.active(1000 + 300000));
}

void test_silence_survives_millis_wraparound() {
  Silence silence(1000);
  silence.start(0xFFFFFF00u);
  TEST_ASSERT_TRUE(silence.active(0x00000100u));  // 512 ms later
}

void test_buzzer_decision() {
  TEST_ASSERT_TRUE(buzzerOn(true, false, false));
  TEST_ASSERT_TRUE(buzzerOn(false, true, false));
  TEST_ASSERT_FALSE(buzzerOn(true, true, true));
  TEST_ASSERT_FALSE(buzzerOn(false, false, false));
}

// --- Local fallback alarm ---------------------------------------------------------

FallbackConfig testConfig() {
  FallbackConfig config;
  config.fail_limit = 3;
  config.gas_extreme_raw = 3200.0f;
  config.gas_hold_ms = 15000;
  config.heat_extreme_c = 57.0f;
  config.heat_hold_ms = 10000;
  return config;
}

void goStandalone(LocalAlarm& alarm) {
  alarm.onHeartbeat(false, false);
  alarm.onHeartbeat(false, false);
  alarm.onHeartbeat(false, false);
}

void test_fallback_needs_three_failures() {
  LocalAlarm alarm(testConfig());
  alarm.onHeartbeat(false, false);
  alarm.onHeartbeat(false, false);
  TEST_ASSERT_FALSE(alarm.standalone());
  alarm.onHeartbeat(false, false);
  TEST_ASSERT_TRUE(alarm.standalone());
  alarm.onHeartbeat(true, false);
  TEST_ASSERT_FALSE(alarm.standalone());
}

void test_fallback_ignores_extreme_gas_while_server_is_up() {
  LocalAlarm alarm(testConfig());
  alarm.update(0, 4000.0f, NAN, true);
  alarm.update(60000, 4000.0f, NAN, true);
  TEST_ASSERT_FALSE(alarm.latched());
}

void test_fallback_latches_on_held_extreme_gas() {
  LocalAlarm alarm(testConfig());
  goStandalone(alarm);
  alarm.update(0, 3300.0f, 25.0f, true);
  alarm.update(14999, 3300.0f, 25.0f, true);
  TEST_ASSERT_FALSE(alarm.latched());
  alarm.update(15000, 3300.0f, 25.0f, true);
  TEST_ASSERT_TRUE(alarm.latched());
  ASSERT_ENUM(LocalReason::kGasExtreme, alarm.reason());
}

void test_fallback_gas_dip_restarts_the_hold() {
  LocalAlarm alarm(testConfig());
  goStandalone(alarm);
  alarm.update(0, 3300.0f, 25.0f, true);
  alarm.update(10000, 3000.0f, 25.0f, true);
  alarm.update(11000, 3300.0f, 25.0f, true);
  alarm.update(20000, 3300.0f, 25.0f, true);
  TEST_ASSERT_FALSE(alarm.latched());
}

void test_fallback_ignores_gas_during_warmup_but_not_heat() {
  LocalAlarm alarm(testConfig());
  goStandalone(alarm);
  alarm.update(0, 4000.0f, 60.0f, false);
  alarm.update(20000, 4000.0f, 60.0f, false);
  TEST_ASSERT_TRUE(alarm.latched());
  ASSERT_ENUM(LocalReason::kHeat, alarm.reason());
}

void test_fallback_nan_temperature_never_alarms() {
  LocalAlarm alarm(testConfig());
  goStandalone(alarm);
  alarm.update(0, 100.0f, NAN, true);
  alarm.update(60000, 100.0f, NAN, true);
  TEST_ASSERT_FALSE(alarm.latched());
}

void test_fallback_keeps_an_alarm_the_server_raised() {
  LocalAlarm alarm(testConfig());
  alarm.onHeartbeat(true, true);  // server says ALARM
  goStandalone(alarm);
  TEST_ASSERT_TRUE(alarm.latched());
  ASSERT_ENUM(LocalReason::kServerAlarmKept, alarm.reason());
}

void test_fallback_latch_clears_only_when_server_adopts_it() {
  LocalAlarm alarm(testConfig());
  goStandalone(alarm);
  alarm.update(0, 3300.0f, 25.0f, true);
  alarm.update(15000, 3300.0f, 25.0f, true);
  TEST_ASSERT_TRUE(alarm.latched());
  alarm.onHeartbeat(true, false);  // reachable, but not yet ALARM
  TEST_ASSERT_TRUE(alarm.latched());
  alarm.onHeartbeat(true, true);   // server adopted the local alarm
  TEST_ASSERT_FALSE(alarm.latched());
}

// --- State and LED -----------------------------------------------------------------

void test_parse_device_state() {
  ASSERT_ENUM(DeviceState::kAlarm, parseDeviceState("ALARM"));
  ASSERT_ENUM(DeviceState::kWarmup, parseDeviceState("WARMUP"));
  ASSERT_ENUM(DeviceState::kUnknown, parseDeviceState("alarm"));
  ASSERT_ENUM(DeviceState::kUnknown, parseDeviceState(nullptr));
}

void test_led_mode_priorities() {
  ASSERT_ENUM(LedMode::kAlarm, ledModeFor(true, false, DeviceState::kUnknown, true));
  ASSERT_ENUM(LedMode::kFault, ledModeFor(true, false, DeviceState::kNormal, false));
  ASSERT_ENUM(LedMode::kWarmup, ledModeFor(false, true, DeviceState::kNormal, false));
  ASSERT_ENUM(LedMode::kChecking, ledModeFor(true, true, DeviceState::kWarning, false));
  ASSERT_ENUM(LedMode::kNormal, ledModeFor(true, true, DeviceState::kNormal, false));
}

void test_led_patterns() {
  TEST_ASSERT_TRUE(ledLevel(LedMode::kFault, 12345));
  TEST_ASSERT_TRUE(ledLevel(LedMode::kAlarm, 50));
  TEST_ASSERT_FALSE(ledLevel(LedMode::kAlarm, 150));
  TEST_ASSERT_TRUE(ledLevel(LedMode::kNormal, 2050));
  TEST_ASSERT_FALSE(ledLevel(LedMode::kNormal, 2500));
}

int main() {
  UNITY_BEGIN();
  RUN_TEST(test_ntc_reads_nominal_temperature_at_half_supply);
  RUN_TEST(test_ntc_lower_voltage_means_hotter);
  RUN_TEST(test_ntc_matches_beta_equation_at_60c);
  RUN_TEST(test_ntc_open_or_short_is_nan);
  RUN_TEST(test_ewma_starts_at_first_sample_then_smooths);
  RUN_TEST(test_window_mean_resets_after_take);
  RUN_TEST(test_debouncer_fires_once_after_settling);
  RUN_TEST(test_debouncer_ignores_bounce);
  RUN_TEST(test_silence_expires);
  RUN_TEST(test_silence_survives_millis_wraparound);
  RUN_TEST(test_buzzer_decision);
  RUN_TEST(test_fallback_needs_three_failures);
  RUN_TEST(test_fallback_ignores_extreme_gas_while_server_is_up);
  RUN_TEST(test_fallback_latches_on_held_extreme_gas);
  RUN_TEST(test_fallback_gas_dip_restarts_the_hold);
  RUN_TEST(test_fallback_ignores_gas_during_warmup_but_not_heat);
  RUN_TEST(test_fallback_nan_temperature_never_alarms);
  RUN_TEST(test_fallback_keeps_an_alarm_the_server_raised);
  RUN_TEST(test_fallback_latch_clears_only_when_server_adopts_it);
  RUN_TEST(test_parse_device_state);
  RUN_TEST(test_led_mode_priorities);
  RUN_TEST(test_led_patterns);
  return UNITY_END();
}
