#pragma once
#include <Arduino.h>
#include <driver/i2s.h>

#define I2S_WS   25
#define I2S_SCK  26
#define I2S_SD   34
#define I2S_PORT I2S_NUM_0
#define AUDIO_BUFFER_LEN 1024

class AudioEngine {
public:
  bool  begin();
  void  read();
  float getIntensidade();
  bool  isAtivo();
  float getNoiseFloor() { return _noiseFloor; }
  bool  isCalibrado()   { return _calibrado; }

private:
  int32_t _buffer[AUDIO_BUFFER_LEN];
  float   _envelope;
  float   _dynamicMax;
  float   _noiseFloor;    // ruído de fundo calibrado no boot
  float   _intensidade;
  bool    _ativo;

  // Calibração automática
  bool    _calibrado;
  int     _calAmostras;
  float   _calSoma;
};