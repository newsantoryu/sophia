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
  EVENT_AUDIO_ACTIVE,
  EVENT_IMPACT,        // impacto piezo leve/médio
  EVENT_IMPACT_STRONG  // impacto piezo forte
};

struct SophiaEvent {
  EventType     type;
  float         severity;
  const char*   state;
  unsigned long timestamp;
  float         audioIntensidade;
  float         movIntensidade;
  float         piezoIntensidade;  // 0.0–1.0 normalizado
};

class EventEngine {
public:
  EventEngine(StateEngine& stateEngine);

  // piezoIntensidade: valor ADC normalizado 0.0–1.0 (passe 0 se sem piezo)
  bool process(float movIntensidade, float audioIntensidade, bool audioAtivo,
               float piezoIntensidade = 0.0f);

  SophiaEvent getLast();
  String toJson();

private:
  StateEngine& _state;
  SophiaEvent  _last;
  float        _normalize(float v, float max);
};