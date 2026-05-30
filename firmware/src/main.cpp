#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include "StateEngine.h"
#include "EventEngine.h"
#include "DisplayEngine.h"
#include "AudioEngine.h"
#include "TelemetryEngine.h"

// ── Pinos ─────────────────────────────────────────────────────────────────
#define SDA_PIN   32
#define SCL_PIN   33
#define PIEZO_PIN 35

// ── Piezo ─────────────────────────────────────────────────────────────────
#define PIEZO_THRESHOLD  150
#define PIEZO_MAX       4095.0f
#define ANTI_SPAM_MS     200
#define AMOSTRAS           8
#define JANELA_MS          50

// ── MPU calibração ────────────────────────────────────────────────────────
// Calibramos o offset de repouso nas primeiras amostras do boot
#define CAL_AMOSTRAS  50
float movOffset = 0.0f;   // valor médio em repouso — subtraído em todo loop

// ── Objetos ───────────────────────────────────────────────────────────────
Adafruit_MPU6050 mpu;
StateEngine      stateEngine;
EventEngine      eventEngine(stateEngine);
DisplayEngine    display;
AudioEngine      audio;
TelemetryEngine  telemetry;

unsigned long ultimoLogAudio  = 0;
unsigned long ultimoTelemetry = 0;
unsigned long ultimoImpacto   = 0;

// ── Piezo helpers ─────────────────────────────────────────────────────────
int lerPiezo() {
  int soma = 0;
  for (int i = 0; i < AMOSTRAS; i++) {
    soma += analogRead(PIEZO_PIN);
    delayMicroseconds(200);
  }
  return soma / AMOSTRAS;
}

int capturarPico() {
  int pico = 0;
  unsigned long inicio = millis();
  while (millis() - inicio < JANELA_MS) {
    int v = lerPiezo();
    if (v > pico) pico = v;
    delayMicroseconds(500);
  }
  return pico;
}

float lerPiezoNormalizado() {
  unsigned long agora = millis();
  int leitura = lerPiezo();
  if (leitura > PIEZO_THRESHOLD && agora - ultimoImpacto > ANTI_SPAM_MS) {
    int pico = capturarPico();
    if (pico > PIEZO_THRESHOLD) {
      ultimoImpacto = agora;
      float norm = (float)pico / PIEZO_MAX;
      return norm > 1.0f ? 1.0f : norm;
    }
  }
  return 0.0f;
}

// ── Leitura MPU com offset removido ──────────────────────────────────────
float lerMovimento() {
  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);
  float raw = fabs(sqrt(
    a.acceleration.x * a.acceleration.x +
    a.acceleration.y * a.acceleration.y +
    a.acceleration.z * a.acceleration.z
  ) - 9.8f);
  float corrigido = raw - movOffset;
  return corrigido < 0.0f ? 0.0f : corrigido;
}

// ── Calibração MPU no boot ────────────────────────────────────────────────
void calibrarMPU() {
  Serial.print("[CAL] Calibrando MPU6050 (mantenha parado)");
  float soma = 0.0f;
  for (int i = 0; i < CAL_AMOSTRAS; i++) {
    sensors_event_t a, g, temp;
    mpu.getEvent(&a, &g, &temp);
    soma += fabs(sqrt(
      a.acceleration.x * a.acceleration.x +
      a.acceleration.y * a.acceleration.y +
      a.acceleration.z * a.acceleration.z
    ) - 9.8f);
    delay(20);
    if (i % 10 == 9) Serial.print(".");
  }
  movOffset = soma / CAL_AMOSTRAS;
  Serial.println();
  Serial.print("[CAL] Offset: ");
  Serial.println(movOffset, 4);
}

// ── Setup ─────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("================================");
  Serial.println("  SOPHIA oo MVP - Boot v1.0.0  ");
  Serial.println("================================");

  Wire.begin(21, 22);
  Serial.print("[DISPLAY] OLED... ");
  display.begin() ? Serial.println("OK") : Serial.println("ERRO!");
  display.showBoot();
  delay(800);

  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);
  Serial.println("[PIEZO]  GPIO 35 OK");

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

  calibrarMPU();  // zera o ruído de repouso

  Serial.print("[AUDIO]  INMP441... ");
  audio.begin() ? Serial.println("OK") : Serial.println("ERRO!");

  telemetry.begin();

  Serial.println("================================");
  Serial.println("[SOPHIA] Sistema nervoso ativo!");
  Serial.println("[STATE]  IDLE");
  Serial.println("================================");
  display.showState("IDLE", 0.0f);
}

// ── Loop ──────────────────────────────────────────────────────────────────
void loop() {
  audio.read();
  float audioIntensidade = audio.getIntensidade();
  bool  audioAtivo       = audio.isAtivo();

  float movIntensidade   = lerMovimento();   // com offset removido
  float piezoIntensidade = lerPiezoNormalizado();

  if (piezoIntensidade > 0.0f) {
    Serial.print("[PIEZO]  impacto=");
    Serial.print(piezoIntensidade, 3);
    Serial.println(piezoIntensidade > 0.7f ? " FORTE" : " LEVE");
  }

  float intensidade = max(movIntensidade, audioIntensidade * 10.0f);
  stateEngine.update(intensidade);

  unsigned long agora = millis();

  if (agora - ultimoLogAudio > 500) {
    Serial.print("[AUDIO]  ativo: ");
    Serial.print(audioAtivo ? "SIM" : "NAO");
    Serial.print(" | int: ");
    Serial.print(audioIntensidade, 2);
    Serial.print(" | mov: ");
    Serial.print(movIntensidade, 3);
    Serial.print(" | state: ");
    Serial.println(stateEngine.getStateName());
    ultimoLogAudio = agora;
  }

  if (agora - ultimoTelemetry > 10000) {
    String tJson = telemetry.toJson();
    Serial.print("[TELEMETRY] ");
    Serial.println(tJson);
    ultimoTelemetry = agora;
  }

  if (eventEngine.process(movIntensidade, audioIntensidade, audioAtivo, piezoIntensidade)) {
    String json = eventEngine.toJson();
    Serial.print("[EVENT]  ");
    Serial.println(json);

    SophiaEvent ev = eventEngine.getLast();
    display.showState(stateEngine.getStateName(), ev.severity);

    if (ev.type == EVENT_STATE_CHANGED || ev.type == EVENT_IMPACT_STRONG) {
      display.showEvent(stateEngine.getStateName());
      delay(800);
      display.showState(stateEngine.getStateName(), ev.severity);
    }
  }
}
