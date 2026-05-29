#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include "StateEngine.h"
#include "EventEngine.h"
#include "NetworkEngine.h"
#include "DisplayEngine.h"
#include "AudioEngine.h"
#include "TelemetryEngine.h"

#define SDA_PIN  32
#define SCL_PIN  33

#define WIFI_SSID   "Victor - 2.4G-EXT"
#define WIFI_PASS   "07110589"
#define MQTT_BROKER "192.168.15.65"

Adafruit_MPU6050 mpu;
StateEngine      stateEngine;
EventEngine      eventEngine(stateEngine);
NetworkEngine    network(WIFI_SSID, WIFI_PASS, MQTT_BROKER);
DisplayEngine    display;
AudioEngine      audio;
TelemetryEngine  telemetry;

unsigned long ultimoLogAudio = 0;
unsigned long ultimoTelemetry = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("================================");
  Serial.println("  SOPHIA ∞ MVP — Boot v1.0.0  ");
  Serial.println("================================");

  Serial.println("[NET] Conectando WiFi...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  int tentativas = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    if (++tentativas > 40) { ESP.restart(); }
  }
  Serial.println();
  Serial.print("[NET] WiFi OK | IP: ");
  Serial.println(WiFi.localIP());
  network.begin();

  Wire.begin(21, 22);
  Serial.print("[DISPLAY] OLED... ");
  display.begin() ? Serial.println("OK") : Serial.println("ERRO!");
  display.showIP(WiFi.localIP().toString().c_str());
  delay(1500);

  Wire1.begin(SDA_PIN, SCL_PIN);
  Serial.print("[SENSOR] MPU6050... ");
  if (!mpu.begin(0x68, &Wire1)) {
    Serial.println("ERRO!");
    while (true) { delay(500); }
  }
  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
  Serial.println("OK");

  Serial.print("[AUDIO] INMP441... ");
  audio.begin() ? Serial.println("OK") : Serial.println("ERRO!");

  telemetry.begin();

  Serial.println("================================");
  Serial.println("[SOPHIA] Sistema nervoso ativo!");
  Serial.println("[STATE]  IDLE");
  Serial.println("================================");
  display.showState("IDLE", 0.0f);
}

void loop() {
  audio.read();
  float audioIntensidade = audio.getIntensidade();
  bool  audioAtivo       = audio.isAtivo();

  network.loop();

  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);
  float movIntensidade = fabs(sqrt(
    a.acceleration.x * a.acceleration.x +
    a.acceleration.y * a.acceleration.y +
    a.acceleration.z * a.acceleration.z
  ) - 9.8f);

  float intensidade = max(movIntensidade, audioIntensidade * 10.0f);
  stateEngine.update(intensidade);

  // log audio
  unsigned long agora = millis();
  if (agora - ultimoLogAudio > 500) {
    Serial.print("[AUDIO]  ativo: ");
    Serial.print(audioAtivo ? "SIM" : "NAO");
    Serial.print(" | int: ");
    Serial.print(audioIntensidade, 2);
    Serial.print(" | mov: ");
    Serial.println(movIntensidade, 2);
    ultimoLogAudio = agora;
  }

  // telemetria a cada 10s
  if (agora - ultimoTelemetry > 10000) {
    String tJson = telemetry.toJson();
    Serial.print("[TELEMETRY] ");
    Serial.println(tJson);
    network.publish("sophia/telemetry", tJson);
    ultimoTelemetry = agora;
  }

  if (eventEngine.process(movIntensidade, audioIntensidade, audioAtivo)) {
    String json = eventEngine.toJson();
    Serial.print("[EVENT]  ");
    Serial.println(json);
    network.publish("sophia/events", json);

    SophiaEvent ev = eventEngine.getLast();
    display.showState(stateEngine.getStateName(), ev.severity);

    if (ev.type == EVENT_STATE_CHANGED) {
      display.showEvent(stateEngine.getStateName());
      delay(800);
      display.showState(stateEngine.getStateName(), ev.severity);
    }
  }
}
