# SOPHIA ∞ — Sistema Cognitivo Híbrido

> *"Inteligência não é algoritmo. É relacionamento entre percepção, contexto e adaptação."*

Sistema nervoso cognitivo embarcado que percebe o ambiente físico, interpreta padrões, decide ações e age — tudo com IA local, sem dependência de nuvem.

---

## Visão Geral

```
ESP32 (corpo físico)          PC Local (cérebro)
┌─────────────────────┐       ┌──────────────────────────┐
│ MPU6050  → movimento│       │ Observer Engine           │
│ INMP441  → áudio    │──USB──│ ↓                        │
│ Piezo    → vibração │Serial │ Qwen2.5-Coder (Ollama)   │
│ OLED     ← feedback │       │ ↓                        │
└─────────────────────┘       │ Insight → OLED do ESP32  │
                              └──────────────────────────┘
```

**Ciclo cognitivo:**
```
PERCEBER → INTERPRETAR → DECIDIR → AGIR → APRENDER
sensores    Observer       Qwen     OLED    SQLite
```

---

## Hardware

| Módulo | Função | Pinos |
|---|---|---|
| ESP32 DevKit | Microcontrolador principal | — |
| MPU6050 | Acelerômetro + giroscópio | SDA=32, SCL=33 |
| INMP441 | Microfone I2S | WS=25, SCK=26, SD=34 |
| Piezo | Sensor de vibração/impacto | GPIO 35 (ADC) |
| OLED SSD1306 | Display 128x64 | SDA=21, SCL=22 |

---

## Arquitetura do Firmware

```
firmware/src/main.cpp
firmware/lib/
├── StateEngine/      — estados: IDLE, ACTIVE, ALERT, RECOVERY
├── EventEngine/      — 7 tipos de evento + piezo integrado
├── DisplayEngine/    — OLED + showInsight() para feedback do Qwen
├── AudioEngine/      — INMP441 com calibração automática de noise floor
└── TelemetryEngine/  — uptime, heap, rssi em JSON
```

### Protocolo Serial bidirecional

O ESP32 comunica com o PC via USB Serial (115200 baud):

**ESP32 → PC** (eventos):
```
[EVENT]     {"event":"MOVEMENT_SPIKE","severity":0.38,"state":"ACTIVE",...}
[TELEMETRY] {"uptime":120,"heap":333124,"rssi":0,"ip":"0.0.0.0"}
[PIEZO]     impacto=0.318 LEVE
```

**PC → ESP32** (comandos):
```
CMD:INSIGHT:!! ALERTA CRITICO|Reduza a agitação\n
CMD:OLED:Sistema estavel\n
CMD:PING:\n  →  [ACK] PONG
```

---

## Arquitetura do Core Python

```
core/
├── sophia_core.py          — entry point principal
└── sophia/
    ├── parser.py           — classifica linhas do Serial por tipo
    ├── serial_reader.py    — leitura bidirecional + reconexão automática
    ├── database.py         — SQLite: events_v2, telemetry_v2, sessions
    ├── sessions.py         — isolamento por sessão (detecta reboot pelo uptime)
    ├── observer.py         — análise temporal, padrões, métricas
    ├── qwen_bridge.py      — integração Ollama qwen2.5-coder:7b
    └── command_sender.py   — envia comandos ao ESP32
```

### Engines do Core

| Engine | Responsabilidade |
|---|---|
| `SerialReader` | Lê Serial, despacha por tipo, watchdog 30s |
| `SessionEngine` | Detecta reboot pelo uptime, isola sessões no banco |
| `ObserverEngine` | Analisa janela temporal, calcula nível/padrão/tendência |
| `QwenBridge` | Formata prompt, chama Ollama, parseia resposta JSON |
| `CognitiveCycle` | Thread periódica: Observer → Qwen → OLED |
| `CommandSender` | Envia `CMD:*` ao ESP32 via Serial |

---

## Instalação

### Firmware
```bash
cd firmware
pio run --target upload
```

### Core Python
```bash
cd core
python3 -m venv .venv
source .venv/bin/activate
pip install pyserial
python3 sophia_core.py --port /dev/ttyACM0 --ciclo 30
```

### Dependências locais
- [PlatformIO](https://platformio.org/)
- [Ollama](https://ollama.ai/) com `ollama pull qwen2.5-coder:7b`

---

## Uso

```bash
# Modo completo: Serial + Observer + Qwen
python3 sophia_core.py --port /dev/ttyACM0 --ciclo 60

# Análise rápida da sessão atual
python3 sophia_core.py --observe

# Sem IA (modo offline)
python3 sophia_core.py --no-qwen

# Consulta banco
python3 sophia_core.py --query

# Lista portas disponíveis
python3 sophia_core.py --list
```

---

## Calibrações automáticas no boot

```
[CAL] Calibrando MPU6050 (mantenha parado).....
[CAL] Offset MPU: 0.4923

[AUDIO]  Calibrando noise floor..................................................
[AUDIO]  Noise floor: 342.5
```

O sistema mede o ruído de fundo de cada sensor nas primeiras amostras e subtrai automaticamente — zero falsos positivos em repouso.

---

## Resultados de sessão (exemplo real)

```
[SES] ── Nova sessão #10 (boot #1) ──────────────
[COG] Observer: 180 eventos | nível=CRITICO | padrão=CRITICO
[COG] Consultando Qwen...

  ╔═ SOPHIA INSIGHT ═════════════════════════════╗
  ║ Nível   : CRITICO
  ║ Padrão  : CRITICO
  ║ Insight : Ambiente em estado de alerta crítico, com alta intensidade.
  ║ Sugestão: Reduza a agitação ou verifique fontes de perturbação.
  ║ OLED    : [ALERTA CRÍTICO - Red]
  ╚══════════════════════════════════════════════╝

[CMD] Insight enviado ao OLED: [ALERTA CRÍTICO - Red]
Stats: {events: 180, telemetry: 10, states: 16, errors: 0, reconnects: 0, sessions: 1, commands_sent: 4}
```

---

## Roadmap — 90 dias

| Fase | Status | Entrega |
|---|---|---|
| 1 — Infraestrutura | ✅ | VSCode, PlatformIO, Ollama, Git |
| 2 — Sistema Nervoso | ✅ | MPU6050, EventEngine, StateEngine, OLED |
| 3 — Percepção Multimodal | ✅ | INMP441 calibrado, Piezo integrado |
| 4 — Homeostasis | ✅ | Calibração automática, watchdog, sessões |
| 5 — Sophia Local Core | ✅ | Parser, SQLite, Observer, Qwen, OLED feedback |
| 6 — IA Multiplicadora | 🔄 | Geração de firmware ESP32, análise de logs |

---

## Princípios de Engenharia

1. **Hardware primeiro** — sem abstração sem validação física
2. **Eventos > polling** — o sistema reage, não varre
3. **Calibração automática** — zero configuração manual de threshold
4. **Offline first** — funciona sem WiFi, sem nuvem
5. **Modularidade** — cada engine tem responsabilidade única

---

## Missão

> Ser a ponte entre você e a luz da inteligência que já existe dentro e ao seu redor.
> Servir, proteger e evoluir com você.

**SOPHIA ∞ — A Inteligência que Conecta**