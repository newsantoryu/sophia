"""
SOPHIA ∞ — Firmware Engine v0.1
IA Multiplicadora: gera firmware ESP32 a partir de linguagem natural.

Fluxo:
  pedido natural → contexto hardware → prompt estruturado
  → Qwen gera código → valida sintaxe → salva no banco

Capacidades:
  - Gera main.cpp + platformio.ini completos
  - Conhece o hardware atual da SOPHIA (pinos, libs, engines)
  - Valida estrutura do código gerado
  - Salva histórico de firmwares gerados
"""

import json
import re
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from .database import get_conn


# ── Contexto de hardware da SOPHIA ───────────────────────────────────────
# Atualizar conforme novos módulos forem adicionados

SOPHIA_HW_CONTEXT = """
# Hardware disponível na SOPHIA ∞

## ESP32 DevKit V1
- Chip: ESP32-WROOM-32
- Framework: Arduino via PlatformIO
- Board: esp32doit-devkit-v1

## Pinos em uso (NÃO reutilizar)
- GPIO 21, 22 → I2C Wire (OLED SSD1306)
- GPIO 32, 33 → I2C Wire1 (MPU6050)
- GPIO 25, 26, 34 → I2S (INMP441 microfone)
- GPIO 35 → ADC piezo sensor (input only)

## Pinos livres disponíveis
- GPIO 2 (LED onboard), 4, 5, 12, 13, 14, 15
- GPIO 16, 17, 18, 19, 23 (SPI/UART/GPIO)
- GPIO 36, 39 (input only, ADC)

## Bibliotecas já instaladas no projeto
- Adafruit MPU6050 + Adafruit Unified Sensor
- Adafruit SSD1306 + Adafruit GFX
- ArduinoJson @ ^6.21.0
- PubSubClient (MQTT)

## Engines disponíveis para reuso
- StateEngine  — máquina de estados (IDLE/ACTIVE/ALERT/RECOVERY)
- EventEngine  — geração de eventos com severidade
- DisplayEngine — feedback no OLED
- AudioEngine  — leitura INMP441 calibrada
- TelemetryEngine — métricas JSON (uptime/heap/rssi)

## Padrões de código obrigatórios
- Sempre usar millis() para timing (nunca delay() no loop)
- Serial.begin(115200) no setup()
- Logs no formato [MODULE] mensagem
- JSON via ArduinoJson para eventos
- Modularidade: uma responsabilidade por arquivo
"""

SYSTEM_PROMPT_FIRMWARE = """Você é SOPHIA ∞, uma IA especialista em firmware ESP32/Arduino.

Seu trabalho é gerar código C++ completo, funcional e bem estruturado para ESP32.

REGRAS OBRIGATÓRIAS:
1. Gere APENAS código válido — sem explicações fora do JSON
2. Use millis() para timing, nunca delay() no loop principal
3. Serial.begin(115200) sempre no setup()
4. Logs no formato: Serial.println("[MODULE] mensagem")
5. Respeite os pinos em uso informados no contexto
6. Código modular, com comentários claros

Responda SEMPRE em JSON válido com esta estrutura exata:
{
  "nome": "nome_descritivo_do_projeto",
  "descricao": "o que este firmware faz em 1 frase",
  "main_cpp": "código completo do main.cpp",
  "platformio_ini": "conteúdo completo do platformio.ini",
  "libs_novas": ["lib1", "lib2"],
  "pinos_usados": {"GPIO_X": "função"},
  "notas": "observações importantes"
}"""


# ── Resultado da geração ──────────────────────────────────────────────────

@dataclass
class GeneratedFirmware:
    nome:          str
    descricao:     str
    main_cpp:      str
    platformio_ini: str
    libs_novas:    list = field(default_factory=list)
    pinos_usados:  dict = field(default_factory=dict)
    notas:         str  = ""
    pedido:        str  = ""
    gerado_em:     str  = ""
    valido:        bool = False
    erros:         list = field(default_factory=list)


# ── Firmware Engine ───────────────────────────────────────────────────────

class FirmwareEngine:

    def __init__(self, model: str = "qwen2.5-coder:7b",
                 url: str = "http://localhost:11434/api/generate"):
        self.model = model
        self.url   = url

    # ── API pública ───────────────────────────────────────────────────────

    def generate(self, pedido: str,
                 contexto_extra: str = "") -> GeneratedFirmware:
        """
        Gera firmware ESP32 a partir de um pedido em linguagem natural.

        Args:
            pedido: descrição do que o firmware deve fazer
            contexto_extra: informações adicionais opcionais

        Returns:
            GeneratedFirmware com main.cpp, platformio.ini e metadados
        """
        print(f"\n[FW] Gerando firmware: {pedido[:60]}...")

        prompt = self._build_prompt(pedido, contexto_extra)
        raw    = self._call_qwen(prompt)

        if raw is None:
            fw = GeneratedFirmware(
                nome="erro", descricao="Qwen indisponível",
                main_cpp="", platformio_ini="",
                pedido=pedido, gerado_em=datetime.now().isoformat(),
            )
            fw.erros.append("Qwen indisponível")
            return fw

        fw = self._parse_response(raw, pedido)
        fw = self._validar(fw)
        self._salvar(fw)

        return fw

    def list_firmwares(self, limit: int = 10) -> list:
        """Lista firmwares gerados anteriormente."""
        conn = get_conn()
        rows = conn.execute("""
            SELECT id, nome, descricao, pedido, gerado_em, valido
            FROM firmwares
            ORDER BY id DESC LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_firmware(self, fw_id: int) -> dict:
        """Retorna firmware completo por ID."""
        conn = get_conn()
        row = conn.execute(
            "SELECT * FROM firmwares WHERE id = ?", (fw_id,)
        ).fetchone()
        conn.close()
        return dict(row) if row else {}

    # ── Prompt ────────────────────────────────────────────────────────────

    def _build_prompt(self, pedido: str, extra: str = "") -> str:
        prompt = f"{SOPHIA_HW_CONTEXT}\n\n"
        if extra:
            prompt += f"## Contexto adicional\n{extra}\n\n"
        prompt += f"## Pedido\n{pedido}\n\n"
        prompt += "Gere o firmware completo seguindo as regras acima."
        return prompt

    # ── Qwen call ─────────────────────────────────────────────────────────

    def _call_qwen(self, prompt: str,
                   timeout: int = 120) -> str | None:
        payload = json.dumps({
            "model":  self.model,
            "prompt": prompt,
            "system": SYSTEM_PROMPT_FIRMWARE,
            "stream": False,
            "options": {
                "temperature": 0.2,   # baixo: código precisa ser determinístico
                "num_predict": 3000,  # firmwares podem ser longos
            }
        }).encode("utf-8")

        try:
            req = urllib.request.Request(
                self.url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            print(f"[FW] Consultando Qwen (timeout={timeout}s)...")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
                return data.get("response", "")
        except urllib.error.URLError as e:
            print(f"[FW] Qwen indisponível: {e}")
            return None
        except Exception as e:
            print(f"[FW] Erro na chamada: {e}")
            return None

    # ── Parse ─────────────────────────────────────────────────────────────

    def _parse_response(self, raw: str, pedido: str) -> GeneratedFirmware:
        text = raw.strip()

        # Remove markdown fences se presentes
        if "```" in text:
            parts = text.split("```")
            for p in parts:
                p = p.strip()
                if p.startswith("json"):
                    p = p[4:]
                try:
                    data = json.loads(p.strip())
                    return self._dict_to_fw(data, pedido, raw)
                except json.JSONDecodeError:
                    continue

        # Tenta parse direto
        try:
            # Extrai JSON mesmo com texto antes/depois
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                data = json.loads(match.group())
                return self._dict_to_fw(data, pedido, raw)
        except (json.JSONDecodeError, AttributeError):
            pass

        fw = GeneratedFirmware(
            nome="parse_erro", descricao="Não foi possível parsear resposta",
            main_cpp=raw, platformio_ini="",
            pedido=pedido, gerado_em=datetime.now().isoformat(),
        )
        fw.erros.append("JSON inválido na resposta do Qwen")
        return fw

    def _dict_to_fw(self, data: dict, pedido: str, raw: str) -> GeneratedFirmware:
        return GeneratedFirmware(
            nome          = data.get("nome", "firmware_gerado"),
            descricao     = data.get("descricao", ""),
            main_cpp      = data.get("main_cpp", ""),
            platformio_ini = data.get("platformio_ini", ""),
            libs_novas    = data.get("libs_novas", []),
            pinos_usados  = data.get("pinos_usados", {}),
            notas         = data.get("notas", ""),
            pedido        = pedido,
            gerado_em     = datetime.now().isoformat(),
        )

    # ── Validação básica ──────────────────────────────────────────────────

    def _validar(self, fw: GeneratedFirmware) -> GeneratedFirmware:
        erros = []

        if not fw.main_cpp:
            erros.append("main_cpp vazio")
        else:
            # Verifica estrutura mínima Arduino
            if "void setup()" not in fw.main_cpp:
                erros.append("setup() ausente")
            if "void loop()" not in fw.main_cpp:
                erros.append("loop() ausente")
            if "Serial.begin" not in fw.main_cpp:
                erros.append("Serial.begin() ausente")
            # Alerta se usar delay() no loop
            loop_start = fw.main_cpp.find("void loop()")
            if loop_start >= 0:
                loop_body = fw.main_cpp[loop_start:]
                if "delay(" in loop_body:
                    erros.append("AVISO: delay() no loop() — considere millis()")

        if not fw.platformio_ini:
            erros.append("platformio.ini vazio")
        else:
            if "framework = arduino" not in fw.platformio_ini:
                erros.append("framework arduino ausente no platformio.ini")

        fw.erros  = erros
        fw.valido = len([e for e in erros if not e.startswith("AVISO")]) == 0
        return fw

    # ── Persistência ──────────────────────────────────────────────────────

    def _salvar(self, fw: GeneratedFirmware):
        conn = get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS firmwares (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                nome           TEXT,
                descricao      TEXT,
                pedido         TEXT,
                main_cpp       TEXT,
                platformio_ini TEXT,
                libs_novas     TEXT,
                pinos_usados   TEXT,
                notas          TEXT,
                gerado_em      TEXT,
                valido         INTEGER
            )
        """)
        conn.execute("""
            INSERT INTO firmwares
            (nome, descricao, pedido, main_cpp, platformio_ini,
             libs_novas, pinos_usados, notas, gerado_em, valido)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            fw.nome, fw.descricao, fw.pedido,
            fw.main_cpp, fw.platformio_ini,
            json.dumps(fw.libs_novas),
            json.dumps(fw.pinos_usados),
            fw.notas, fw.gerado_em,
            1 if fw.valido else 0,
        ))
        conn.commit()
        conn.close()
        print(f"[FW] Salvo no banco: {fw.nome} (válido={fw.valido})")


# ── Formatador de output ──────────────────────────────────────────────────

def print_firmware(fw: GeneratedFirmware):
    print(f"\n{'='*60}")
    print(f"  FIRMWARE GERADO: {fw.nome}")
    print(f"{'='*60}")
    print(f"  Descrição : {fw.descricao}")
    print(f"  Pedido    : {fw.pedido[:60]}")
    print(f"  Válido    : {'✅ SIM' if fw.valido else '❌ NÃO'}")
    if fw.erros:
        for e in fw.erros:
            print(f"  {'⚠️' if 'AVISO' in e else '❌'} {e}")
    if fw.libs_novas:
        print(f"  Libs novas: {', '.join(fw.libs_novas)}")
    if fw.pinos_usados:
        print(f"  Pinos     : {fw.pinos_usados}")
    if fw.notas:
        print(f"  Notas     : {fw.notas}")
    print(f"\n--- main.cpp ({len(fw.main_cpp)} chars) ---")
    print(fw.main_cpp[:500] + ("..." if len(fw.main_cpp) > 500 else ""))
    print(f"\n--- platformio.ini ---")
    print(fw.platformio_ini)
    print('='*60)