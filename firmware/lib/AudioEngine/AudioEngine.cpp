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
  _noiseFloor  = 0;
  _dynamicMax  = 500;   // FIX: começa maior para não comprimir no início
  _intensidade = 0;
  _ativo       = false;
  _calibrado   = false;
  _calAmostras = 0;
  _calSoma     = 0;

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

  // ── Calibração automática do noise floor nas primeiras 50 amostras ─────
  if (!_calibrado) {
    _calSoma += amp;
    _calAmostras++;
    if (_calAmostras >= 50) {
      _noiseFloor = (_calSoma / _calAmostras) * 1.3f;  // 30% acima do ruído
      _calibrado  = true;
    }
    _intensidade = 0;
    _ativo = false;
    return;
  }

  // Remove noise floor antes de calcular
  float ampLimpa = amp - _noiseFloor;
  if (ampLimpa < 0) ampLimpa = 0;

  // Envelope suavizado sobre amplitude limpa
  _envelope += 0.1f * (ampLimpa - _envelope);

  // FIX: dynamicMax decai mais rápido (0.995 em vez de 0.999)
  // evita que um pico alto comprima tudo por muito tempo
  if (_envelope > _dynamicMax) _dynamicMax = _envelope;
  _dynamicMax *= 0.995f;
  if (_dynamicMax < 50) _dynamicMax = 50;  // mínimo para evitar div por zero

  float norm = _envelope / _dynamicMax;
  if (norm > 1.0f) norm = 1.0f;

  _intensidade = norm;

  // FIX: threshold mais alto (0.5 em vez de 0.3)
  // só marca ativo quando claramente acima do ruído calibrado
  _ativo = norm > 0.5f;
}

float AudioEngine::getIntensidade() { return _intensidade; }
bool  AudioEngine::isAtivo()        { return _ativo; }