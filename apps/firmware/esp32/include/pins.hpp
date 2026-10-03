#pragma once

#include <Arduino.h>

namespace firesight::pins {
constexpr gpio_num_t kMq2Adc = GPIO_NUM_34;
constexpr gpio_num_t kDht11Data = GPIO_NUM_4;
constexpr gpio_num_t kBuzzer = GPIO_NUM_18;
constexpr gpio_num_t kStatusLed = GPIO_NUM_19;
constexpr gpio_num_t kSilenceButton = GPIO_NUM_27;
}  // namespace firesight::pins
