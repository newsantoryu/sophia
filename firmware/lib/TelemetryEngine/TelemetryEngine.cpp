#include "TelemetryEngine.h"

void TelemetryEngine::begin() {
  _ultimoEnvio = 0;
}

void TelemetryEngine::loop(unsigned long intervalo) {
  // publicação controlada pelo main
}

String TelemetryEngine::toJson() {
  DynamicJsonDocument doc(256);

  doc["uptime"]    = millis() / 1000;
  doc["heap"]      = ESP.getFreeHeap();
  doc["rssi"]      = WiFi.RSSI();
  doc["ip"]        = WiFi.localIP().toString();

  String output;
  serializeJson(doc, output);
  return output;
}
