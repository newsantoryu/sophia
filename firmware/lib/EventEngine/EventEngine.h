#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include "StateEngine.h"

enum EventType {
  EVENT_NONE,
  EVENT_MOVEMENT_SPIKE,
  EVENT_MOVEMENT_GENTLE,
  EVENT_STATE_CHANGED,
  EVENT_ALERT_TRIGGERED
};

struct SophiaEvent {
  EventType   type;
  float       severity;
  const char* state;
  unsigned long timestamp;
};

class EventEngine {
public:
  EventEngine(StateEngine& stateEngine);
  bool process(float intensidade);
  SophiaEvent getLast();
  String toJson();

private:
  StateEngine&  _state;
  SophiaEvent   _last;
  float         _normalize(float intensidade);
};
