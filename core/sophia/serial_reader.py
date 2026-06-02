"""
SOPHIA ∞ — Serial Reader v0.3
Bidirecional: lê eventos do ESP32 e envia comandos de volta.
"""

import serial
import serial.tools.list_ports
import time
import threading
from typing import Callable, Optional
from .parser import parse_line, ParsedLine, LineType
from .database import (insert_event, insert_telemetry, insert_state,
                       insert_event_v2, insert_telemetry_v2)
from .sessions import SessionEngine
from .command_sender import CommandSender

BAUD_RATE       = 115200
TIMEOUT_S       = 3.0
RECONNECT_S     = 5.0
WATCHDOG_S      = 30.0
SEV_MIN_DISPLAY = 0.25


class SerialReader:
    def __init__(
        self,
        port: str,
        on_event:     Optional[Callable[[ParsedLine], None]] = None,
        on_telemetry: Optional[Callable[[ParsedLine], None]] = None,
        on_state:     Optional[Callable[[ParsedLine], None]] = None,
        on_audio:     Optional[Callable[[ParsedLine], None]] = None,
        on_piezo:     Optional[Callable[[ParsedLine], None]] = None,
        verbose: bool = True,
    ):
        self.port         = port
        self.on_event     = on_event
        self.on_telemetry = on_telemetry
        self.on_state     = on_state
        self.on_audio     = on_audio
        self.on_piezo     = on_piezo
        self.verbose      = verbose

        self._running  = False
        self._ser: Optional[serial.Serial] = None
        self._last_rx  = time.time()
        self._thread: Optional[threading.Thread] = None
        self._lock     = threading.Lock()
        self.session   = SessionEngine()
        self.cmd: Optional[CommandSender] = None  # disponível após conexão

        self.stats = {
            "events": 0, "telemetry": 0, "states": 0,
            "errors": 0, "reconnects": 0, "sessions": 0,
            "commands_sent": 0,
        }

    def start(self):
        self._running = True
        self._thread  = threading.Thread(
            target=self._loop, daemon=True, name="sophia-serial"
        )
        self._thread.start()
        print(f"[SERIAL] Iniciado em {self.port} @ {BAUD_RATE}baud")

    def stop(self):
        self._running = False
        if self._ser and self._ser.is_open:
            self._ser.close()
        print("[SERIAL] Encerrado.")

    def send_insight(self, insight) -> bool:
        """Envia insight do Qwen para o OLED do ESP32."""
        if self.cmd:
            ok = self.cmd.send_insight(insight)
            if ok:
                self.stats["commands_sent"] += 1
                print(f"[CMD] Insight enviado ao OLED: [{insight.oled_msg}]")
            return ok
        return False

    def send_oled(self, msg: str) -> bool:
        if self.cmd:
            ok = self.cmd.send_oled(msg)
            if ok:
                self.stats["commands_sent"] += 1
            return ok
        return False

    def _connect(self) -> bool:
        try:
            if self._ser and self._ser.is_open:
                self._ser.close()
            self._ser = serial.Serial(self.port, BAUD_RATE, timeout=TIMEOUT_S)
            self.cmd   = CommandSender(self._ser)
            self._last_rx = time.time()
            print(f"[SERIAL] Conectado a {self.port}")
            return True
        except serial.SerialException as e:
            print(f"[SERIAL] Falha ao conectar: {e}")
            self.cmd = None
            return False

    def _loop(self):
        while self._running:
            if not self._connect():
                time.sleep(RECONNECT_S)
                self.stats["reconnects"] += 1
                continue
            try:
                while self._running:
                    if time.time() - self._last_rx > WATCHDOG_S:
                        print("[SERIAL] Watchdog — reconectando")
                        self.stats["reconnects"] += 1
                        break
                    raw = self._ser.readline()
                    if not raw:
                        continue
                    self._last_rx = time.time()
                    try:
                        line = raw.decode("utf-8", errors="replace")
                    except Exception:
                        continue
                    self._dispatch(line)
            except serial.SerialException as e:
                print(f"[SERIAL] Conexão perdida: {e}")
                self.cmd = None
                self.stats["reconnects"] += 1
                time.sleep(RECONNECT_S)

    def _dispatch(self, raw: str):
        parsed = parse_line(raw)
        sid = self.session.ensure_session()

        if parsed.type == LineType.EVENT:
            self.stats["events"] += 1
            insert_event(parsed.data, parsed.raw)
            insert_event_v2(sid, parsed.data, parsed.raw)

            if self.verbose:
                event = parsed.data.get("event", "")
                sev   = parsed.data.get("severity", 0)
                if not (event == "MOVEMENT_GENTLE" and sev < SEV_MIN_DISPLAY):
                    print(f"  [EVT] {event:20s} "
                          f"sev={sev:.3f}  state={parsed.data.get('state','?')}")

            if self.on_event:
                self.on_event(parsed)

        elif parsed.type == LineType.TELEMETRY:
            self.stats["telemetry"] += 1
            uptime = parsed.data.get("uptime", 0)

            if self.session.process_telemetry(uptime):
                self.stats["sessions"] += 1
                sid = self.session.session_id

            insert_telemetry(parsed.data, parsed.raw)
            insert_telemetry_v2(sid, parsed.data, parsed.raw)

            if self.verbose:
                print(f"  [TEL] uptime={uptime}s  "
                      f"heap={parsed.data.get('heap')}  "
                      f"session=#{sid}")

            if self.on_telemetry:
                self.on_telemetry(parsed)

        elif parsed.type == LineType.STATE:
            self.stats["states"] += 1
            insert_state(parsed.data, parsed.raw)
            insert_event_v2(sid, parsed.data, parsed.raw)

            print(f"  [STA] ► {parsed.data.get('state','?'):10s} "
                  f"sev={parsed.data.get('severity', 0):.3f}  "
                  f"session=#{sid}")

            if self.on_state:
                self.on_state(parsed)

        elif parsed.type == LineType.AUDIO:
            if self.on_audio:
                self.on_audio(parsed)

        elif parsed.type == LineType.PIEZO:
            print(f"  [PIE] impacto={parsed.data.get('intensidade', 0):.3f} "
                  f"{parsed.data.get('nivel', '')}")
            if self.on_piezo:
                self.on_piezo(parsed)

        elif parsed.type == LineType.SYSTEM:
            if self.verbose:
                print(f"  [SYS] {parsed.raw.strip()}")

        elif parsed.error:
            self.stats["errors"] += 1
            print(f"  [ERR] {parsed.error}")


def list_ports() -> list[str]:
    return [p.device for p in serial.tools.list_ports.comports()]