#include "EventEngine.h"

EventEngine::EventEngine(StateEngine& stateEngine)
  : _state(stateEngine) {
  _last = { EVENT_NONE, 0.0f, "IDLE", 0 };
}

bool EventEngine::process(float intensidade) {
  bool gerou = false;

  if (_state.mudou()) {
    _last.type      = EVENT_STATE_CHANGED;
    _last.severity  = _normalize(intensidade);
    _last.state     = _state.getStateName();
    _last.timestamp = millis();
    gerou = true;
  }
  else if (intensidade >= 7.0f) {
    _last.type      = EVENT_ALERT_TRIGGERED;
    _last.severity  = _normalize(intensidade);
    _last.state     = _state.getStateName();
    _last.timestamp = millis();
    gerou = true;
  }
  else if (intensidade >= 4.0f) {
    _last.type      = EVENT_MOVEMENT_SPIKE;
    _last.severity  = _normalize(intensidade);
    _last.state     = _state.getStateName();
    _last.timestamp = millis();
    gerou = true;
  }
  else if (intensidade >= 2.5f) {
    _last.type      = EVENT_MOVEMENT_GENTLE;
    _last.severity  = _normalize(intensidade);
    _last.state     = _state.getStateName();
    _last.timestamp = millis();
    gerou = true;
  }

  return gerou;
}

SophiaEvent EventEngine::getLast() {
  return _last;
}

String EventEngine::toJson() {
  JsonDocument doc;

  switch (_last.type) {
    case EVENT_MOVEMENT_SPIKE:    doc["event"] = "MOVEMENT_SPIKE";    break;
    case EVENT_MOVEMENT_GENTLE:   doc["event"] = "MOVEMENT_GENTLE";   break;
    case EVENT_STATE_CHANGED:     doc["event"] = "STATE_CHANGED";     break;
    case EVENT_ALERT_TRIGGERED:   doc["event"] = "ALERT_TRIGGERED";   break;
    default:                      doc["event"] = "NONE";              break;
  }

  doc["severity"]  = serialized(String(_last.severity, 2));
  doc["state"]     = _last.state;
  doc["timestamp"] = _last.timestamp;

  String output;
  serializeJson(doc, output);
  return output;
}

float EventEngine::_normalize(float intensidade) {
  float v = intensidade / 15.0f;
  if (v > 1.0f) v = 1.0f;
  return v;
}
