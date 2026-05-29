#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <ArduinoJson.h>

class TelemetryEngine {
public:
  void begin();
  void loop(unsigned long intervalo = 10000);
  String toJson();

private:
  unsigned long _ultimoEnvio;
};
