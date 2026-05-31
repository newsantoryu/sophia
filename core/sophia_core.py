#!/usr/bin/env python3
"""
SOPHIA ∞ — Local Core v0.1
Ponto de entrada principal.

Uso:
  python sophia_core.py                     # auto-detecta porta
  python sophia_core.py --port /dev/ttyACM0 # porta específica
  python sophia_core.py --list              # lista portas disponíveis
  python sophia_core.py --query             # mostra últimos eventos do banco
"""

import argparse
import sys
import signal
import time

from sophia.database import init_db, query_recent_events, query_state_summary
from sophia.serial_reader import SerialReader, list_ports
from sophia.parser import ParsedLine


# ── Banner ────────────────────────────────────────────────────────────────
BANNER = """
╔══════════════════════════════════════════════╗
║          SOPHIA ∞  —  LOCAL CORE v0.1        ║
║   Sistema Nervoso Cognitivo Embarcado        ║
║   Perceber → Interpretar → Decidir → Agir    ║
╚══════════════════════════════════════════════╝
"""


# ── Callbacks de alto nível ───────────────────────────────────────────────

def on_alert(parsed: ParsedLine):
    """Disparado quando evento é ALERT_TRIGGERED ou IMPACT_STRONG."""
    event = parsed.data.get("event", "")
    sev   = parsed.data.get("severity", 0)
    if event in ("ALERT_TRIGGERED", "IMPACT_STRONG") and sev > 0.6:
        print(f"\n  ⚠️  ALERTA ALTO: {event} sev={sev:.3f}\n")


def on_state_change(parsed: ParsedLine):
    """Disparado em toda mudança de estado."""
    state = parsed.data.get("state", "?")
    sev   = parsed.data.get("severity", 0)
    icons = {
        "IDLE":     "😴",
        "ACTIVE":   "⚡",
        "ALERT":    "🚨",
        "RECOVERY": "🔄",
    }
    icon = icons.get(state, "◉")
    print(f"\n  {icon}  ESTADO → {state}  (sev={sev:.3f})\n")


# ── Auto-detecção de porta ────────────────────────────────────────────────

def auto_detect_port() -> str:
    ports = list_ports()
    esp_ports = [p for p in ports if "ACM" in p or "USB" in p]
    if not esp_ports:
        print("[ERRO] Nenhum ESP32 detectado.")
        print(f"       Portas disponíveis: {ports or 'nenhuma'}")
        sys.exit(1)
    if len(esp_ports) == 1:
        print(f"[AUTO] ESP32 detectado em {esp_ports[0]}")
        return esp_ports[0]
    print(f"[AUTO] Múltiplas portas: {esp_ports}")
    print(f"[AUTO] Usando {esp_ports[0]} (use --port para escolher)")
    return esp_ports[0]


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SOPHIA ∞ Local Core")
    parser.add_argument("--port",  type=str, help="Porta serial do ESP32")
    parser.add_argument("--list",  action="store_true", help="Lista portas")
    parser.add_argument("--query", action="store_true",
                        help="Mostra últimos eventos do banco")
    parser.add_argument("--quiet", action="store_true",
                        help="Suprime logs de áudio e system")
    args = parser.parse_args()

    print(BANNER)

    # ── Listar portas
    if args.list:
        ports = list_ports()
        print("Portas disponíveis:")
        for p in ports:
            print(f"  {p}")
        return

    # ── Inicializa banco
    init_db()

    # ── Query mode
    if args.query:
        print("\n── Últimos 20 eventos ──────────────────")
        for ev in query_recent_events(20):
            print(
                f"  {ev['received'][:19]}  "
                f"{ev['event']:22s}  "
                f"sev={ev['severity'] or 0:.3f}  "
                f"state={ev['state']}"
            )
        print("\n── Resumo de estados ───────────────────")
        for state, total in query_state_summary().items():
            print(f"  {state:12s}: {total} vezes")
        return

    # ── Porta serial
    port = args.port or auto_detect_port()

    # ── Reader
    reader = SerialReader(
        port=port,
        on_event=on_alert,
        on_state=on_state_change,
        verbose=not args.quiet,
    )

    # ── Graceful shutdown
    def shutdown(sig, frame):
        print("\n[SOPHIA] Encerrando...")
        reader.stop()
        print(f"[SOPHIA] Stats: {reader.stats}")
        sys.exit(0)

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # ── Start
    reader.start()
    print(f"[SOPHIA] Lendo {port} — Ctrl+C para encerrar\n")

    # Heartbeat a cada 60s
    while True:
        time.sleep(60)
        print(
            f"[SOPHIA] ♾  stats={reader.stats}  "
            f"uptime={int(time.time())}s"
        )


if __name__ == "__main__":
    main()
