#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>

class NetworkEngine {
public:
  NetworkEngine(const char* ssid, const char* password, const char* broker);
  void begin();
  void loop();
  bool publish(const char* topic, const String& payload);
  bool connected();

private:
  const char* _ssid;
  const char* _password;
  const char* _broker;
  WiFiClient  _wifiClient;
  PubSubClient _mqtt;
  void _connectWifi();
  void _connectMqtt();
};
