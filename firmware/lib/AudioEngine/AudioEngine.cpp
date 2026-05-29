#include "AudioEngine.h"

bool AudioEngine::begin() {
  i2s_config_t config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = 16000,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_RIGHT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .dma_buf_count = 4,
    .dma_buf_len = 128
  };

  i2s_pin_config_t pins = {
    .bck_io_num   = I2S_SCK,
    .ws_io_num    = I2S_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num  = I2S_SD
  };

  if (i2s_driver_install(I2S_PORT, &config, 0, NULL) != ESP_OK) return false;
  if (i2s_set_pin(I2S_PORT, &pins) != ESP_OK) return false;

  _envelope    = 0;
  _dynamicMax  = 100;
  _intensidade = 0;
  _ativo       = false;

  return true;
}

void AudioEngine::read() {
  size_t bytesIn = 0;
  i2s_read(I2S_PORT, _buffer, sizeof(_buffer), &bytesIn, portMAX_DELAY);

  int samples = bytesIn / sizeof(int32_t);
  if (samples == 0) return;

  long sum = 0;
  for (int i = 0; i < samples; i++) {
    sum += abs(_buffer[i] >> 16);
  }

  float amp = (float)sum / samples;
  _envelope += 0.1f * (amp - _envelope);

  if (_envelope > _dynamicMax) _dynamicMax = _envelope;
  _dynamicMax *= 0.999f;

  float norm = (_dynamicMax > 0) ? _envelope / _dynamicMax : 0;
  _intensidade = norm;
  _ativo = norm > 0.3f;
}

float AudioEngine::getIntensidade() { return _intensidade; }
bool  AudioEngine::isAtivo()        { return _ativo; }
