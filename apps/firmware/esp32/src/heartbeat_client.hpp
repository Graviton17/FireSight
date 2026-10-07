#pragma once

#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>
#include <freertos/task.h>

#include <cstdint>

#include "firesight_core.hpp"
#include "sensors.hpp"

namespace firesight {

struct HeartbeatPayload {
  SensorWindow sensors;
  bool local_alarm = false;
  bool silenced = false;
  uint32_t uptime_s = 0;
};

struct HeartbeatResult {
  bool ok = false;
  bool buzzer = false;
  core::DeviceState state = core::DeviceState::kUnknown;
  int http_code = 0;  // negative values are HTTPClient transport errors
};

// Owns Wi-Fi and the HTTP heartbeat. Requests run in a separate FreeRTOS task, so a
// slow or missing server never stalls sampling, the buzzer or the silence button.
class HeartbeatClient {
 public:
  void begin();

  // Queues a heartbeat; a newer payload replaces one that has not been sent yet.
  void send(const HeartbeatPayload& payload);

  // Returns true and fills `out` when a heartbeat finished since the last call.
  bool takeResult(HeartbeatResult& out);

  bool wifiConnected() const;

 private:
  static void taskEntry(void* self);
  void run();
  void ensureWifi();
  HeartbeatResult post(const HeartbeatPayload& payload);

  SemaphoreHandle_t mutex_ = nullptr;
  TaskHandle_t task_ = nullptr;
  HeartbeatPayload pending_;
  HeartbeatResult result_;
  bool has_result_ = false;
  uint32_t last_wifi_attempt_ms_ = 0;
};

}  // namespace firesight
