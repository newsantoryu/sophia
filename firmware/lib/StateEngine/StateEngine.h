#pragma once
#include <Arduino.h>

enum SophiaState {
  STATE_IDLE,
  STATE_ACTIVE,
  STATE_ALERT,
  STATE_RECOVERY
};

class StateEngine {
public:
  StateEngine();
  void update(float intensidade);
  SophiaState getState();
  const char* getStateName();
  bool mudou();

private:
  SophiaState _atual;
  SophiaState _anterior;
  unsigned long _ultimoEvento;
  unsigned long _entradaRecovery;
};
