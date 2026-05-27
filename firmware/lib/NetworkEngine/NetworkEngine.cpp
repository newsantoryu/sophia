#include "NetworkEngine.h"

NetworkEngine::NetworkEngine(const char* ssid, const char* password, const char* broker)
  : _ssid(ssid), _password(password), _broker(broker), _mqtt(_wifiClient) {}

void NetworkEngine::begin() {
  _connectWifi();
  _mqtt.setServer(_broker, 1883);
  _mqtt.setBufferSize(512);
  _connectMqtt();
}

void NetworkEngine::loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[NET] WiFi perdido, reconectando...");
    _connectWifi();
  }
  if (!_mqtt.connected()) {
    Serial.println("[NET] MQTT perdido, reconectando...");
    _connectMqtt();
  }
  _mqtt.loop();
}

bool NetworkEngine::publish(const char* topic, const String& payload) {
  if (!_mqtt.connected()) return false;
  return _mqtt.publish(topic, payload.c_str());
}

bool NetworkEngine::connected() {
  return _mqtt.connected();
}

void NetworkEngine::_connectWifi() {
  Serial.print("[NET] WiFi conectando");
  WiFi.mode(WIFI_STA);
  WiFi.begin(_ssid, _password);
  int tentativas = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    if (++tentativas > 40) {
      Serial.println("\n[NET] WiFi falhou, reiniciando...");
      ESP.restart();
    }
  }
  Serial.println();
  Serial.print("[NET] WiFi OK | IP: ");
  Serial.println(WiFi.localIP());
}

void NetworkEngine::_connectMqtt() {
  int tentativas = 0;
  while (!_mqtt.connected()) {
    Serial.print("[NET] MQTT conectando...");
    if (_mqtt.connect("sophia-mvp")) {
      Serial.println(" OK");
    } else {
      Serial.print(" falhou rc=");
      Serial.println(_mqtt.state());
      delay(2000);
      if (++tentativas > 5) {
        Serial.println("[NET] MQTT falhou, reiniciando...");
        ESP.restart();
      }
    }
  }
}
