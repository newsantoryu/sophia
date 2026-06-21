#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include "StateEngine.h"

enum EventType {
  EVENT_NONE,
  EVENT_MOVEMENT_SPIKE,
  EVENT_MOVEMENT_GENTLE,
  EVENT_STATE_CHANGED,
  EVENT_ALERT_TRIGGERED,
  EVENT_AUDIO_ACTIVE
};

struct SophiaEvent {
  EventType     type;
  float         severity;
  const char*   state;
  unsigned long timestamp;
  float         audioIntensidade;
  float         movIntensidade;
  float         bmpTemp;
};

class EventEngine {
public:
  EventEngine(StateEngine& stateEngine);

  bool process(float movIntensidade,
               float audioIntensidade,
               bool audioAtivo,
               float bmpTemp = 0.0f);

  SophiaEvent getLast();
  String toJson();

private:
  StateEngine& _state;
  SophiaEvent  _last;
  float        _normalize(float v, float max);
};