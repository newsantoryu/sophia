#include "EventEngine.h"

EventEngine::EventEngine(StateEngine& stateEngine)
  : _state(stateEngine) {
  _last = { EVENT_NONE, 0.0f, "IDLE", 0 };
}

bool EventEngine::process(float intensidade) {
  bool gerou = false;

  if (_state.mudou()) {
    _last = { EVENT_STATE_CHANGED, _normalize(intensidade), _state.getStateName(), millis() };
    gerou = true;
  } else if (intensidade >= 7.0f) {
    _last = { EVENT_ALERT_TRIGGERED, _normalize(intensidade), _state.getStateName(), millis() };
    gerou = true;
  } else if (intensidade >= 4.0f) {
    _last = { EVENT_MOVEMENT_SPIKE, _normalize(intensidade), _state.getStateName(), millis() };
    gerou = true;
  } else if (intensidade >= 2.5f) {
    _last = { EVENT_MOVEMENT_GENTLE, _normalize(intensidade), _state.getStateName(), millis() };
    gerou = true;
  }

  return gerou;
}

SophiaEvent EventEngine::getLast() {
  return _last;
}

String EventEngine::toJson() {
  DynamicJsonDocument doc(256);

  switch (_last.type) {
    case EVENT_MOVEMENT_SPIKE:   doc["event"] = "MOVEMENT_SPIKE";   break;
    case EVENT_MOVEMENT_GENTLE:  doc["event"] = "MOVEMENT_GENTLE";  break;
    case EVENT_STATE_CHANGED:    doc["event"] = "STATE_CHANGED";    break;
    case EVENT_ALERT_TRIGGERED:  doc["event"] = "ALERT_TRIGGERED";  break;
    default:                     doc["event"] = "NONE";             break;
  }

  doc["severity"]  = _last.severity;
  doc["state"]     = _last.state;
  doc["timestamp"] = _last.timestamp;

  String output;
  serializeJson(doc, output);
  return output;
}

float EventEngine::_normalize(float intensidade) {
  float v = intensidade / 15.0f;
  return v > 1.0f ? 1.0f : v;
}
