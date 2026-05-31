"""
SOPHIA ∞ — Session Engine
Gerencia sessões de operação do ESP32.

Uma sessão começa quando o ESP32 boota (uptime volta para ~0).
Cada sessão tem um ID único e isola eventos/telemetria no banco.

Detecção de nova sessão:
- uptime atual < uptime anterior (ESP32 reiniciou)
- Primeira telemetria recebida
"""

import sqlite3
from datetime import datetime
from .database import get_conn


def init_sessions_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT    NOT NULL,
            ended_at   TEXT,
            boot_count INTEGER DEFAULT 1,
            notes      TEXT
        );

        -- Adiciona session_id nas tabelas existentes se não existir
        CREATE TABLE IF NOT EXISTS events_v2 (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL DEFAULT 1,
            received   TEXT    NOT NULL,
            event      TEXT    NOT NULL,
            severity   REAL,
            state      TEXT,
            timestamp  INTEGER,
            audio      REAL,
            mov        REAL,
            piezo      REAL,
            raw        TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

        CREATE TABLE IF NOT EXISTS telemetry_v2 (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL DEFAULT 1,
            received   TEXT    NOT NULL,
            uptime     INTEGER,
            heap       INTEGER,
            rssi       INTEGER,
            ip         TEXT,
            raw        TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

        CREATE INDEX IF NOT EXISTS idx_events_v2_session  ON events_v2(session_id);
        CREATE INDEX IF NOT EXISTS idx_events_v2_event    ON events_v2(event);
        CREATE INDEX IF NOT EXISTS idx_events_v2_received ON events_v2(received);
        CREATE INDEX IF NOT EXISTS idx_tel_v2_session     ON telemetry_v2(session_id);
    """)
    conn.commit()
    conn.close()


class SessionEngine:
    """
    Rastreia sessões do ESP32.
    Detecta reinicialização pelo uptime e cria nova sessão automaticamente.
    """

    def __init__(self):
        self._session_id: int = 0
        self._last_uptime: int = -1
        self._boot_count: int = 0

    @property
    def session_id(self) -> int:
        return self._session_id

    @property
    def active(self) -> bool:
        return self._session_id > 0

    def process_telemetry(self, uptime: int) -> bool:
        """
        Processa uptime do ESP32.
        Retorna True se uma nova sessão foi criada.
        """
        nova_sessao = False

        # Primeira telemetria ou uptime menor que anterior = boot detectado
        if self._last_uptime < 0 or uptime < self._last_uptime:
            self._fechar_sessao_anterior()
            self._session_id = self._criar_sessao()
            self._boot_count += 1
            nova_sessao = True
            print(f"\n[SES] ── Nova sessão #{self._session_id} "
                  f"(boot #{self._boot_count}) ──────────────")

        self._last_uptime = uptime
        return nova_sessao

    def ensure_session(self) -> int:
        """Garante que há uma sessão ativa. Cria se necessário."""
        if self._session_id == 0:
            self._session_id = self._criar_sessao()
        return self._session_id

    # ── Banco ─────────────────────────────────────────────────────────────

    def _criar_sessao(self) -> int:
        conn = get_conn()
        cur = conn.execute(
            "INSERT INTO sessions (started_at, boot_count) VALUES (?, ?)",
            (datetime.now().isoformat(), self._boot_count + 1)
        )
        sid = cur.lastrowid
        conn.commit()
        conn.close()
        return sid

    def _fechar_sessao_anterior(self):
        if self._session_id == 0:
            return
        conn = get_conn()
        conn.execute(
            "UPDATE sessions SET ended_at = ? WHERE id = ?",
            (datetime.now().isoformat(), self._session_id)
        )
        conn.commit()
        conn.close()
        print(f"[SES] Sessão #{self._session_id} encerrada")

    # ── Consultas ─────────────────────────────────────────────────────────

    def get_session_summary(self, session_id: int = None) -> dict:
        sid = session_id or self._session_id
        if not sid:
            return {}
        conn = get_conn()
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (sid,)
        ).fetchone()
        if not row:
            conn.close()
            return {}
        events = conn.execute(
            "SELECT COUNT(*) FROM events_v2 WHERE session_id = ?", (sid,)
        ).fetchone()[0]
        conn.close()
        return {
            "id": row["id"],
            "started_at": row["started_at"],
            "ended_at": row["ended_at"],
            "boot_count": row["boot_count"],
            "total_events": events,
        }

    def list_sessions(self, limit: int = 10) -> list:
        conn = get_conn()
        rows = conn.execute("""
            SELECT s.*, COUNT(e.id) as total_events
            FROM sessions s
            LEFT JOIN events_v2 e ON e.session_id = s.id
            GROUP BY s.id
            ORDER BY s.id DESC
            LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]