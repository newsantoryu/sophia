#include "NetworkEngine.h"

NetworkEngine::NetworkEngine(const char* ssid, const char* password, const char* broker)
  : _ssid(ssid), _password(password), _broker(broker), _mqtt(_wifiClient) {}

void NetworkEngine::begin() {
  _mqtt.setServer(_broker, 1883);
  _mqtt.setBufferSize(512);
  _connectMqtt();
}

void NetworkEngine::loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[NET] WiFi perdido!");
    ESP.restart();
  }
  if (!_mqtt.connected()) {
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

void NetworkEngine::_connectWifi() {}

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
      if (++tentativas > 5) ESP.restart();
    }
  }
}
