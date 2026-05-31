"""
SOPHIA ∞ — Database Engine
Armazena eventos, telemetria e estados em SQLite local.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "sophia.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS events (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            received  TEXT    NOT NULL,
            event     TEXT    NOT NULL,
            severity  REAL,
            state     TEXT,
            timestamp INTEGER,
            audio     REAL,
            mov       REAL,
            piezo     REAL,
            raw       TEXT
        );

        CREATE TABLE IF NOT EXISTS telemetry (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            received TEXT    NOT NULL,
            uptime   INTEGER,
            heap     INTEGER,
            rssi     INTEGER,
            ip       TEXT,
            raw      TEXT
        );

        CREATE TABLE IF NOT EXISTS states (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            received TEXT    NOT NULL,
            state    TEXT    NOT NULL,
            severity REAL,
            raw      TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_events_event    ON events(event);
        CREATE INDEX IF NOT EXISTS idx_events_received ON events(received);
        CREATE INDEX IF NOT EXISTS idx_states_state    ON states(state);
    """)
    conn.commit()
    conn.close()
    print(f"[DB] Banco inicializado: {DB_PATH}")


def insert_event(data: dict, raw: str):
    conn = get_conn()
    conn.execute("""
        INSERT INTO events (received, event, severity, state, timestamp, audio, mov, piezo, raw)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        data.get("event", "UNKNOWN"),
        data.get("severity"),
        data.get("state"),
        data.get("timestamp"),
        data.get("audio"),
        data.get("mov"),
        data.get("piezo"),
        raw,
    ))
    conn.commit()
    conn.close()


def insert_telemetry(data: dict, raw: str):
    conn = get_conn()
    conn.execute("""
        INSERT INTO telemetry (received, uptime, heap, rssi, ip, raw)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        data.get("uptime"),
        data.get("heap"),
        data.get("rssi"),
        data.get("ip"),
        raw,
    ))
    conn.commit()
    conn.close()


def insert_state(data: dict, raw: str):
    conn = get_conn()
    conn.execute("""
        INSERT INTO states (received, state, severity, raw)
        VALUES (?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        data.get("state", "UNKNOWN"),
        data.get("severity"),
        raw,
    ))
    conn.commit()
    conn.close()


def query_recent_events(limit: int = 20) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def query_state_summary() -> dict:
    conn = get_conn()
    rows = conn.execute("""
        SELECT state, COUNT(*) as total
        FROM states
        GROUP BY state
        ORDER BY total DESC
    """).fetchall()
    conn.close()
    return {r["state"]: r["total"] for r in rows}


# ── Funções v2 com session_id ─────────────────────────────────────────────

def insert_event_v2(session_id: int, data: dict, raw: str):
    conn = get_conn()
    conn.execute("""
        INSERT INTO events_v2
        (session_id, received, event, severity, state, timestamp, audio, mov, piezo, raw)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id,
        datetime.now().isoformat(),
        data.get("event", "UNKNOWN"),
        data.get("severity"),
        data.get("state"),
        data.get("timestamp"),
        data.get("audio"),
        data.get("mov"),
        data.get("piezo"),
        raw,
    ))
    conn.commit()
    conn.close()


def insert_telemetry_v2(session_id: int, data: dict, raw: str):
    conn = get_conn()
    conn.execute("""
        INSERT INTO telemetry_v2
        (session_id, received, uptime, heap, rssi, ip, raw)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id,
        datetime.now().isoformat(),
        data.get("uptime"),
        data.get("heap"),
        data.get("rssi"),
        data.get("ip"),
        raw,
    ))
    conn.commit()
    conn.close()


def query_events_by_session(session_id: int, limit: int = 50) -> list:
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM events_v2
        WHERE session_id = ?
        ORDER BY id DESC LIMIT ?
    """, (session_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def query_recent_events_v2(session_id: int = None, limit: int = 20,
                            since: str = None) -> list:
    conn = get_conn()
    if session_id and since:
        rows = conn.execute("""
            SELECT * FROM events_v2
            WHERE session_id = ? AND received >= ?
            ORDER BY id DESC LIMIT ?
        """, (session_id, since, limit)).fetchall()
    elif session_id:
        rows = conn.execute("""
            SELECT * FROM events_v2 WHERE session_id = ?
            ORDER BY id DESC LIMIT ?
        """, (session_id, limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM events_v2 ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]