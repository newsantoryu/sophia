"""
SOPHIA ∞ — Serial Reader
Lê o ESP32 via USB Serial com reconexão automática.
Watchdog integrado: reinicia leitura se ESP32 travar.
"""

import serial
import serial.tools.list_ports
import time
import threading
from typing import Callable, Optional
from .parser import parse_line, ParsedLine, LineType
from .database import insert_event, insert_telemetry, insert_state


# ── Config ────────────────────────────────────────────────────────────────
BAUD_RATE      = 115200
TIMEOUT_S      = 3.0
RECONNECT_S    = 5.0
WATCHDOG_S     = 30.0   # reinicia se não receber nada por 30s

SEV_MIN_DISPLAY = 0.25  # GENTLE abaixo disso não aparece no terminal


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

        self._running     = False
        self._ser: Optional[serial.Serial] = None
        self._last_rx     = time.time()
        self._thread: Optional[threading.Thread] = None

        # Contadores de sessão
        self.stats = {
            "events": 0,
            "telemetry": 0,
            "states": 0,
            "errors": 0,
            "reconnects": 0,
        }

    # ── Público ───────────────────────────────────────────────────────────

    def start(self):
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="sophia-serial"
        )
        self._thread.start()
        print(f"[SERIAL] Iniciado em {self.port} @ {BAUD_RATE}baud")

    def stop(self):
        self._running = False
        if self._ser and self._ser.is_open:
            self._ser.close()
        print("[SERIAL] Encerrado.")

    def wait(self):
        if self._thread:
            self._thread.join()

    # ── Interno ───────────────────────────────────────────────────────────

    def _connect(self) -> bool:
        try:
            if self._ser and self._ser.is_open:
                self._ser.close()
            self._ser = serial.Serial(
                self.port, BAUD_RATE, timeout=TIMEOUT_S
            )
            self._last_rx = time.time()
            print(f"[SERIAL] Conectado a {self.port}")
            return True
        except serial.SerialException as e:
            print(f"[SERIAL] Falha ao conectar: {e}")
            return False

    def _loop(self):
        while self._running:
            if not self._connect():
                time.sleep(RECONNECT_S)
                self.stats["reconnects"] += 1
                continue

            try:
                while self._running:
                    # Watchdog
                    if time.time() - self._last_rx > WATCHDOG_S:
                        print("[SERIAL] Watchdog: sem dados — reconectando")
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
                self.stats["reconnects"] += 1
                time.sleep(RECONNECT_S)

    def _dispatch(self, raw: str):
        parsed = parse_line(raw)

        if parsed.type == LineType.EVENT:
            self.stats["events"] += 1
            insert_event(parsed.data, parsed.raw)
            
            if self.verbose:
                event = parsed.data.get("event", "")
                sev = parsed.data.get("severity", 0)

                # Suprime GENTLE de baixa severidade — ruído de fundo
                if not (event == "MOVEMENT_GENTLE" and sev < SEV_MIN_DISPLAY):
                    print(
                         f"  [EVT] {parsed.data.get('event','?'):20s} "
                         f"sev={sev:.3f}  state={parsed.data.get('state','?')}"
                )
            if self.on_event:
                self.on_event(parsed)

        elif parsed.type == LineType.TELEMETRY:
            self.stats["telemetry"] += 1
            insert_telemetry(parsed.data, parsed.raw)
            if self.verbose:
                print(
                    f"  [TEL] uptime={parsed.data.get('uptime')}s  "
                    f"heap={parsed.data.get('heap')}  "
                    f"ip={parsed.data.get('ip')}"
                )
            if self.on_telemetry:
                self.on_telemetry(parsed)

        elif parsed.type == LineType.STATE:
            self.stats["states"] += 1
            insert_state(parsed.data, parsed.raw)
            insert_event(parsed.data, parsed.raw)
            print(
                f"  [STA] ► {parsed.data.get('state','?'):10s} "
                f"sev={parsed.data.get('severity', 0):.3f}"
            )
            if self.on_state:
                self.on_state(parsed)

        elif parsed.type == LineType.AUDIO:
            if self.on_audio:
                self.on_audio(parsed)

        elif parsed.type == LineType.PIEZO:
            print(
                f"  [PIE] impacto={parsed.data.get('intensidade', 0):.3f} "
                f"{parsed.data.get('nivel', '')}"
            )
            if self.on_piezo:
                self.on_piezo(parsed)

        elif parsed.type == LineType.SYSTEM:
            if self.verbose:
                print(f"  [SYS] {parsed.raw.strip()}")

        elif parsed.error:
            self.stats["errors"] += 1
            print(f"  [ERR] {parsed.error} | raw: {parsed.raw.strip()}")


def list_ports() -> list[str]:
    ports = serial.tools.list_ports.comports()
    return [p.device for p in ports]
