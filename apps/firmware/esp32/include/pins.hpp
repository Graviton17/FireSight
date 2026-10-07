#pragma once

#include <Arduino.h>

// Budget build pin map (see the "Phase 1" circuit diagram in the project plan).
// All analog inputs are on ADC1, because ADC2 cannot be read while Wi-Fi is on.
namespace firesight::pins {
constexpr gpio_num_t kMq2Adc = GPIO_NUM_34;        // MQ-2 AO via 10k/15k divider
constexpr gpio_num_t kFlameDigital = GPIO_NUM_32;  // IR flame module DO
constexpr gpio_num_t kFlameAnalog = GPIO_NUM_35;   // IR flame module AO
constexpr gpio_num_t kHeatNtc = GPIO_NUM_33;       // NTC divider node
constexpr gpio_num_t kBuzzer = GPIO_NUM_18;
constexpr gpio_num_t kStatusLed = GPIO_NUM_19;
constexpr gpio_num_t kSilenceButton = GPIO_NUM_27;  // to GND, internal pull-up
}  // namespace firesight::pins
