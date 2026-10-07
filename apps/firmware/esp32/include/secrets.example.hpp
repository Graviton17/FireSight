#pragma once

// Copy this file to include/secrets.hpp (git-ignored) and fill in your values.
namespace firesight::secrets {

constexpr const char* kWifiSsid = "your-wifi-name";
constexpr const char* kWifiPassword = "your-wifi-password";

// The laptop running the backend, on the same network. Find its address with
// `ip addr` (Linux) or `ipconfig` (Windows).
constexpr const char* kTelemetryUrl = "http://192.168.1.10:8000/api/telemetry";

// Must match API_KEY in apps/backend/.env.
constexpr const char* kApiKey = "dev-only-change-me";

}  // namespace firesight::secrets
