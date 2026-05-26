from typing import Optional
import sqlite3
import os
from pathlib import Path
from datetime import datetime

RIDGE_DIR = Path.home() / ".ridge"
DB_PATH = RIDGE_DIR / "data.db"


def get_db() -> sqlite3.Connection:
    RIDGE_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _create_tables(conn)
    return conn


def _create_tables(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            task        TEXT,
            started_at  TEXT NOT NULL,
            ended_at    TEXT,
            focus_score INTEGER
        );

        CREATE TABLE IF NOT EXISTS events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  INTEGER,
            ts          TEXT NOT NULL,
            event_type  TEXT NOT NULL,
            app         TEXT,
            url         TEXT,
            domain      TEXT,
            category    TEXT,
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        );

        CREATE TABLE IF NOT EXISTS site_overrides (
            domain      TEXT PRIMARY KEY,
            category    TEXT NOT NULL
        );
    """)
    conn.commit()


def start_session(task: str = "") -> int:
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO sessions (task, started_at) VALUES (?, ?)",
        (task, datetime.utcnow().isoformat())
    )
    conn.commit()
    session_id = cur.lastrowid
    conn.close()
    # Save active session id to file
    (RIDGE_DIR / "active_session").write_text(str(session_id))
    return session_id


def end_session(session_id: int, focus_score: int):
    conn = get_db()
    conn.execute(
        "UPDATE sessions SET ended_at=?, focus_score=? WHERE id=?",
        (datetime.utcnow().isoformat(), focus_score, session_id)
    )
    conn.commit()
    conn.close()
    active = RIDGE_DIR / "active_session"
    if active.exists():
        active.unlink()


def get_active_session_id() -> Optional[int]:
    f = RIDGE_DIR / "active_session"
    if f.exists():
        try:
            return int(f.read_text().strip())
        except Exception:
            return None
    return None


def log_event(session_id: int, event_type: str, app: str = "",
              url: str = "", domain: str = "", category: str = ""):
    conn = get_db()
    conn.execute(
        """INSERT INTO events
           (session_id, ts, event_type, app, url, domain, category)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (session_id, datetime.utcnow().isoformat(),
         event_type, app, url, domain, category)
    )
    conn.commit()
    conn.close()


def get_today_events():
    conn = get_db()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT * FROM events WHERE ts LIKE ? ORDER BY ts",
        (f"{today}%",)
    ).fetchall()
    conn.close()
    return rows


def get_week_events():
    from datetime import timedelta
    conn = get_db()
    since = (datetime.utcnow() - timedelta(days=7)).isoformat()
    rows = conn.execute(
        "SELECT * FROM events WHERE ts >= ? ORDER BY ts",
        (since,)
    ).fetchall()
    conn.close()
    return rows


def get_today_sessions():
    conn = get_db()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT * FROM sessions WHERE started_at LIKE ? ORDER BY started_at",
        (f"{today}%",)
    ).fetchall()
    conn.close()
    return rows


def get_week_sessions():
    from datetime import timedelta
    conn = get_db()
    since = (datetime.utcnow() - timedelta(days=7)).isoformat()
    rows = conn.execute(
        "SELECT * FROM sessions WHERE started_at >= ? ORDER BY started_at",
        (since,)
    ).fetchall()
    conn.close()
    return rows
    