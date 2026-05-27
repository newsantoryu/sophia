#include "StateEngine.h"

StateEngine::StateEngine() {
  _atual         = STATE_IDLE;
  _anterior      = STATE_IDLE;
  _ultimoEvento  = 0;
  _entradaRecovery = 0;
}

void StateEngine::update(float intensidade) {
  _anterior = _atual;
  unsigned long agora = millis();

  switch (_atual) {

    case STATE_IDLE:
      if (intensidade > 2.5f) {
        _atual = STATE_ACTIVE;
        _ultimoEvento = agora;
      }
      break;

    case STATE_ACTIVE:
      if (intensidade > 7.0f) {
        _atual = STATE_ALERT;
        _ultimoEvento = agora;
      } else if (agora - _ultimoEvento > 3000) {
        _atual = STATE_RECOVERY;
        _entradaRecovery = agora;
      } else if (intensidade > 2.5f) {
        _ultimoEvento = agora;
      }
      break;

    case STATE_ALERT:
      if (agora - _ultimoEvento > 3000) {
        _atual = STATE_RECOVERY;
        _entradaRecovery = agora;
      } else if (intensidade > 2.5f) {
        _ultimoEvento = agora;
      }
      break;

    case STATE_RECOVERY:
      if (agora - _entradaRecovery > 2000) {
        _atual = STATE_IDLE;
      }
      break;
  }
}

SophiaState StateEngine::getState() {
  return _atual;
}

const char* StateEngine::getStateName() {
  switch (_atual) {
    case STATE_IDLE:     return "IDLE";
    case STATE_ACTIVE:   return "ACTIVE";
    case STATE_ALERT:    return "ALERT";
    case STATE_RECOVERY: return "RECOVERY";
    default:             return "UNKNOWN";
  }
}

bool StateEngine::mudou() {
  return _atual != _anterior;
}
