"""
SOPHIA ∞ — Observer Engine v0.2
Correções:
- Filtra eventos por relevância (ignora MOVEMENT_GENTLE de baixa severidade)
- Limita janela a eventos significativos para não explodir o prompt
- Peso diferenciado por tipo de evento
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from .database import get_conn


@dataclass
class SessionSnapshot:
    janela_minutos: int
    total_eventos:  int
    total_raw:      int   # todos os eventos, incluindo os filtrados
    inicio:         str
    fim:            str

    tempo_idle:     float = 0.0
    tempo_active:   float = 0.0
    tempo_alert:    float = 0.0
    tempo_recovery: float = 0.0

    severidade_media:  float = 0.0
    severidade_max:    float = 0.0
    picos_movimento:   int   = 0
    alertas_totais:    int   = 0
    impactos_totais:   int   = 0

    padrao:      str = "ESTAVEL"
    nivel_geral: str = "BAIXO"
    tendencia:   str = "NEUTRA"

    resumo:   str = ""
    sugestao: str = ""
    transicoes: list = field(default_factory=list)


# Peso por tipo — GENTLE de baixa sev não conta para métricas de agitação
PESO_EVENTO = {
    "ALERT_TRIGGERED": 3.0,
    "STATE_CHANGED":   2.0,
    "MOVEMENT_SPIKE":  1.5,
    "IMPACT_STRONG":   2.5,
    "IMPACT":          1.5,
    "MOVEMENT_GENTLE": 0.3,
    "AUDIO_ACTIVE":    0.5,
}

# Threshold mínimo de severidade para incluir no cálculo
SEV_MIN_GENTLE = 0.20   # GENTLE abaixo disso é ruído de fundo


class ObserverEngine:

    def __init__(self, janela_minutos: int = 5):
        self.janela_minutos = janela_minutos

    def observe(self) -> SessionSnapshot:
        conn = get_conn()
        since = (datetime.now() - timedelta(minutes=self.janela_minutos)).isoformat()
        todos    = self._fetch_events(conn, since)
        telemetry = self._fetch_last_telemetry(conn)
        conn.close()

        if not todos:
            return self._snapshot_vazio()

        # Filtra eventos relevantes
        relevantes = self._filtrar(todos)
        snap = self._analisar(relevantes, len(todos))
        snap = self._gerar_semantico(snap, telemetry)
        return snap

    def _filtrar(self, eventos: list) -> list:
        """Remove ruído — GENTLE de baixa severidade."""
        resultado = []
        for e in eventos:
            tipo, sev = e[0], e[1] or 0
            if tipo == "MOVEMENT_GENTLE" and sev < SEV_MIN_GENTLE:
                continue   # ruído de fundo, descarta
            resultado.append(e)
        return resultado

    def _fetch_events(self, conn, since: str) -> list:
        return conn.execute("""
            SELECT event, severity, state, received, timestamp, audio, mov, piezo
            FROM events WHERE received >= ?
            ORDER BY received ASC
        """, (since,)).fetchall()

    def _fetch_last_telemetry(self, conn) -> Optional[dict]:
        row = conn.execute(
            "SELECT uptime, heap, rssi FROM telemetry ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def _analisar(self, eventos: list, total_raw: int) -> SessionSnapshot:
        total  = len(eventos)
        if total == 0:
            return self._snapshot_vazio(total_raw)

        severidades = [e[1] for e in eventos if e[1] is not None]
        states      = [e[2] for e in eventos if e[2]]

        contagem = {}
        for e in eventos:
            contagem[e[0]] = contagem.get(e[0], 0) + 1

        picos    = contagem.get("MOVEMENT_SPIKE", 0)
        alertas  = contagem.get("ALERT_TRIGGERED", 0)
        impactos = contagem.get("IMPACT", 0) + contagem.get("IMPACT_STRONG", 0)

        total_state = len(states) or 1
        dist = {s: states.count(s) / total_state
                for s in ["IDLE", "ACTIVE", "ALERT", "RECOVERY"]}

        sev_media = sum(severidades) / len(severidades) if severidades else 0
        sev_max   = max(severidades) if severidades else 0

        transicoes = [
            {"estado": e[2], "severity": e[1], "quando": e[3]}
            for e in eventos if e[0] == "STATE_CHANGED"
        ]

        # Tendência — só sobre eventos com peso
        sevs_pesadas = [
            e[1] * PESO_EVENTO.get(e[0], 1.0)
            for e in eventos if e[1] is not None
        ]
        meio = len(sevs_pesadas) // 2
        if meio > 0:
            mi = sum(sevs_pesadas[:meio]) / meio
            mf = sum(sevs_pesadas[meio:]) / (len(sevs_pesadas) - meio)
            tendencia = "SUBINDO" if mf - mi > 0.1 else \
                        "DESCENDO" if mi - mf > 0.1 else "NEUTRA"
        else:
            tendencia = "NEUTRA"

        padrao = self._detectar_padrao(severidades, alertas, picos, tendencia)
        nivel  = self._calcular_nivel(sev_media, alertas, dist.get("ALERT", 0))

        return SessionSnapshot(
            janela_minutos   = self.janela_minutos,
            total_eventos    = total,
            total_raw        = total_raw,
            inicio           = eventos[0][3],
            fim              = eventos[-1][3],
            tempo_idle       = dist.get("IDLE", 0),
            tempo_active     = dist.get("ACTIVE", 0),
            tempo_alert      = dist.get("ALERT", 0),
            tempo_recovery   = dist.get("RECOVERY", 0),
            severidade_media = round(sev_media, 3),
            severidade_max   = round(sev_max, 3),
            picos_movimento  = picos,
            alertas_totais   = alertas,
            impactos_totais  = impactos,
            padrao           = padrao,
            nivel_geral      = nivel,
            tendencia        = tendencia,
            transicoes       = transicoes,
        )

    def _detectar_padrao(self, sevs, alertas, picos, tendencia):
        if not sevs: return "ESTAVEL"
        if alertas >= 8: return "CRITICO"
        if tendencia == "SUBINDO" and picos >= 3: return "ESCALADA"
        if tendencia == "DESCENDO" and max(sevs) > 0.5: return "ACALMIA"
        if len(sevs) >= 6:
            altas  = sum(1 for s in sevs if s > 0.3)
            baixas = sum(1 for s in sevs if s < 0.2)
            if altas > 2 and baixas > 2: return "CICLICO"
        if max(sevs) > 0.6 and alertas <= 2: return "PICO"
        return "ESTAVEL"

    def _calcular_nivel(self, sev_media, alertas, pct_alert):
        if sev_media > 0.5 or alertas > 10 or pct_alert > 0.5: return "CRITICO"
        if sev_media > 0.35 or alertas > 5  or pct_alert > 0.3: return "ALTO"
        if sev_media > 0.2  or alertas > 1  or pct_alert > 0.1: return "MODERADO"
        return "BAIXO"

    def _gerar_semantico(self, snap, tel):
        partes = [
            f"Nos últimos {snap.janela_minutos} minutos, "
            f"{snap.total_eventos} eventos relevantes "
            f"(de {snap.total_raw} totais) foram analisados."
        ]
        if snap.tempo_alert > 0.3:
            partes.append(f"Sistema em ALERTA por {snap.tempo_alert*100:.0f}% do tempo.")
        elif snap.tempo_active > 0.5:
            partes.append("Atividade moderada a alta.")
        else:
            partes.append("Ambiente predominantemente calmo.")
        if snap.picos_movimento > 3:
            partes.append(f"{snap.picos_movimento} picos de movimento.")
        if snap.alertas_totais > 0:
            partes.append(
                f"{snap.alertas_totais} alertas (max sev={snap.severidade_max:.2f})."
            )
        if snap.impactos_totais > 0:
            partes.append(f"{snap.impactos_totais} impactos físicos.")
        if snap.tendencia != "NEUTRA":
            partes.append(f"Tendência {snap.tendencia.lower()}.")
        if tel:
            partes.append(f"Uptime={tel.get('uptime')}s heap={tel.get('heap')}.")
        snap.resumo = " ".join(partes)

        snap.sugestao = {
            "CRITICO":  "Agitação crítica. Considere pausar atividades.",
            "ALTO":     "Atividade elevada. Atenção ao ambiente.",
            "MODERADO": "Atividade moderada. Sistema normal.",
            "BAIXO":    "Ambiente calmo. Sistema estável.",
        }.get(snap.nivel_geral, "")
        return snap

    def _snapshot_vazio(self, total_raw: int = 0) -> SessionSnapshot:
        return SessionSnapshot(
            janela_minutos=self.janela_minutos, total_eventos=0,
            total_raw=total_raw,
            inicio=datetime.now().isoformat(), fim=datetime.now().isoformat(),
            padrao="ESTAVEL", nivel_geral="BAIXO", tendencia="NEUTRA",
            resumo="Nenhum evento relevante na janela atual.",
            sugestao="Sistema aguardando percepção.",
        )


def snapshot_to_prompt(snap: SessionSnapshot) -> str:
    return f"""# SOPHIA ∞ — Contexto da Sessão

## Resumo
{snap.resumo}

## Métricas (janela: {snap.janela_minutos} min)
- Eventos relevantes: {snap.total_eventos} (total bruto: {snap.total_raw})
- Severidade: média={snap.severidade_media:.3f} máx={snap.severidade_max:.3f}
- Picos movimento: {snap.picos_movimento} | Alertas: {snap.alertas_totais} | Impactos: {snap.impactos_totais}

## Estados
- IDLE {snap.tempo_idle*100:.0f}% | ACTIVE {snap.tempo_active*100:.0f}% | ALERT {snap.tempo_alert*100:.0f}% | RECOVERY {snap.tempo_recovery*100:.0f}%

## Avaliação
- Padrão: {snap.padrao} | Nível: {snap.nivel_geral} | Tendência: {snap.tendencia}
"""