#include "heartbeat_client.hpp"

#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <esp_task_wdt.h>

#include <cmath>

#include "config.hpp"

#if __has_include("secrets.hpp")
#include "secrets.hpp"
#else
#error "Copy include/secrets.example.hpp to include/secrets.hpp and fill in Wi-Fi and server details."
#endif

namespace firesight {

namespace {
constexpr uint32_t kTaskStackBytes = 8192;
constexpr UBaseType_t kTaskPriority = 1;
constexpr BaseType_t kTaskCore = 0;  // Arduino loop() runs on core 1
// Wake at least this often to feed the task watchdog while idle.
constexpr TickType_t kIdleWaitTicks = pdMS_TO_TICKS(1000);
}  // namespace

void HeartbeatClient::begin() {
  mutex_ = xSemaphoreCreateMutex();

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(secrets::kWifiSsid, secrets::kWifiPassword);
  last_wifi_attempt_ms_ = millis();

  xTaskCreatePinnedToCore(&HeartbeatClient::taskEntry, "heartbeat", kTaskStackBytes, this,
                          kTaskPriority, &task_, kTaskCore);
}

void HeartbeatClient::send(const HeartbeatPayload& payload) {
  xSemaphoreTake(mutex_, portMAX_DELAY);
  pending_ = payload;
  xSemaphoreGive(mutex_);
  xTaskNotifyGive(task_);
}

bool HeartbeatClient::takeResult(HeartbeatResult& out) {
  xSemaphoreTake(mutex_, portMAX_DELAY);
  const bool fresh = has_result_;
  if (fresh) {
    out = result_;
    has_result_ = false;
  }
  xSemaphoreGive(mutex_);
  return fresh;
}

bool HeartbeatClient::wifiConnected() const { return WiFi.status() == WL_CONNECTED; }

void HeartbeatClient::taskEntry(void* self) { static_cast<HeartbeatClient*>(self)->run(); }

void HeartbeatClient::run() {
  // Not every core version starts the task watchdog; carry on without it if not.
  const bool watched = esp_task_wdt_add(nullptr) == ESP_OK;

  for (;;) {
    if (watched) {
      esp_task_wdt_reset();
    }
    if (ulTaskNotifyTake(pdTRUE, kIdleWaitTicks) == 0) {
      ensureWifi();
      continue;
    }

    xSemaphoreTake(mutex_, portMAX_DELAY);
    const HeartbeatPayload payload = pending_;
    xSemaphoreGive(mutex_);

    ensureWifi();
    const HeartbeatResult result = post(payload);

    xSemaphoreTake(mutex_, portMAX_DELAY);
    result_ = result;
    has_result_ = true;
    xSemaphoreGive(mutex_);
  }
}

void HeartbeatClient::ensureWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }
  const uint32_t now = millis();
  if (static_cast<uint32_t>(now - last_wifi_attempt_ms_) < config::kWifiRetryMs) {
    return;
  }
  last_wifi_attempt_ms_ = now;
  Serial.println("[wifi] not connected, retrying");
  WiFi.disconnect();
  WiFi.begin(secrets::kWifiSsid, secrets::kWifiPassword);
}

HeartbeatResult HeartbeatClient::post(const HeartbeatPayload& payload) {
  HeartbeatResult result;
  if (WiFi.status() != WL_CONNECTED) {
    result.http_code = -1;
    return result;
  }

  JsonDocument body;
  body["device_id"] = config::kDeviceId;
  body["mq2"] = payload.sensors.mq2;
  if (std::isnan(payload.sensors.temp_c)) {
    body["temp_c"] = nullptr;
  } else {
    body["temp_c"] = roundf(payload.sensors.temp_c * 10.0f) / 10.0f;
  }
  body["hum_pct"] = nullptr;  // no humidity sensor in the budget build
  body["warmup_done"] = payload.sensors.warmup_done;
  body["local_alarm"] = payload.local_alarm;
  body["uptime_s"] = payload.uptime_s;
  body["rssi"] = WiFi.RSSI();
  body["fw"] = config::kFirmwareVersion;
  body["flame_ir"] = payload.sensors.flame_ir;
  body["flame_ir_raw"] = payload.sensors.flame_ir_raw;
  body["silenced"] = payload.silenced;

  String request;
  serializeJson(body, request);

  HTTPClient http;
  http.setConnectTimeout(config::kHttpTimeoutMs);
  http.setTimeout(config::kHttpTimeoutMs);
  if (!http.begin(secrets::kTelemetryUrl)) {
    result.http_code = -2;
    return result;
  }
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", secrets::kApiKey);

  result.http_code = http.POST(request);
  if (result.http_code == HTTP_CODE_OK) {
    JsonDocument reply;
    const DeserializationError error = deserializeJson(reply, http.getString());
    if (!error && reply["buzzer"].is<bool>() && reply["state"].is<const char*>()) {
      result.ok = true;
      result.buzzer = reply["buzzer"].as<bool>();
      result.state = core::parseDeviceState(reply["state"].as<const char*>());
    }
  }
  http.end();
  return result;
}

}  // namespace firesight
