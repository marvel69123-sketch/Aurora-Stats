"""
Aurora Chat Database — conversation history storage.

Tables
------
  chat_sessions  — one row per conversation session (keyed by session_id UUID)
  chat_messages  — individual turns: user messages + Aurora responses

Public API
----------
  init_chat_db()
  create_session(session_id)                              -> dict
  save_message(session_id, role, content, intent, entities, fixture_home, fixture_away) -> int
  get_session(session_id)                                 -> dict | None
  get_session_messages(session_id, limit, offset)         -> list[dict]
  get_history(limit, offset, intent_filter)               -> dict
  search_history(query, limit)                            -> list[dict]
  update_session_context(session_id, home, away, intent)
"""
from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent.parent / "aurora.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _row(r: sqlite3.Row | None) -> dict | None:
    return dict(r) if r else None


_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS chat_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT    NOT NULL UNIQUE,
    started_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    last_active     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    message_count   INTEGER NOT NULL DEFAULT 0,
    last_intent     TEXT,
    last_home       TEXT,
    last_away       TEXT
);
CREATE INDEX IF NOT EXISTS idx_cs_session   ON chat_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_cs_active    ON chat_sessions(last_active DESC);

CREATE TABLE IF NOT EXISTS chat_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT    NOT NULL,
    role        TEXT    NOT NULL CHECK(role IN ('user','aurora')),
    content     TEXT    NOT NULL,
    intent      TEXT,
    entities    TEXT    NOT NULL DEFAULT '{}',
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_cm_session   ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_cm_role      ON chat_messages(session_id, role);
CREATE INDEX IF NOT EXISTS idx_cm_intent    ON chat_messages(intent);
CREATE INDEX IF NOT EXISTS idx_cm_created   ON chat_messages(created_at DESC);
"""


def _migrate_add_context_columns() -> None:
    """Safe migration — adds context_json column if not already present."""
    with _conn() as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(chat_sessions)")}
        if "context_json" not in cols:
            conn.execute("ALTER TABLE chat_sessions ADD COLUMN context_json TEXT DEFAULT '{}'")
            logger.info("chat_db: added context_json column to chat_sessions")
        conn.commit()


def init_chat_db() -> None:
    with _conn() as conn:
        conn.executescript(_CREATE_SQL)
        conn.commit()
    _migrate_add_context_columns()
    logger.info("Aurora Chat DB ready")


def create_session(session_id: str) -> dict:
    """Create a new chat session. Silently returns existing session if already present."""
    now = _now()
    with _conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO chat_sessions (session_id, started_at, last_active) VALUES (?, ?, ?)",
            (session_id, now, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM chat_sessions WHERE session_id = ?", (session_id,)).fetchone()
    return dict(row)


def update_session_context(
    session_id: str,
    home: str | None = None,
    away: str | None = None,
    intent: str | None = None,
) -> None:
    """Update the session's last fixture context so follow-up intents can reference it."""
    updates: list[str] = ["last_active = ?"]
    params: list = [_now()]
    if home is not None:
        updates.append("last_home = ?"); params.append(home)
    if away is not None:
        updates.append("last_away = ?"); params.append(away)
    if intent is not None:
        updates.append("last_intent = ?"); params.append(intent)
    params.append(session_id)
    with _conn() as conn:
        conn.execute(
            f"UPDATE chat_sessions SET {', '.join(updates)} WHERE session_id = ?", params
        )
        conn.execute(
            "UPDATE chat_sessions SET message_count = message_count + 1 WHERE session_id = ?",
            (session_id,),
        )
        conn.commit()


def save_message(
    session_id: str,
    role: str,
    content: str,
    intent: str | None = None,
    entities: dict | None = None,
) -> int:
    entities_json = json.dumps(entities or {})
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO chat_messages (session_id, role, content, intent, entities, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, role, content, intent, entities_json, _now()),
        )
        conn.commit()
        return cur.lastrowid or 0


def get_session(session_id: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM chat_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
    return dict(row) if row else None


def get_session_messages(
    session_id: str, limit: int = 50, offset: int = 0
) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE session_id = ? "
            "ORDER BY created_at ASC LIMIT ? OFFSET ?",
            (session_id, limit, offset),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["entities"] = json.loads(d.get("entities") or "{}")
        except Exception:
            d["entities"] = {}
        result.append(d)
    return result


def get_history(
    limit: int = 20,
    offset: int = 0,
    intent_filter: str | None = None,
) -> dict:
    with _conn() as conn:
        if intent_filter:
            total = conn.execute(
                "SELECT COUNT(*) FROM chat_sessions s "
                "WHERE EXISTS (SELECT 1 FROM chat_messages m WHERE m.session_id = s.session_id AND m.intent = ?)",
                (intent_filter,),
            ).fetchone()[0]
            rows = conn.execute(
                "SELECT s.*, "
                "  (SELECT content FROM chat_messages WHERE session_id = s.session_id AND role = 'user' ORDER BY created_at ASC LIMIT 1) AS first_message "
                "FROM chat_sessions s "
                "WHERE EXISTS (SELECT 1 FROM chat_messages m WHERE m.session_id = s.session_id AND m.intent = ?) "
                "ORDER BY s.last_active DESC LIMIT ? OFFSET ?",
                (intent_filter, limit, offset),
            ).fetchall()
        else:
            total = conn.execute("SELECT COUNT(*) FROM chat_sessions").fetchone()[0]
            rows = conn.execute(
                "SELECT s.*, "
                "  (SELECT content FROM chat_messages WHERE session_id = s.session_id AND role = 'user' ORDER BY created_at ASC LIMIT 1) AS first_message "
                "FROM chat_sessions s ORDER BY s.last_active DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
    return {
        "total":   total,
        "limit":   limit,
        "offset":  offset,
        "sessions": [dict(r) for r in rows],
    }


def search_history(query: str, limit: int = 20) -> list[dict]:
    """Search across all message content and intents."""
    like = f"%{query}%"
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_messages "
            "WHERE content LIKE ? COLLATE NOCASE OR intent LIKE ? COLLATE NOCASE "
            "ORDER BY created_at DESC LIMIT ?",
            (like, like, limit),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["entities"] = json.loads(d.get("entities") or "{}")
        except Exception:
            d["entities"] = {}
        result.append(d)
    return result


def count_sessions() -> int:
    with _conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM chat_sessions").fetchone()[0]


def count_messages() -> int:
    with _conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0]


# ---------------------------------------------------------------------------
# Conversation context helpers (Phase 2 — ConversationContext)
# ---------------------------------------------------------------------------

def get_conversation_context(session_id: str) -> dict:
    """
    Return the ConversationContext dict stored for *session_id*.

    Shape:
      {
        "last_match":    str | None,
        "last_home":     str | None,
        "last_away":     str | None,
        "last_intent":   str | None,
        "last_analysis": dict | None,   # full analysis payload minus 'brain'
        "user_profile":  {
            "experience_level":  str | None,
            "risk_preference":   str | None,
            "bankroll":          float | None,
            "preferred_markets": list[str],
        }
      }

    Returns {} when session doesn't exist or context_json is empty/invalid.
    """
    with _conn() as conn:
        row = conn.execute(
            "SELECT context_json FROM chat_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if not row:
        return {}
    try:
        return json.loads(row[0] or "{}") or {}
    except Exception:
        return {}


def save_conversation_context(session_id: str, context: dict) -> None:
    """Persist *context* dict as JSON for *session_id*."""
    try:
        ctx_json = json.dumps(context, ensure_ascii=False)
    except Exception as exc:
        logger.warning("save_conversation_context: serialisation error: %s", exc)
        return
    with _conn() as conn:
        conn.execute(
            "UPDATE chat_sessions SET context_json = ?, last_active = ? WHERE session_id = ?",
            (ctx_json, _now(), session_id),
        )
        conn.commit()
