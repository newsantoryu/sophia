#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define OLED_WIDTH  128
#define OLED_HEIGHT  64
#define OLED_ADDR  0x3C

class DisplayEngine {
public:
  bool begin();
  void showBoot();
  void showState(const char* state, float severity);
  void showEvent(const char* event);
  void showIP(const char* ip);
  void showError(const char* msg);

private:
  Adafruit_SSD1306 _display{OLED_WIDTH, OLED_HEIGHT, &Wire, -1};
  void _header(const char* title);
};
