#include <Arduino.h>

#include "pins.hpp"

void setup() {
  Serial.begin(115200);
  pinMode(firesight::pins::kBuzzer, OUTPUT);
  pinMode(firesight::pins::kStatusLed, OUTPUT);
  pinMode(firesight::pins::kSilenceButton, INPUT_PULLUP);
  digitalWrite(firesight::pins::kBuzzer, LOW);
}

void loop() {
  // Firmware services will add sampling, Wi-Fi heartbeats, watchdog handling,
  // and local alarm fallback without blocking this loop.
  digitalWrite(firesight::pins::kStatusLed, HIGH);
  delay(100);
  digitalWrite(firesight::pins::kStatusLed, LOW);
  delay(900);
}
