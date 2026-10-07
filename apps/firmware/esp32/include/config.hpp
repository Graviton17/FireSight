#pragma once

#include <cstdint>

// Tunable firmware constants. Values marked TUNE are starting points that must be
// replaced after the MQ-2 burn-in and calibration (plan Phase 4.2).
namespace firesight::config {

constexpr const char* kFirmwareVersion = "0.2.0";
constexpr const char* kDeviceId = "node_1";

// Heartbeat (report: every 2 s, short timeout, reply carries the buzzer command).
constexpr uint32_t kHeartbeatPeriodMs = 2000;
constexpr uint16_t kHttpTimeoutMs = 1500;
constexpr uint32_t kWifiRetryMs = 5000;

// Sampling.
constexpr uint32_t kMq2SamplePeriodMs = 250;  // ~4 Hz, averaged per heartbeat
constexpr uint8_t kMq2OversampleCount = 4;
constexpr float kMq2EwmaAlpha = 0.3f;         // local smoothing for the fallback
constexpr uint32_t kNtcSamplePeriodMs = 500;
constexpr uint8_t kNtcOversampleCount = 8;
constexpr float kNtcEwmaAlpha = 0.5f;
constexpr uint32_t kFlameSamplePeriodMs = 50;  // catch flicker between heartbeats

// The flame module's DO pin is usually LOW when it sees flame; flip if yours is not.
constexpr bool kFlameActiveLow = true;

// MQ-2 heater warm-up after every power-up; readings are flagged until it ends. TUNE
constexpr uint32_t kMq2WarmupMs = 180000;

// Outputs. The BC547 driver (or a module with its own driver) is active HIGH;
// set false for buzzer modules that sound when I/O is pulled LOW.
constexpr bool kBuzzerActiveHigh = true;
constexpr uint32_t kButtonSettleMs = 40;
constexpr uint32_t kSilenceMs = 300000;  // report: silence_s = 300

// Local fallback when the server is unreachable (report FR-10).
constexpr uint8_t kFallbackFailLimit = 3;           // ~6 s of missed heartbeats
constexpr float kFallbackGasExtremeRaw = 3200.0f;   // TUNE
constexpr uint32_t kFallbackGasHoldMs = 15000;      // TUNE
constexpr float kFallbackHeatExtremeC = 57.0f;      // TUNE
constexpr uint32_t kFallbackHeatHoldMs = 10000;     // TUNE

// NTC divider: 3V3 -> fixed resistor -> GPIO33 -> NTC -> GND.
constexpr float kNtcFixedOhm = 10000.0f;
constexpr float kNtcNominalOhm = 10000.0f;
constexpr float kNtcBeta = 3950.0f;
constexpr float kNtcSupplyMv = 3300.0f;

constexpr uint32_t kSerialBaud = 115200;

}  // namespace firesight::config
