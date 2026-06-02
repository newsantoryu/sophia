#include "DisplayEngine.h"

bool DisplayEngine::begin() {
  if (!_display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
    Serial.println("[DISPLAY] ERRO: SSD1306 nao encontrado!");
    return false;
  }
  _display.clearDisplay();
  _display.setTextColor(SSD1306_WHITE);
  _display.setTextWrap(false);
  showBoot();
  return true;
}

void DisplayEngine::_header(const char* title) {
  _display.fillRect(0, 0, OLED_WIDTH, 12, SSD1306_WHITE);
  _display.setTextColor(SSD1306_BLACK);
  _display.setTextSize(1);
  _display.setCursor(2, 2);
  _display.print(title);
  _display.setTextColor(SSD1306_WHITE);
}

void DisplayEngine::showBoot() {
  _display.clearDisplay();
  _header("SOPHIA oo MVP");
  _display.setTextSize(1);
  _display.setCursor(0, 18);
  _display.println("Sistema Nervoso");
  _display.setCursor(0, 30);
  _display.println("Cognitivo Embarcado");
  _display.setCursor(0, 48);
  _display.println("Inicializando...");
  _display.display();
}

void DisplayEngine::showState(const char* state, float severity) {
  _display.clearDisplay();
  _header("SOPHIA oo ESTADO");
  _display.setTextSize(2);
  _display.setCursor(0, 18);
  _display.println(state);
  _display.setTextSize(1);
  _display.setCursor(0, 42);
  _display.print("Intensidade: ");
  _display.print(severity, 2);
  float sev = severity < 0.0f ? 0.0f : (severity > 1.0f ? 1.0f : severity);
  int barW = (int)(sev * OLED_WIDTH);
  _display.fillRect(0, 56, barW, 6, SSD1306_WHITE);
  _display.display();
}

void DisplayEngine::showEvent(const char* event) {
  _display.clearDisplay();
  _header("SOPHIA oo EVENTO");
  _display.setTextSize(1);
  _display.setCursor(0, 16);
  _display.println(event);
  _display.display();
}

void DisplayEngine::showIP(const char* ip) {
  _display.clearDisplay();
  _header("SOPHIA oo REDE");
  _display.setTextSize(1);
  _display.setCursor(0, 18);
  _display.println("WiFi conectado!");
  _display.setCursor(0, 32);
  _display.println("IP:");
  _display.setCursor(0, 44);
  _display.println(ip);
  _display.display();
}

void DisplayEngine::showError(const char* msg) {
  _display.clearDisplay();
  _header("ERRO");
  _display.setTextSize(1);
  _display.setCursor(0, 18);
  _display.println(msg);
  _display.display();
}

// ── NOVO: exibe insight do Qwen no OLED ───────────────────────────────────
void DisplayEngine::showInsight(const char* linha1, const char* linha2) {
  _display.clearDisplay();
  _header("SOPHIA oo INSIGHT");
  _display.setTextSize(1);
  _display.setTextWrap(true);   // wrap para textos longos

  _display.setCursor(0, 16);
  _display.println(linha1);

  if (linha2 && strlen(linha2) > 0) {
    _display.setCursor(0, 40);
    _display.println(linha2);
  }

  _display.setTextWrap(false);
  _display.display();
}