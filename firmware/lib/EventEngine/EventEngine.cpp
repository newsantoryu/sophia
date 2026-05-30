#include "EventEngine.h"

EventEngine::EventEngine(StateEngine& stateEngine)
  : _state(stateEngine) {
  _last = { EVENT_NONE, 0.0f, "IDLE", 0, 0.0f, 0.0f, 0.0f };
}

bool EventEngine::process(float movIntensidade, float audioIntensidade,
                          bool audioAtivo, float piezoIntensidade) {
  bool gerou = false;
  unsigned long agora = millis();

  float intensidade = max(movIntensidade, audioIntensidade * 10.0f);

  // ── Piezo tem prioridade máxima — impacto físico direto ────────────────
  // piezoIntensidade já vem normalizado 0.0–1.0
  // forte: >0.7  |  leve: >0.2
  if (piezoIntensidade > 0.7f) {
    _last = {
      EVENT_IMPACT_STRONG,
      piezoIntensidade,
      _state.getStateName(),
      agora,
      audioIntensidade,
      movIntensidade,
      piezoIntensidade
    };
    // Impacto forte também alimenta o StateEngine com intensidade alta
    _state.update(piezoIntensidade * 15.0f);
    return true;
  }

  if (piezoIntensidade > 0.2f) {
    _last = {
      EVENT_IMPACT,
      piezoIntensidade,
      _state.getStateName(),
      agora,
      audioIntensidade,
      movIntensidade,
      piezoIntensidade
    };
    _state.update(piezoIntensidade * 8.0f);
    return true;
  }

  // ── Fluxo normal (mov + audio) ─────────────────────────────────────────
  if (_state.mudou()) {
    _last = { EVENT_STATE_CHANGED, _normalize(intensidade, 15.0f),
              _state.getStateName(), agora, audioIntensidade, movIntensidade, 0.0f };
    gerou = true;
  } else if (intensidade >= 7.0f) {
    _last = { EVENT_ALERT_TRIGGERED, _normalize(intensidade, 15.0f),
              _state.getStateName(), agora, audioIntensidade, movIntensidade, 0.0f };
    gerou = true;
  } else if (intensidade >= 4.0f) {
    _last = { EVENT_MOVEMENT_SPIKE, _normalize(intensidade, 15.0f),
              _state.getStateName(), agora, audioIntensidade, movIntensidade, 0.0f };
    gerou = true;
  } else if (intensidade >= 2.5f) {
    _last = { EVENT_MOVEMENT_GENTLE, _normalize(intensidade, 15.0f),
              _state.getStateName(), agora, audioIntensidade, movIntensidade, 0.0f };
    gerou = true;
  } else if (audioAtivo) {
    _last = { EVENT_AUDIO_ACTIVE, audioIntensidade,
              _state.getStateName(), agora, audioIntensidade, movIntensidade, 0.0f };
    gerou = true;
  }

  return gerou;
}

SophiaEvent EventEngine::getLast() {
  return _last;
}

String EventEngine::toJson() {
  DynamicJsonDocument doc(512);

  switch (_last.type) {
    case EVENT_MOVEMENT_SPIKE:   doc["event"] = "MOVEMENT_SPIKE";   break;
    case EVENT_MOVEMENT_GENTLE:  doc["event"] = "MOVEMENT_GENTLE";  break;
    case EVENT_STATE_CHANGED:    doc["event"] = "STATE_CHANGED";    break;
    case EVENT_ALERT_TRIGGERED:  doc["event"] = "ALERT_TRIGGERED";  break;
    case EVENT_AUDIO_ACTIVE:     doc["event"] = "AUDIO_ACTIVE";     break;
    case EVENT_IMPACT:           doc["event"] = "IMPACT";           break;
    case EVENT_IMPACT_STRONG:    doc["event"] = "IMPACT_STRONG";    break;
    default:                     doc["event"] = "NONE";             break;
  }

  doc["severity"]  = _last.severity;
  doc["state"]     = _last.state;
  doc["timestamp"] = _last.timestamp;
  doc["audio"]     = _last.audioIntensidade;
  doc["mov"]       = _last.movIntensidade;
  doc["piezo"]     = _last.piezoIntensidade;

  String output;
  serializeJson(doc, output);
  return output;
}

float EventEngine::_normalize(float v, float max) {
  float n = v / max;
  return n > 1.0f ? 1.0f : n;
}
