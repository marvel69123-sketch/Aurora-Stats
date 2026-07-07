"""
Aurora Brain — SQLite knowledge engine.

Provides persistent, searchable knowledge storage across 10 domain tables.
The database lives at artifacts/aurora/aurora.db and is created automatically
on first use via init_db().

Public API
----------
init_db()                                    — create tables if they don't exist
save_knowledge(table, title, content, tags)  — insert a new knowledge record
get_knowledge(table, id)                     — fetch one record by id
search_knowledge(q, tables=None)             — full-text LIKE search across all/some tables
list_knowledge(table, limit, offset)         — paginated listing for one table
update_knowledge(table, id, **fields)        — update title / content / tags

Design rules
------------
- Brain files in /brain/*.md are never touched by this module — separate concerns.
- All table names are allowlisted to prevent SQL injection via table parameter.
- sqlite3 is used directly (no ORM) to keep the Python-only artifact dependency-free.
- Connection row_factory = sqlite3.Row so results are dict-like.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "aurora.db"

# ---------------------------------------------------------------------------
# Table registry — the allowlist. Every knowledge table must appear here.
# ---------------------------------------------------------------------------

TABLES: list[str] = [
    "methodology",
    "betting_rules",
    "bankroll_rules",
    "market_rules",
    "learning_history",
    "predictions",
    "bet_results",
    "teams_notes",
    "referee_notes",
    "competitions_notes",
]

_TABLE_SET = set(TABLES)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS {table} (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    title       TEXT    NOT NULL,
    content     TEXT    NOT NULL DEFAULT '',
    tags        TEXT    NOT NULL DEFAULT ''
);
"""

_CREATE_UPDATED_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS {table}_updated_at
AFTER UPDATE ON {table}
BEGIN
    UPDATE {table} SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
    WHERE id = NEW.id;
END;
"""


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # safe for concurrent reads
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _validate_table(table: str) -> None:
    if table not in _TABLE_SET:
        raise ValueError(
            f"Unknown knowledge table '{table}'. "
            f"Valid tables: {sorted(_TABLE_SET)}"
        )


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def init_db() -> None:
    """
    Create all knowledge tables and associated updated_at triggers.
    Safe to call multiple times (CREATE TABLE IF NOT EXISTS).
    Called once at FastAPI startup.
    """
    with _conn() as conn:
        for table in TABLES:
            conn.execute(_CREATE_TABLE.format(table=table))
            conn.execute(_CREATE_UPDATED_TRIGGER.format(table=table))
        conn.commit()
    logger.info("Aurora knowledge DB initialised at %s (%d tables)", DB_PATH, len(TABLES))


def save_knowledge(
    table: str,
    title: str,
    content: str,
    tags: str = "",
) -> dict:
    """
    Insert a new knowledge record into *table*.

    Parameters
    ----------
    table   : one of the 10 knowledge table names
    title   : short human-readable title
    content : full knowledge text (markdown supported)
    tags    : comma-separated labels e.g. "poisson,model,corners"

    Returns the newly created record as a dict.
    """
    _validate_table(table)
    now = _now()
    with _conn() as conn:
        cur = conn.execute(
            f"INSERT INTO {table} (created_at, updated_at, title, content, tags) "
            "VALUES (?, ?, ?, ?, ?)",
            (now, now, title.strip(), content.strip(), tags.strip()),
        )
        conn.commit()
        row = conn.execute(
            f"SELECT * FROM {table} WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return _row_to_dict(row)


def get_knowledge(table: str, record_id: int) -> dict | None:
    """
    Fetch a single knowledge record by id.
    Returns None if not found.
    """
    _validate_table(table)
    with _conn() as conn:
        row = conn.execute(
            f"SELECT * FROM {table} WHERE id = ?", (record_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def search_knowledge(
    q: str,
    tables: list[str] | None = None,
    limit_per_table: int = 20,
) -> list[dict]:
    """
    Full-text LIKE search across title, content, and tags in all (or specified) tables.

    Parameters
    ----------
    q               : search query (case-insensitive LIKE match)
    tables          : restrict to these table names; None = search all 10
    limit_per_table : max results returned per table

    Returns a flat list sorted by updated_at descending with a `source_table` field.
    """
    target = []
    for t in (tables if tables else TABLES):
        _validate_table(t)
        target.append(t)

    like = f"%{q}%"
    results: list[dict] = []

    with _conn() as conn:
        for table in target:
            rows = conn.execute(
                f"""
                SELECT *, '{table}' AS source_table
                FROM {table}
                WHERE title   LIKE ? COLLATE NOCASE
                   OR content LIKE ? COLLATE NOCASE
                   OR tags    LIKE ? COLLATE NOCASE
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (like, like, like, limit_per_table),
            ).fetchall()
            results.extend(_row_to_dict(r) for r in rows)

    results.sort(key=lambda r: r.get("updated_at", ""), reverse=True)
    return results


def list_knowledge(
    table: str,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Return all records from *table* sorted by updated_at descending."""
    _validate_table(table)
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM {table} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def update_knowledge(
    table: str,
    record_id: int,
    title: str | None = None,
    content: str | None = None,
    tags: str | None = None,
) -> dict | None:
    """
    Update title, content, and/or tags for an existing record.
    The updated_at trigger fires automatically.
    Returns the updated record, or None if the id doesn't exist.
    """
    _validate_table(table)
    fields: list[str] = []
    values: list = []
    if title is not None:
        fields.append("title = ?")
        values.append(title.strip())
    if content is not None:
        fields.append("content = ?")
        values.append(content.strip())
    if tags is not None:
        fields.append("tags = ?")
        values.append(tags.strip())

    if not fields:
        return get_knowledge(table, record_id)

    values.append(record_id)
    with _conn() as conn:
        conn.execute(
            f"UPDATE {table} SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        conn.commit()
    return get_knowledge(table, record_id)
