#include <math.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>

// ---------- WiFi ----------
const char* WIFI_SSID = "Graviton";
const char* WIFI_PASS = "Graviton@17Hmm";

#define WIFI_CONNECT_TIMEOUT_MS 15000
#define WIFI_RETRY_INTERVAL_MS 10000

// ---------- Server ----------
// FireSight backend (backend/main.py). Replace the IP with your PC's LAN IP.
const char* SERVER_URL = "http://10.29.223.123:8000/api/v1/sensor-data";
#define HTTP_TIMEOUT_MS 5000       // server verifies fire with the camera before answering
#define DEVICE_ID "esp32-fire-01"
#define POST_INTERVAL_MS 5000      // also posts immediately when alarm state changes

// ---------- Pins ----------
#define PIN_NTC 32
#define PIN_BUZZER 33
#define PIN_MQ2_AO 34
#define PIN_FLAME_AO 35
#define PIN_LED 23
#define PIN_SWITCH 21              // one leg to GPIO21, other leg to GND (no resistor needed)

#define BUZZER_ON  HIGH            // swap these if your buzzer module is active-LOW
#define BUZZER_OFF LOW
#define LED_ON  LOW               // LED is active-LOW; swap these if it is wired to GND
#define LED_OFF HIGH
#define LED_BLINK_MS 1000           // blink length after a successful POST

// ---------- Fire thresholds (TUNE THESE) ----------
#define SMOKE_THRESHOLD 1500       // smoke vote when raw ADC  >  this (0-4095)
#define FLAME_THRESHOLD 1000       // flame vote when raw ADC  <  this (0-4095)
#define TEMP_ALARM_C 57.0          // fixed-temperature alarm point
#define TEMP_ROR_C_PER_MIN 8.3     // rate-of-rise alarm point

#define MQ2_WARMUP_MS 30000        // ignore smoke reading while MQ-2 heats up
#define CONFIRM_CYCLES 2           // consecutive fire readings before buzzer turns on
#define CLEAR_CYCLES 5             // consecutive safe readings before buzzer turns off
#define SENSOR_INTERVAL_MS 1000    // how often sensors are checked

// ---------- Thermistor ----------
// Make sure these match your real parts, otherwise the temperature (and the 57C limit) is wrong.
// If your NTC is 100k, set both SERIES_RESISTOR and NOMINAL_RESISTANCE to 100000.
#define SERIES_RESISTOR 10000
#define NOMINAL_RESISTANCE 10000
#define NOMINAL_TEMPERATURE 25
#define B_COEFFICIENT 3950
#define VCC_MV 3300.0

#define NUM_SAMPLES 16

// ---------- Rate-of-rise history ----------
#define TEMP_HIST_SIZE 64
#define ROR_WINDOW_MS 60000        // look back up to 60 s
#define ROR_MIN_SPAN_MS 15000      // need at least 15 s of data to trust the rate

float tempHist[TEMP_HIST_SIZE];
unsigned long tempHistTime[TEMP_HIST_SIZE];
int tempHistHead = 0;
int tempHistCount = 0;

// ---------- Alarm state ----------
bool fireAlarm = false;
int alarmCount = 0;
int clearCount = 0;

// Second verification: the server checks the phone camera and answers "buzz".
// PENDING only lasts while the POST is in flight (max HTTP_TIMEOUT_MS).
enum ServerVerdict { VERDICT_PENDING, VERDICT_BUZZ, VERDICT_SILENT };
ServerVerdict serverVerdict = VERDICT_PENDING;

// Average several ADC samples (raw counts) to reduce noise
int readAveragedRaw(int pin) {
  uint32_t sum = 0;
  for (int i = 0; i < NUM_SAMPLES; i++) {
    sum += analogRead(pin);
    delay(2);
  }
  return (int)(sum / NUM_SAMPLES);
}

// Returns temperature in Celsius, or NAN if the sensor looks disconnected/shorted.
// Wiring assumed: 3.3V -> NTC -> GPIO32 -> fixed resistor -> GND
float readTempC() {
  uint32_t mv = 0;
  for (int i = 0; i < NUM_SAMPLES; i++) {
    mv += analogReadMilliVolts(PIN_NTC);
    delay(2);
  }
  float v = mv / (float)NUM_SAMPLES;

  if (v <= 0 || v >= VCC_MV) return NAN;

  float r = SERIES_RESISTOR * (VCC_MV / v - 1.0);
  float k = log(r / NOMINAL_RESISTANCE) / B_COEFFICIENT + 1.0 / (NOMINAL_TEMPERATURE + 273.15);
  return (1.0 / k) - 273.15;
}

// Stores the reading and returns the temperature rise in C/min over the last ~60 s.
// Returns 0 until enough history exists.
float tempRiseRate(float tempC) {
  if (isnan(tempC)) return 0;

  unsigned long now = millis();
  tempHist[tempHistHead] = tempC;
  tempHistTime[tempHistHead] = now;
  tempHistHead = (tempHistHead + 1) % TEMP_HIST_SIZE;
  if (tempHistCount < TEMP_HIST_SIZE) tempHistCount++;

  int oldest = (tempHistHead - tempHistCount + TEMP_HIST_SIZE) % TEMP_HIST_SIZE;
  for (int k = 0; k < tempHistCount; k++) {
    int idx = (oldest + k) % TEMP_HIST_SIZE;
    unsigned long age = now - tempHistTime[idx];
    if (age <= ROR_WINDOW_MS) {
      if (age < ROR_MIN_SPAN_MS) return 0;
      return (tempC - tempHist[idx]) * 60000.0 / (float)age;
    }
  }
  return 0;
}

// Fire = ALL three sensors are past their limits at the same time.
// 'warning' is set when one or two sensors triggered (not enough for an alarm).
bool evaluateFire(int smoke, int flame, float tempC, float rise, bool &warning) {
  bool smokeValid = millis() > MQ2_WARMUP_MS;

  bool smokeHigh  = smokeValid && (smoke > SMOKE_THRESHOLD);
  bool flameSeen  = flame < FLAME_THRESHOLD;
  bool tempHigh   = !isnan(tempC) && tempC >= TEMP_ALARM_C;
  bool tempRising = rise >= TEMP_ROR_C_PER_MIN;
  bool heat       = tempHigh || tempRising;   // use just 'tempHigh' to require the full 57 C

  int votes = (int)smokeHigh + (int)flameSeen + (int)heat;

  bool fire = (votes == 1);
  warning = (votes >= 1) && !fire;
  return fire;
}

// Buzzer is ON only when the sensors see fire, the server says buzz (or could not
// be reached), AND the switch is not pressed.
// Called every loop pass so the buzzer reacts to the switch immediately.
void applyBuzzer() {
  bool switchPressed = (digitalRead(PIN_SWITCH) == LOW);   // INPUT_PULLUP: pressed = LOW
  bool confirmed = (serverVerdict == VERDICT_BUZZ);
  digitalWrite(PIN_BUZZER, (fireAlarm && confirmed && !switchPressed) ? BUZZER_ON : BUZZER_OFF);
}

// Debounce + latch the alarm state.
void updateAlarm(bool fireNow) {
  if (fireNow) {
    clearCount = 0;
    if (alarmCount < CONFIRM_CYCLES) alarmCount++;
    if (alarmCount >= CONFIRM_CYCLES && !fireAlarm) {
      fireAlarm = true;
      serverVerdict = VERDICT_PENDING;   // wait for the server's camera check
    }
  } else {
    alarmCount = 0;
    if (fireAlarm) {
      clearCount++;
      if (clearCount >= CLEAR_CYCLES) {
        fireAlarm = false;
        clearCount = 0;
        serverVerdict = VERDICT_PENDING;
      }
    }
  }
  applyBuzzer();
}

// One short blink to show a successful POST
void blinkLed() {
  digitalWrite(PIN_LED, LED_ON);
  delay(LED_BLINK_MS);
  digitalWrite(PIN_LED, LED_OFF);
}

// Reads "buzz" from the server's JSON reply, e.g. {...,"buzz":true,...}.
// Missing or unreadable -> true (fail-safe: trust the sensors).
bool parseBuzz(const String &body) {
  int i = body.indexOf("\"buzz\"");
  if (i < 0) return true;
  i = body.indexOf(':', i);
  if (i < 0) return true;
  i++;
  while (i < (int)body.length() && body[i] == ' ') i++;
  return !body.startsWith("false", i);
}

// Sends sensor readings as JSON via HTTP POST. Returns true on 2xx response and
// sets 'buzz' to the server's decision.
bool postSensorData(int smoke, int flame, float tempC, bool fire, bool &buzz) {
  buzz = true;   // fail-safe until the server says otherwise
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("POST skipped: WiFi not connected");
    return false;
  }

  String payload = "{";
  payload += "\"device_id\":\"" DEVICE_ID "\",";
  payload += "\"smoke\":" + String(smoke) + ",";
  payload += "\"flame\":" + String(flame) + ",";
  payload += "\"temperature\":";
  payload += isnan(tempC) ? String("null") : String(tempC, 1);
  payload += ",\"fire\":";
  payload += fire ? "true" : "false";
  payload += "}";

  HTTPClient http;
  WiFiClientSecure secureClient;
  WiFiClient plainClient;

  bool isHttps = String(SERVER_URL).startsWith("https://");
  if (isHttps) {
    secureClient.setInsecure();  // skips certificate check; use setCACert() in production
    http.begin(secureClient, SERVER_URL);
  } else {
    http.begin(plainClient, SERVER_URL);
  }

  http.setConnectTimeout(HTTP_TIMEOUT_MS);
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.addHeader("Content-Type", "application/json");

  int code = http.POST(payload);

  if (code > 0) {
    Serial.print("POST response code: ");
    Serial.println(code);
    if (code >= 200 && code < 300) buzz = parseBuzz(http.getString());
  } else {
    Serial.print("POST failed: ");
    Serial.println(HTTPClient::errorToString(code));
  }

  http.end();
  return (code >= 200 && code < 300);
}

void checkSensors() {
  static unsigned long lastPost = 0;
  static bool lastFireState = false;

  int smokeValue = readAveragedRaw(PIN_MQ2_AO);
  int flameValue = readAveragedRaw(PIN_FLAME_AO);
  float tempC = readTempC();
  float rise = tempRiseRate(tempC);

  // Decide and drive the buzzer FIRST, before any slow network work
  bool warning = false;
  bool fireNow = evaluateFire(smokeValue, flameValue, tempC, rise, warning);
  updateAlarm(fireNow);

  Serial.print("Smoke: ");
  Serial.print(smokeValue);
  if (millis() <= MQ2_WARMUP_MS) Serial.print("  (MQ-2 warming up)");
  Serial.println();

  Serial.print("Flame: ");
  Serial.println(flameValue);

  Serial.print("Temp: ");
  if (isnan(tempC)) {
    Serial.println("Error/Disconnected");
  } else {
    Serial.print(tempC, 1);
    Serial.print(" °C  (rise ");
    Serial.print(rise, 1);
    Serial.println(" °C/min)");
  }

  Serial.print("Status: ");
  Serial.println(fireAlarm ? "FIRE ALARM" : (warning ? "WARNING" : "OK"));
  Serial.println();

  // Post every POST_INTERVAL_MS, or immediately when the alarm state changes
  unsigned long now = millis();
  if (fireAlarm != lastFireState || now - lastPost >= POST_INTERVAL_MS) {
    lastFireState = fireAlarm;
    lastPost = now;
    bool buzz = true;
    bool ok = postSensorData(smokeValue, flameValue, tempC, fireAlarm, buzz);

    if (fireAlarm) {
      // Server unreachable -> buzz anyway (fail-safe). Otherwise obey the camera check.
      serverVerdict = (!ok || buzz) ? VERDICT_BUZZ : VERDICT_SILENT;
      applyBuzzer();   // before the LED blink, which blocks
      Serial.print("Camera verification: ");
      Serial.println(!ok ? "server unreachable -> BUZZ (fail-safe)"
                         : (buzz ? "fire confirmed -> BUZZ" : "no fire in image -> SILENT"));
    }

    if (ok) {
      Serial.println("reached");
      blinkLed();   // blink only when the server returned 2xx
    }
  }
}

// Connects to WiFi and waits up to the timeout. Used once in setup().
bool connectWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < WIFI_CONNECT_TIMEOUT_MS) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("WiFi connected. IP: ");
    Serial.println(WiFi.localIP());
    return true;
  }

  Serial.println("WiFi connection failed");
  return false;
}

// Non-blocking reconnect: never stalls the fire detection while WiFi is down.
void ensureWiFi() {
  static unsigned long lastAttempt = 0;

  if (WiFi.status() == WL_CONNECTED) return;
  if (millis() - lastAttempt < WIFI_RETRY_INTERVAL_MS) return;
  lastAttempt = millis();

  Serial.println("WiFi disconnected, retrying...");
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASS);
}

void setup() {
  Serial.begin(115200);

  analogSetAttenuation(ADC_11db);

  pinMode(PIN_MQ2_AO, INPUT);
  pinMode(PIN_FLAME_AO, INPUT);
  pinMode(PIN_NTC, INPUT);

  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, BUZZER_OFF);

  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LED_OFF);

  pinMode(PIN_SWITCH, INPUT_PULLUP);   // pressed = LOW

  // Short beep at boot to confirm the buzzer wiring
  digitalWrite(PIN_BUZZER, BUZZER_ON);
  delay(200);
  digitalWrite(PIN_BUZZER, BUZZER_OFF);

  connectWiFi();
}

void loop() {
  static unsigned long lastRead = 0;

  ensureWiFi();
  applyBuzzer();   // checks the switch on every pass

  if (millis() - lastRead >= SENSOR_INTERVAL_MS) {
    lastRead = millis();
    checkSensors();
  }
}
