#!/usr/bin/env python3
"""
SOPHIA ∞ — Local Core v0.2
Perceber → Interpretar → Decidir → Agir

Uso:
  python3 sophia_core.py                      # auto-detecta porta
  python3 sophia_core.py --port /dev/ttyACM0  # porta específica
  python3 sophia_core.py --list               # lista portas
  python3 sophia_core.py --query              # consulta banco
  python3 sophia_core.py --observe            # snapshot do Observer
  python3 sophia_core.py --no-qwen            # roda sem IA
"""

import argparse
import sys
import signal
import time
import threading

from sophia.database    import init_db, query_recent_events, query_state_summary
from sophia.serial_reader import SerialReader, list_ports
from sophia.observer    import ObserverEngine, snapshot_to_prompt
from sophia.qwen_bridge import QwenBridge
from sophia.parser      import ParsedLine


BANNER = """
╔══════════════════════════════════════════════════╗
║         SOPHIA ∞  —  LOCAL CORE v0.2            ║
║  Perceber → Interpretar → Decidir → Agir        ║
╚══════════════════════════════════════════════════╝
"""

# ── Ciclo cognitivo ───────────────────────────────────────────────────────

class CognitiveCycle:
    """
    Roda em thread separada.
    A cada N segundos: Observer analisa → Qwen interpreta → loga insight.
    """

    def __init__(self, intervalo_s: int = 60, usar_qwen: bool = True):
        self.intervalo  = intervalo_s
        self.observer   = ObserverEngine(janela_minutos=5)
        self.bridge     = QwenBridge() if usar_qwen else None
        self._running   = False
        self._thread    = None
        self.last_insight = None

    def start(self):
        self._running = True
        self._thread  = threading.Thread(
            target=self._loop, daemon=True, name="sophia-cognitive"
        )
        self._thread.start()
        print(f"[COG] Ciclo cognitivo ativo — análise a cada {self.intervalo}s")

    def stop(self):
        self._running = False

    def run_now(self):
        """Dispara análise imediata (uso interativo)."""
        self._cycle()

    def _loop(self):
        # Aguarda acumular dados antes da primeira análise
        time.sleep(self.intervalo)
        while self._running:
            self._cycle()
            time.sleep(self.intervalo)

    def _cycle(self):
        print("\n[COG] ── Iniciando ciclo cognitivo ──────────────────")
        snap = self.observer.observe()

        print(f"[COG] Observer: {snap.total_eventos} eventos | "
              f"nível={snap.nivel_geral} | padrão={snap.padrao}")

        if snap.total_eventos == 0:
            print("[COG] Sem eventos na janela — aguardando dados")
            return

        if self.bridge:
            print("[COG] Consultando Qwen...")
            insight = self.bridge.analyze(snap)
            self.last_insight = insight

            print(f"\n  ╔═ SOPHIA INSIGHT ═════════════════════════════╗")
            print(f"  ║ Nível   : {insight.nivel}")
            print(f"  ║ Padrão  : {insight.padrao}")
            print(f"  ║ Insight : {insight.insight}")
            print(f"  ║ Sugestão: {insight.sugestao}")
            print(f"  ║ OLED    : [{insight.oled_msg}]")
            print(f"  ╚══════════════════════════════════════════════╝\n")
        else:
            print(f"[COG] {snap.resumo}")
            print(f"[COG] Sugestão: {snap.sugestao}")


# ── Callbacks serial ──────────────────────────────────────────────────────

def on_alert(parsed: ParsedLine):
    event = parsed.data.get("event", "")
    sev   = parsed.data.get("severity", 0)
    if event in ("ALERT_TRIGGERED", "IMPACT_STRONG") and sev > 0.6:
        print(f"\n  ⚠️  ALERTA: {event} sev={sev:.3f}\n")

def on_state_change(parsed: ParsedLine):
    icons = {"IDLE":"😴","ACTIVE":"⚡","ALERT":"🚨","RECOVERY":"🔄"}
    state = parsed.data.get("state","?")
    sev   = parsed.data.get("severity", 0)
    print(f"\n  {icons.get(state,'◉')}  ESTADO → {state}  (sev={sev:.3f})\n")


# ── Utilitários ───────────────────────────────────────────────────────────

def auto_detect_port() -> str:
    ports = list_ports()
    esp   = [p for p in ports if "ACM" in p or "USB" in p]
    if not esp:
        print(f"[ERRO] Nenhum ESP32 detectado. Portas: {ports or 'nenhuma'}")
        sys.exit(1)
    port = esp[0]
    print(f"[AUTO] ESP32 em {port}")
    return port


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="SOPHIA ∞ Local Core")
    ap.add_argument("--port",     type=str,        help="Porta serial")
    ap.add_argument("--list",     action="store_true", help="Lista portas")
    ap.add_argument("--query",    action="store_true", help="Últimos eventos")
    ap.add_argument("--observe",  action="store_true", help="Snapshot Observer")
    ap.add_argument("--no-qwen",  action="store_true", help="Sem IA local")
    ap.add_argument("--ciclo",    type=int, default=60,
                    help="Intervalo do ciclo cognitivo em segundos (default: 60)")
    args = ap.parse_args()

    print(BANNER)
    init_db()

    if args.list:
        for p in list_ports(): print(f"  {p}")
        return

    if args.query:
        print("\n── Últimos 20 eventos ──────────────────────────────")
        for ev in query_recent_events(20):
            print(f"  {ev['received'][:19]}  {ev['event']:22s}  "
                  f"sev={ev['severity'] or 0:.3f}  state={ev['state']}")
        print("\n── Resumo de estados ───────────────────────────────")
        for state, total in query_state_summary().items():
            print(f"  {state:12s}: {total}")
        return

    if args.observe:
        obs  = ObserverEngine(janela_minutos=10)
        snap = obs.observe()
        print(snapshot_to_prompt(snap))
        if not args.no_qwen:
            bridge = QwenBridge()
            if bridge.ping():
                print("[QWEN] Consultando...")
                insight = bridge.analyze(snap)
                print(f"\nInsight : {insight.insight}")
                print(f"Sugestão: {insight.sugestao}")
                print(f"OLED    : [{insight.oled_msg}]")
            else:
                print("[QWEN] Ollama offline")
        return

    # ── Modo principal: Serial + Ciclo Cognitivo
    port = args.port or auto_detect_port()

    usar_qwen = not args.no_qwen
    if usar_qwen:
        bridge = QwenBridge()
        if bridge.ping():
            print(f"[QWEN] Ollama online — modelo: {bridge.model}")
        else:
            print("[QWEN] Ollama offline — rodando sem IA (use --no-qwen para silenciar)")
            usar_qwen = False

    cognitive = CognitiveCycle(intervalo_s=args.ciclo, usar_qwen=usar_qwen)
    reader    = SerialReader(
        port=port,
        on_event=on_alert,
        on_state=on_state_change,
        verbose=True,
    )

    def shutdown(sig, frame):
        print("\n[SOPHIA] Encerrando...")
        cognitive.stop()
        reader.stop()
        print(f"[SOPHIA] Stats: {reader.stats}")
        sys.exit(0)

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    reader.start()
    cognitive.start()
    print(f"[SOPHIA] Rodando — ciclo cognitivo a cada {args.ciclo}s\n"
          f"         Ctrl+C para encerrar | --ciclo N para ajustar intervalo\n")

    while True:
        time.sleep(60)
        print(f"[SOPHIA] ♾  stats={reader.stats}")


if __name__ == "__main__":
    main()