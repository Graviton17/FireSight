# FireSight ESP32 Firmware

Arduino C++ firmware for the budget FireSight node: MQ-2 smoke/gas sensor, IR flame
module, NTC thermistor, buzzer, status LED and silence button on an ESP32 DevKit.
Every 2 s it posts a heartbeat to `POST /api/telemetry` and applies the buzzer
command in the reply. If the server stops answering, it raises its own alarm.

## Wiring

| Part | ESP32 pin | Notes |
| --- | --- | --- |
| MQ-2 AO | GPIO34 | Through a 10 kΩ (series) / 15 kΩ (to GND) divider, 100 nF to GND. Never wire AO straight to the pin. |
| MQ-2 VCC / GND | VIN (5 V) / GND | The heater needs 5 V. |
| IR flame DO / AO | GPIO32 / GPIO35 | Power the module from **3V3**, not 5 V. |
| NTC thermistor | GPIO33 | 3V3 → 10 kΩ → GPIO33 → NTC → GND, 100 nF from GPIO33 to GND. |
| Buzzer | GPIO18 | Through a BC547 driver, or a buzzer module's I/O pin. |
| Status LED | GPIO19 | Through 330 Ω to GND. |
| Silence button | GPIO27 | To GND; the internal pull-up is used. |

The pin map is in `include/pins.hpp`; every analog input is on ADC1 because ADC2
stops working while Wi-Fi is on.

## Setup

1. Copy `include/secrets.example.hpp` to `include/secrets.hpp` (git-ignored) and set
   your Wi-Fi name and password, the laptop's address in `kTelemetryUrl`, and
   `kApiKey` to match `API_KEY` in `apps/backend/.env`.
2. Start the backend on the laptop (`make api-run`) and allow port 8000 through the
   firewall on private networks.
3. Build, flash and watch the serial log:

```bash
pio run -e esp32dev -t upload
```

```bash
pio device monitor -e esp32dev
```

Tunable values (heartbeat period, MQ-2 warm-up, fallback thresholds, buzzer and
flame polarity) live in `include/config.hpp`. Values marked TUNE are placeholders
until the sensors are calibrated.

## What it does

- **Sampling:** MQ-2 at ~4 Hz (averaged per heartbeat), NTC every 500 ms, flame
  module every 50 ms so a brief flicker between heartbeats is still reported.
- **Warm-up:** `warmup_done` stays `false` for the first 3 minutes after power-up
  so the server ignores MQ-2 readings while the heater warms.
- **Heartbeat:** runs in its own FreeRTOS task with a 1.5 s timeout, so a slow
  server never delays the buzzer or the button.
- **Fallback:** after 3 missed heartbeats (~6 s) the node is standalone. It sounds
  the buzzer itself on held extreme gas (3200 counts for 15 s) or heat (57 °C for
  10 s), and keeps sounding if the server had already raised an alarm. On
  reconnection it sends `local_alarm: true` until the server replies `ALARM`.
- **Silence button:** silences a sounding buzzer for 5 minutes and reports
  `silenced: true`. A press while nothing is sounding is ignored, so it can never
  pre-mute a later alarm.
- **Watchdogs:** the loop and heartbeat tasks are watched; a brownout reset is
  logged with a hint to use a stronger supply.

## Status LED

| Pattern | Meaning |
| --- | --- |
| Slow blink (1 Hz) | MQ-2 warming up |
| Short flash every 2 s | Normal, server reachable |
| Double flash | Server is checking (CHECKING or WARNING) |
| Fast blink (5 Hz) | Alarm |
| Solid on | Server unreachable |

## Serial log

```text
[sense] mq2=812 smooth=809 temp=27.4 flame=0 flame_raw=3900 warm=1
[hb] code=200 ok=1 state=NORMAL buzzer=0 local=none fails=0
```

`code=-1` means Wi-Fi is down; other negative codes are HTTP transport errors (for
example, the server is not running or the firewall blocks port 8000).

## Tests

The safety logic (NTC conversion, button debounce, silence timer, fallback alarm,
LED patterns) lives in `lib/firesight_core` with no Arduino dependencies and is
unit-tested on the development machine:

```bash
pio test -e native
```
