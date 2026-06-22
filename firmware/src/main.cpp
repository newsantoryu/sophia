#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include "StateEngine.h"
#include "EventEngine.h"
#include "DisplayEngine.h"
#include "AudioEngine.h"
#include "TelemetryEngine.h"
#include <Adafruit_BMP085.h>

//coração
#define ECG_PIN   34   // ADC bom e livre


// ── MPU calibração ────────────────────────────────────────────────────────
#define CAL_AMOSTRAS  50
float movOffset = 0.0f;

// ── Objetos ───────────────────────────────────────────────────────────────
Adafruit_MPU6050 mpu;
StateEngine      stateEngine;
EventEngine      eventEngine(stateEngine);
DisplayEngine    display;
AudioEngine      audio;
TelemetryEngine  telemetry;
Adafruit_BMP085 bmp;
bool bmpDisponivel = false;

unsigned long ultimoLogAudio  = 0;
unsigned long ultimoTelemetry = 0;
unsigned long ultimoImpacto   = 0;

float g_temp = 0.0f;
float g_press = 0.0f;
float g_alt = 0.0f;

bool displayLockedByEvent = false;

unsigned long lastOledUpdate = 0;
float lastTempShown = -100.0f;

bool oledBusy = false;
String lastState = "";
// ── Comando Serial vindo do PC ────────────────────────────────────────────
// Protocolo: CMD:<tipo>:<payload>\n
// Exemplos:
//   CMD:INSIGHT:Ambiente calmo|Sistema estavel
//   CMD:OLED:ALERTA CRITICO
//   CMD:STATE:ALERT
String serialBuffer = "";


float baseline = 0;
float filteredECG = 0;


void processarComando(const String& linha) {
  if (!linha.startsWith("CMD:")) return;

  // Parse: CMD:<tipo>:<payload>
  int p1 = linha.indexOf(':', 4);
  if (p1 < 0) return;

  String tipo    = linha.substring(4, p1);
  String payload = linha.substring(p1 + 1);
  payload.trim();

  Serial.print("[CMD] tipo=");
  Serial.print(tipo);
  Serial.print(" payload=");
  Serial.println(payload);

  if (tipo == "INSIGHT") {
    // payload: "linha1|linha2"
    int sep = payload.indexOf('|');
    if (sep >= 0) {
      String l1 = payload.substring(0, sep);
      String l2 = payload.substring(sep + 1);
      display.showInsight(l1.c_str(), l2.c_str());
    } else {
      display.showInsight(payload.c_str());
    }
    delay(4000);  // mostra por 4s depois volta ao estado normal
    display.showState(stateEngine.getStateName(), 0.0f);

  } else if (tipo == "OLED") {
    // payload: mensagem direta
    display.showInsight(payload.c_str());
    delay(3000);
    display.showState(stateEngine.getStateName(), 0.0f);

  } else if (tipo == "PING") {
    Serial.println("[ACK] PONG");
  }
}

void lerComandosSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      serialBuffer.trim();
      if (serialBuffer.length() > 0) {
        processarComando(serialBuffer);
      }
      serialBuffer = "";
    } else {
      serialBuffer += c;
    }
  }
}

void updateOledIdle(float temp) {
    if (oledBusy) return;

    if (millis() - lastOledUpdate < 1000) return;

    if (fabs(temp - lastTempShown) < 0.2f) return;

    lastOledUpdate = millis();
    lastTempShown = temp;

    char buffer[32];
    snprintf(buffer, sizeof(buffer),
             "IDLE %.1fC", temp);

    display.showState(buffer, 0.0f);
}


// ── BMP  ─────────────────────────────────────────────────────────
void readBMP(float &temp, float &press, float &alt) {
  if (!bmpDisponivel) {
    temp = 0;
    press = 0;
    alt = 0;
    return;
  }

  temp = bmp.readTemperature();
  press = bmp.readPressure() / 100.0f;
  alt = bmp.readAltitude();
}

// ── MPU calibrado ─────────────────────────────────────────────────────────
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
  Serial.print("[CAL] Offset MPU: ");
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
  Wire.setClock(100000);
  Serial.print("[DISPLAY] OLED... ");
  display.begin() ? Serial.println("OK") : Serial.println("ERRO!");
  display.showBoot();
  delay(800);

  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);

  long sum = 0;

for(int i = 0; i < 500; i++) {
    sum += analogRead(ECG_PIN);
    delay(2);
}

baseline = sum / 500.0;

Serial.print("Baseline ECG: ");
Serial.println(baseline);

Serial.print("[BMP] init... ");

bmpDisponivel = bmp.begin(BMP085_STANDARD, &Wire);

if (bmpDisponivel) {
  Serial.println("OK");
} else {
  Serial.println("OFFLINE");
}

  Serial.print("[SENSOR] MPU6050... ");
  if (!mpu.begin(0x68)) {
    Serial.println("ERRO!");
    display.showError("MPU6050 falhou!");
    while (true) { delay(500); }
  }
  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);

  calibrarMPU();

  Serial.print("[AUDIO]  INMP441... ");
  audio.begin() ? Serial.println("OK") : Serial.println("ERRO!");
  Serial.print("[AUDIO]  Calibrando noise floor");
  while (!audio.isCalibrado()) {
    audio.read();
    Serial.print(".");
    delay(50);
  }
  Serial.println();
  Serial.print("[AUDIO]  Noise floor: ");
  Serial.println(audio.getNoiseFloor(), 1);

  telemetry.begin();

  Serial.println("================================");
  Serial.println("[SOPHIA] Sistema nervoso ativo!");
  Serial.println("[CMD]    Aguardando comandos PC");
  Serial.println("[STATE]  IDLE");
  Serial.println("================================");
  display.showState("IDLE", 0.0f);
}
void handleStateDisplay(String currentState, float temp) {

    if (currentState != lastState) {
        lastState = currentState;

        // força redraw ao mudar estado
        lastTempShown = -999;
        lastOledUpdate = 0;
    }

    if (currentState == "IDLE") {
        updateOledIdle(temp);
    }
}
// ── Loop ──────────────────────────────────────────────────────────────────
void loop() {
  // Comandos do PC têm prioridade máxima
  lerComandosSerial();

int raw = analogRead(ECG_PIN);

// baseline adaptativo leve
baseline = (baseline * 0.99) + (raw * 0.01);

// remove offset
float ecg = raw - baseline;

// low pass
filteredECG = (filteredECG * 0.95) + (ecg * 0.05);

Serial.print("ECG: ");
Serial.println(filteredECG);

  audio.read();
  float audioIntensidade = audio.getIntensidade();
  bool  audioAtivo       = audio.isAtivo();

  float movIntensidade   = lerMovimento();

  float temp, press, alt;


float envFactor = 0.0f;

if (bmpDisponivel) {
  // pressão influencia “stress do ambiente”
  envFactor += (press - 1000.0f) * 0.001f;

  // temperatura influencia conforto
  envFactor += (25.0f - temp) * 0.02f;
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

    if (bmpDisponivel) {
  Serial.print(" | BMP temp=");
  Serial.print(temp);

  Serial.print(" press=");
  Serial.print(press);

  Serial.print(" env=");
  Serial.print(envFactor);
}
  }

  if (agora - ultimoTelemetry > 10000) {
    String tJson = telemetry.toJson();
    Serial.print("[TELEMETRY] ");
    Serial.println(tJson);
    ultimoTelemetry = agora;
  }

if (eventEngine.process(movIntensidade, audioIntensidade, audioAtivo)) {

    oledBusy = true;

    SophiaEvent ev = eventEngine.getLast();

    display.showState(stateEngine.getStateName(), ev.severity);

    if (ev.type == EVENT_STATE_CHANGED) {
        display.showEvent(stateEngine.getStateName());
        display.showState(stateEngine.getStateName(), ev.severity);
    }

    lastOledUpdate = millis() + 800; // bloqueia refresh por um tempo
    oledBusy = false;
} 
readBMP(g_temp, g_press, g_alt);
handleStateDisplay(stateEngine.getStateName(), g_temp);

}