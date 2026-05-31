"""
SOPHIA ∞ — Observer Engine v0
Analisa padrões do banco e gera contexto estruturado.

Responsabilidades:
- Resumir sessão atual (últimos N minutos)
- Calcular métricas de agitação, foco, estabilidade
- Detectar padrões: escalada, acalmia, ciclo, pico isolado
- Gerar snapshot semântico para o Qwen
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from .database import get_conn


# ── Snapshot — saída do Observer ─────────────────────────────────────────

@dataclass
class SessionSnapshot:
    # Janela analisada
    janela_minutos: int
    total_eventos:  int
    inicio:         str
    fim:            str

    # Distribuição de estados
    tempo_idle:     float = 0.0   # % do tempo
    tempo_active:   float = 0.0
    tempo_alert:    float = 0.0
    tempo_recovery: float = 0.0

    # Métricas de intensidade
    severidade_media:  float = 0.0
    severidade_max:    float = 0.0
    picos_movimento:   int   = 0
    alertas_totais:    int   = 0
    impactos_totais:   int   = 0

    # Padrão detectado
    padrao:      str = "ESTAVEL"     # ESCALADA | ACALMIA | CICLICO | PICO | ESTAVEL
    nivel_geral: str = "BAIXO"       # BAIXO | MODERADO | ALTO | CRITICO
    tendencia:   str = "NEUTRA"      # SUBINDO | DESCENDO | NEUTRA

    # Contexto semântico para o Qwen
    resumo:    str = ""
    sugestao:  str = ""

    # Histórico de transições
    transicoes: list = field(default_factory=list)


# ── Observer Engine ───────────────────────────────────────────────────────

class ObserverEngine:

    def __init__(self, janela_minutos: int = 5):
        self.janela_minutos = janela_minutos

    # ── API pública ───────────────────────────────────────────────────────

    def observe(self, session_id: int = None) -> SessionSnapshot:
        """Gera snapshot da sessão atual."""
        conn = get_conn()
        since = (datetime.now() - timedelta(minutes=self.janela_minutos)).isoformat()

        eventos   = self._fetch_events(conn, since)
        telemetry = self._fetch_last_telemetry(conn)
        conn.close()

        if not eventos:
            return self._snapshot_vazio()

        snap = self._analisar(eventos)
        snap = self._gerar_semantico(snap, telemetry)
        return snap

    def observe_trend(self, janelas: int = 3) -> list[SessionSnapshot]:
        """Compara N janelas consecutivas para detectar tendência macro."""
        snapshots = []
        for i in range(janelas, 0, -1):
            conn = get_conn()
            fim   = datetime.now() - timedelta(minutes=(i-1) * self.janela_minutos)
            inicio = fim - timedelta(minutes=self.janela_minutos)
            eventos = self._fetch_events_range(conn, inicio.isoformat(), fim.isoformat())
            conn.close()
            if eventos:
                snap = self._analisar(eventos)
                snapshots.append(snap)
        return snapshots

    # ── Fetch ─────────────────────────────────────────────────────────────

    def _fetch_events(self, conn, since: str, session_id: int = None) -> list:
        if session_id:
            return conn.execute("""
                SELECT event, severity, state, received, timestamp, audio, mov, piezo
                FROM events_v2
                WHERE received >= ? AND session_id = ?
                ORDER BY received ASC
            """, (since, session_id)).fetchall()
        return conn.execute("""
            SELECT event, severity, state, received, timestamp, audio, mov, piezo
            FROM events
            WHERE received >= ?
            ORDER BY received ASC
        """, (since,)).fetchall()

    def _fetch_events_range(self, conn, inicio: str, fim: str) -> list:
        return conn.execute("""
            SELECT event, severity, state, received, timestamp, audio, mov, piezo
            FROM events
            WHERE received >= ? AND received <= ?
            ORDER BY received ASC
        """, (inicio, fim)).fetchall()

    def _fetch_last_telemetry(self, conn) -> Optional[dict]:
        row = conn.execute("""
            SELECT uptime, heap, rssi FROM telemetry
            ORDER BY id DESC LIMIT 1
        """).fetchone()
        return dict(row) if row else None

    # ── Análise ───────────────────────────────────────────────────────────

    def _analisar(self, eventos: list) -> SessionSnapshot:
        total = len(eventos)
        severidades = [e[1] for e in eventos if e[1] is not None]
        states      = [e[2] for e in eventos if e[2]]

        # Contagens por tipo
        contagem = {}
        for e in eventos:
            contagem[e[0]] = contagem.get(e[0], 0) + 1

        picos    = contagem.get("MOVEMENT_SPIKE", 0)
        alertas  = contagem.get("ALERT_TRIGGERED", 0)
        impactos = contagem.get("IMPACT", 0) + contagem.get("IMPACT_STRONG", 0)

        # Distribuição de estados (% por contagem)
        total_state = len(states) or 1
        dist = {s: states.count(s) / total_state for s in
                ["IDLE", "ACTIVE", "ALERT", "RECOVERY"]}

        # Severidade
        sev_media = sum(severidades) / len(severidades) if severidades else 0
        sev_max   = max(severidades) if severidades else 0

        # Transições de estado
        transicoes = [
            {"estado": e[2], "severity": e[1], "quando": e[3]}
            for e in eventos if e[0] == "STATE_CHANGED"
        ]

        # Tendência — compara primeira e segunda metade
        meio = len(severidades) // 2
        if meio > 0:
            media_ini = sum(severidades[:meio]) / meio
            media_fim = sum(severidades[meio:]) / (len(severidades) - meio)
            delta = media_fim - media_ini
            tendencia = "SUBINDO" if delta > 0.05 else "DESCENDO" if delta < -0.05 else "NEUTRA"
        else:
            tendencia = "NEUTRA"

        # Padrão
        padrao = self._detectar_padrao(severidades, alertas, picos, tendencia)

        # Nível geral
        nivel = self._calcular_nivel(sev_media, alertas, dist.get("ALERT", 0))

        inicio = eventos[0][3] if eventos else datetime.now().isoformat()
        fim    = eventos[-1][3] if eventos else datetime.now().isoformat()

        return SessionSnapshot(
            janela_minutos = self.janela_minutos,
            total_eventos  = total,
            inicio         = inicio,
            fim            = fim,
            tempo_idle     = dist.get("IDLE", 0),
            tempo_active   = dist.get("ACTIVE", 0),
            tempo_alert    = dist.get("ALERT", 0),
            tempo_recovery = dist.get("RECOVERY", 0),
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

    def _detectar_padrao(self, sevs: list, alertas: int,
                          picos: int, tendencia: str) -> str:
        if not sevs:
            return "ESTAVEL"
        if alertas >= 5:
            return "CRITICO"
        if tendencia == "SUBINDO" and picos >= 3:
            return "ESCALADA"
        if tendencia == "DESCENDO" and max(sevs) > 0.5:
            return "ACALMIA"
        # Detecta ciclo: alternância de alta e baixa
        if len(sevs) >= 6:
            altas = sum(1 for s in sevs if s > 0.3)
            baixas = sum(1 for s in sevs if s < 0.2)
            if altas > 2 and baixas > 2:
                return "CICLICO"
        if max(sevs) > 0.6 and alertas <= 2:
            return "PICO"
        return "ESTAVEL"

    def _calcular_nivel(self, sev_media: float,
                         alertas: int, pct_alert: float) -> str:
        if sev_media > 0.5 or alertas > 8 or pct_alert > 0.4:
            return "CRITICO"
        if sev_media > 0.35 or alertas > 4 or pct_alert > 0.2:
            return "ALTO"
        if sev_media > 0.2 or alertas > 1:
            return "MODERADO"
        return "BAIXO"

    # ── Semântico ─────────────────────────────────────────────────────────

    def _gerar_semantico(self, snap: SessionSnapshot,
                          tel: Optional[dict]) -> SessionSnapshot:
        """Gera resumo e sugestão em linguagem natural."""

        # Resumo
        partes = []

        partes.append(
            f"Nos últimos {snap.janela_minutos} minutos, "
            f"{snap.total_eventos} eventos foram registrados."
        )

        if snap.tempo_alert > 0.3:
            partes.append(
                f"O sistema passou {snap.tempo_alert*100:.0f}% do tempo em ALERTA."
            )
        elif snap.tempo_active > 0.5:
            partes.append("Ambiente com atividade moderada a alta.")
        else:
            partes.append("Ambiente predominantemente calmo.")

        if snap.picos_movimento > 5:
            partes.append(
                f"{snap.picos_movimento} picos de movimento detectados."
            )
        if snap.alertas_totais > 0:
            partes.append(
                f"{snap.alertas_totais} alertas disparados "
                f"(intensidade máxima: {snap.severidade_max:.2f})."
            )
        if snap.impactos_totais > 0:
            partes.append(f"{snap.impactos_totais} impactos físicos via piezo.")
        if snap.tendencia != "NEUTRA":
            partes.append(
                f"Tendência {snap.tendencia.lower()} na intensidade."
            )
        if tel:
            partes.append(
                f"Sistema: uptime={tel.get('uptime')}s, "
                f"heap={tel.get('heap')} bytes livres."
            )

        snap.resumo = " ".join(partes)

        # Sugestão
        sugestoes = {
            "CRITICO":  "Ambiente com agitação crítica. Considere pausar atividades.",
            "ALTO":     "Nível de atividade elevado. Atenção ao contexto ao redor.",
            "MODERADO": "Atividade moderada. Sistema operando normalmente.",
            "BAIXO":    "Ambiente calmo. Sistema em estado estável.",
        }
        snap.sugestao = sugestoes.get(snap.nivel_geral, "")

        return snap

    def _snapshot_vazio(self) -> SessionSnapshot:
        return SessionSnapshot(
            janela_minutos = self.janela_minutos,
            total_eventos  = 0,
            inicio         = datetime.now().isoformat(),
            fim            = datetime.now().isoformat(),
            padrao         = "ESTAVEL",
            nivel_geral    = "BAIXO",
            tendencia      = "NEUTRA",
            resumo         = "Nenhum evento registrado na janela atual.",
            sugestao       = "Sistema aguardando percepção.",
        )


# ── Formatador para o Qwen ────────────────────────────────────────────────

def snapshot_to_prompt(snap: SessionSnapshot) -> str:
    """Formata o snapshot como contexto estruturado para o Qwen."""
    return f"""# Contexto SOPHIA ∞ — Sessão Atual

## Resumo
{snap.resumo}

## Métricas
- Janela: últimos {snap.janela_minutos} minutos
- Total de eventos: {snap.total_eventos}
- Severidade média: {snap.severidade_media:.3f} | máxima: {snap.severidade_max:.3f}
- Picos de movimento: {snap.picos_movimento}
- Alertas: {snap.alertas_totais}
- Impactos físicos: {snap.impactos_totais}

## Distribuição de Estados
- IDLE:     {snap.tempo_idle*100:.0f}%
- ACTIVE:   {snap.tempo_active*100:.0f}%
- ALERT:    {snap.tempo_alert*100:.0f}%
- RECOVERY: {snap.tempo_recovery*100:.0f}%

## Avaliação
- Padrão detectado: {snap.padrao}
- Nível geral: {snap.nivel_geral}
- Tendência: {snap.tendencia}
- Sugestão: {snap.sugestao}
"""