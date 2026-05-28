#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include "StateEngine.h"
#include "EventEngine.h"
#include "NetworkEngine.h"
#include "DisplayEngine.h"

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

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("================================");
  Serial.println("  SOPHIA ∞ MVP — Boot v1.0.0  ");
  Serial.println("================================");

  // 1. WIFI — exatamente como no head tracker
  Serial.println("[NET] Conectando WiFi...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  int tentativas = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    if (++tentativas > 40) {
      Serial.println("\n[NET] Falha no WiFi!");
      ESP.restart();
    }
  }
  Serial.println();
  Serial.print("[NET] WiFi OK | IP: ");
  Serial.println(WiFi.localIP());

  // 2. MQTT
  Serial.println("[NET] MQTT...");
  network.begin();

  // 3. DISPLAY
  Wire.begin(21, 22);
  Serial.print("[DISPLAY] OLED... ");
  if (!display.begin()) {
    Serial.println("ERRO!");
  } else {
    Serial.println("OK");
    display.showIP(WiFi.localIP().toString().c_str());
    delay(1500);
  }

  // 4. SENSOR
  Wire1.begin(SDA_PIN, SCL_PIN);
  Serial.print("[SENSOR] MPU6050... ");
  if (!mpu.begin(0x68, &Wire1)) {
    Serial.println("ERRO!");
    display.showError("MPU6050 falhou!");
    while (true) { delay(500); }
  }
  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
  Serial.println("OK");

  Serial.println("================================");
  Serial.println("[SOPHIA] Sistema nervoso ativo!");
  Serial.println("[STATE]  IDLE");
  Serial.println("================================");
  display.showState("IDLE", 0.0f);
}

void loop() {
  network.loop();

  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);

  float intensidade = fabs(sqrt(
    a.acceleration.x * a.acceleration.x +
    a.acceleration.y * a.acceleration.y +
    a.acceleration.z * a.acceleration.z
  ) - 9.8f);

  stateEngine.update(intensidade);

  if (eventEngine.process(intensidade)) {
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

  delay(100);
}
