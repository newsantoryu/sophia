"""
SOPHIA ∞ — Command Sender
Envia comandos do PC para o ESP32 via Serial.

Protocolo: CMD:<tipo>:<payload>\n
Tipos:
  INSIGHT  — exibe insight do Qwen no OLED (linha1|linha2)
  OLED     — mensagem direta no OLED
  PING     — verifica conexão (resposta: [ACK] PONG)
"""

import serial
import time
from typing import Optional
from .qwen_bridge import SophiaInsight


class CommandSender:

    def __init__(self, ser: serial.Serial):
        self._ser = ser

    def send_insight(self, insight: SophiaInsight) -> bool:
        """
        Envia insight do Qwen para o OLED.
        Divide em linha1 (nível+padrão) e linha2 (sugestão curta).
        """
        # Linha 1: nível e padrão — curto e direto
        nivel_icons = {
            "CRITICO":  "!! ",
            "ALTO":     "!  ",
            "MODERADO": "~  ",
            "BAIXO":    "OK ",
        }
        icon  = nivel_icons.get(insight.nivel, "")
        linha1 = f"{icon}{insight.oled_msg}"[:20]

        # Linha 2: sugestão truncada para caber no OLED
        linha2 = insight.sugestao[:40] if insight.sugestao else ""

        return self._send("INSIGHT", f"{linha1}|{linha2}")

    def send_oled(self, msg: str) -> bool:
        """Mensagem direta no OLED."""
        return self._send("OLED", msg[:40])

    def ping(self) -> bool:
        """Verifica se ESP32 está respondendo a comandos."""
        return self._send("PING", "")

    def _send(self, tipo: str, payload: str) -> bool:
        if not self._ser or not self._ser.is_open:
            return False
        try:
            cmd = f"CMD:{tipo}:{payload}\n"
            self._ser.write(cmd.encode("utf-8"))
            self._ser.flush()
            return True
        except Exception as e:
            print(f"[CMD] Erro ao enviar: {e}")
            return False