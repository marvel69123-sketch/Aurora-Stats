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


CATEGORIES: list[str] = [
    "methodology",
    "betting_rules",
    "bankroll_rules",
    "market_rules",
    "live_rules",
    "pre_match_rules",
    "referee_rules",
    "league_rules",
    "team_rules",
    "psychology",
    "risk_management",
    "red_flags",
    "golden_rules",
]

_CATEGORY_SET = set(CATEGORIES)

_CREATE_KNOWLEDGE_ITEMS = """
CREATE TABLE IF NOT EXISTS knowledge_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category    TEXT    NOT NULL,
    title       TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',
    examples    TEXT    NOT NULL DEFAULT '[]',
    confidence  REAL    NOT NULL DEFAULT 0.8,
    version     TEXT    NOT NULL DEFAULT '1.0',
    source      TEXT    NOT NULL DEFAULT 'user',
    tags        TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_ki_category   ON knowledge_items(category);
CREATE INDEX IF NOT EXISTS idx_ki_confidence ON knowledge_items(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_ki_title      ON knowledge_items(title);
"""

_KNOWLEDGE_UPDATED_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS knowledge_items_updated_at
AFTER UPDATE ON knowledge_items
BEGIN
    UPDATE knowledge_items SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
    WHERE id = NEW.id;
END;
"""


def init_knowledge_items() -> None:
    """Create knowledge_items table and seed with foundational rules if empty."""
    with _conn() as conn:
        conn.executescript(_CREATE_KNOWLEDGE_ITEMS)
        conn.executescript(_KNOWLEDGE_UPDATED_TRIGGER)
        conn.commit()
    logger.info("Aurora knowledge_items table ready")
    seed_knowledge_if_empty()


def save_knowledge_item(
    category:    str,
    title:       str,
    description: str,
    examples:    list[str] | None = None,
    confidence:  float = 0.8,
    version:     str = "1.0",
    source:      str = "user",
    tags:        str = "",
) -> dict:
    """Insert a new knowledge item. category must be in CATEGORIES."""
    import json as _json
    if category not in _CATEGORY_SET:
        raise ValueError(f"Unknown category '{category}'. Valid: {sorted(_CATEGORY_SET)}")
    examples_json = _json.dumps(examples or [])
    now = _now()
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO knowledge_items "
            "(category, title, description, examples, confidence, version, source, tags, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (category, title.strip(), description.strip(), examples_json,
             float(confidence), version.strip(), source.strip(), tags.strip(), now, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM knowledge_items WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _row_to_dict(row)


def get_knowledge_item(record_id: int) -> dict | None:
    """Fetch a single knowledge item by id."""
    with _conn() as conn:
        row = conn.execute("SELECT * FROM knowledge_items WHERE id = ?", (record_id,)).fetchone()
    return _row_to_dict(row) if row else None


def search_knowledge_items(
    q: str,
    categories: list[str] | None = None,
    limit: int = 20,
) -> list[dict]:
    """Full-text LIKE search across title, description, tags in knowledge_items."""
    like = f"%{q}%"
    cat_clause = ""
    params: list = [like, like, like]
    if categories:
        placeholders = ",".join("?" * len(categories))
        cat_clause = f"AND category IN ({placeholders})"
        params.extend(categories)
    params.append(limit)
    with _conn() as conn:
        rows = conn.execute(
            f"""SELECT * FROM knowledge_items
               WHERE (title LIKE ? COLLATE NOCASE
                   OR description LIKE ? COLLATE NOCASE
                   OR tags LIKE ? COLLATE NOCASE)
               {cat_clause}
               ORDER BY confidence DESC, updated_at DESC
               LIMIT ?""",
            params,
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def list_category_items(
    category: str,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Return all items for a category, sorted by confidence DESC."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM knowledge_items WHERE category = ? "
            "ORDER BY confidence DESC, updated_at DESC LIMIT ? OFFSET ?",
            (category, limit, offset),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def list_all_knowledge_items(
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Return all knowledge items, optionally filtered by category."""
    if category:
        return list_category_items(category, limit=limit, offset=offset)
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM knowledge_items ORDER BY confidence DESC, updated_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_categories_summary() -> list[dict]:
    """Return each category with its item count and avg confidence."""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT category,
                      COUNT(*) AS total,
                      ROUND(AVG(confidence), 3) AS avg_confidence,
                      MAX(updated_at) AS last_updated
               FROM knowledge_items
               GROUP BY category
               ORDER BY category""",
        ).fetchall()
    present = {r["category"]: _row_to_dict(r) for r in rows}
    result = []
    for cat in CATEGORIES:
        if cat in present:
            result.append(present[cat])
        else:
            result.append({"category": cat, "total": 0, "avg_confidence": 0.0, "last_updated": None})
    return result


def count_knowledge_items(category: str | None = None) -> int:
    """Count total knowledge items (optionally filtered)."""
    with _conn() as conn:
        if category:
            row = conn.execute("SELECT COUNT(*) AS n FROM knowledge_items WHERE category = ?", (category,)).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) AS n FROM knowledge_items").fetchone()
    return int(row["n"])


# ---------------------------------------------------------------------------
# Seed data — foundational knowledge for all 13 categories
# ---------------------------------------------------------------------------

_SEED: list[dict] = [
    # ── methodology ────────────────────────────────────────────────────────────
    {
        "category": "methodology", "confidence": 0.95, "version": "1.0", "source": "aurora",
        "title": "Poisson Model Foundation",
        "description": (
            "Goals in football follow a Poisson distribution. "
            "Aurora models home and away attack/defence rates separately using season averages, "
            "producing independent goal probability vectors. "
            "The model is re-calibrated with live xG data when available."
        ),
        "examples": [
            "Man City home xG 2.4, Liverpool away xG 1.9 → lambda_home=2.4, lambda_away=1.9",
            "P(0 goals) = e^(-lambda) → used for DNB and clean sheet markets",
        ],
        "tags": "poisson,model,xg,goals,probability",
    },
    {
        "category": "methodology", "confidence": 0.90, "version": "1.0", "source": "aurora",
        "title": "Three-Layer Data Hierarchy",
        "description": (
            "Aurora uses three data tiers in priority order: "
            "(1) Live match data — most reliable; "
            "(2) Season-to-date averages per team; "
            "(3) League baseline priors. "
            "A missing upper tier always falls back to the next, never to zero."
        ),
        "examples": [
            "No xG available → use GPG (goals per game) instead",
            "No away record → use league average away scoring rate",
        ],
        "tags": "data,hierarchy,fallback,reliability",
    },
    {
        "category": "methodology", "confidence": 0.88, "version": "1.0", "source": "aurora",
        "title": "Confidence Score Interpretation",
        "description": (
            "Aurora confidence (1–10) measures data richness, NOT certainty. "
            "A 9.0 confidence match has rich, consistent signals. "
            "A 4.0 confidence match lacks xG, lineup, or standings data. "
            "Never interpret confidence as win probability."
        ),
        "examples": [
            "Confidence 8+: live match with xG, events, standings, lineup confirmed",
            "Confidence 4: pre-match only, no xG, no referee assigned",
        ],
        "tags": "confidence,data richness,interpretation",
    },

    # ── betting_rules ──────────────────────────────────────────────────────────
    {
        "category": "betting_rules", "confidence": 0.92, "version": "1.0", "source": "aurora",
        "title": "Positive Expected Value Requirement",
        "description": (
            "Only consider bets with EV > +5%. "
            "EV = (probability × decimal_odds) − 1. "
            "Bets with negative EV are mathematically losing bets over the long run, "
            "regardless of short-term results."
        ),
        "examples": [
            "Probability 60%, odds 1.80 → EV = (0.60 × 1.80) − 1 = +8% → acceptable",
            "Probability 55%, odds 1.70 → EV = (0.55 × 1.70) − 1 = −6.5% → reject",
        ],
        "tags": "ev,expected value,value bet,edge",
    },
    {
        "category": "betting_rules", "confidence": 0.88, "version": "1.0", "source": "aurora",
        "title": "Form Streak Continuation Rule",
        "description": (
            "Teams on a 4+ match winning streak continue to win in approximately 72% of cases. "
            "However, streaks artificially inflate public confidence — always check opponent strength. "
            "Strong form against weak opponents is NOT equivalent to strong form against top teams."
        ),
        "examples": [
            "Team A: 5W in a row against bottom-5 teams → streak less meaningful vs top-4",
            "Team B: 4W including wins over top-6 → stronger signal, weight form higher",
        ],
        "tags": "form,streak,momentum,continuation",
    },
    {
        "category": "betting_rules", "confidence": 0.85, "version": "1.0", "source": "aurora",
        "title": "Market Timing Rule",
        "description": (
            "Pre-match odds are most accurate 60–90 minutes before kickoff after lineups are confirmed. "
            "Odds before lineups contain uncertainty premium of 3–8%. "
            "Live odds re-price every 30–90 seconds — value windows are brief."
        ),
        "examples": [
            "Wait for confirmed lineup before backing a team that relies on one key player",
            "Live EV spike after red card in minute 35 → market re-prices within 90 seconds",
        ],
        "tags": "timing,lineup,live,odds",
    },

    # ── bankroll_rules ─────────────────────────────────────────────────────────
    {
        "category": "bankroll_rules", "confidence": 0.93, "version": "1.0", "source": "aurora",
        "title": "Kelly Criterion — Quarter Kelly",
        "description": (
            "Use 25% of full Kelly stake to reduce variance while preserving edge. "
            "Full Kelly: stake = (probability × odds − 1) / (odds − 1). "
            "Quarter Kelly multiplies this by 0.25. "
            "Never exceed 5% of bankroll on a single bet."
        ),
        "examples": [
            "Kelly = 8%, quarter Kelly = 2% of bankroll",
            "£1000 bankroll, quarter Kelly 2% → stake £20",
        ],
        "tags": "kelly,stake,bankroll,sizing",
    },
    {
        "category": "bankroll_rules", "confidence": 0.90, "version": "1.0", "source": "aurora",
        "title": "Consecutive Loss Stop Rule",
        "description": (
            "Stop betting after 3 consecutive losses and review methodology. "
            "Consecutive losses may indicate: model drift, line movement against you, "
            "or a structural change in a league. "
            "A review period of 48 hours is recommended before resuming."
        ),
        "examples": [
            "3 consecutive losses in same market type → pause that market, not all markets",
            "3 consecutive losses across different markets → full methodology review",
        ],
        "tags": "stop loss,consecutive,loss,review",
    },
    {
        "category": "bankroll_rules", "confidence": 0.87, "version": "1.0", "source": "aurora",
        "title": "Maximum Daily Exposure",
        "description": (
            "Total exposure per day must not exceed 15% of bankroll. "
            "This caps worst-case daily loss regardless of number of bets. "
            "Divide exposure across at least 3 different markets to prevent correlation risk."
        ),
        "examples": [
            "£500 daily limit on £3333 bankroll (15%)",
            "Spread: BTTS + Over Goals + Corners — not three home wins",
        ],
        "tags": "exposure,daily,limit,diversification",
    },

    # ── market_rules ──────────────────────────────────────────────────────────
    {
        "category": "market_rules", "confidence": 0.91, "version": "1.0", "source": "aurora",
        "title": "BTTS — Both Teams Must Have Attacked",
        "description": (
            "BTTS Yes is reliable only when both teams have scored in 60%+ of recent matches. "
            "Check: both teams' home/away scoring records separately. "
            "Teams that park the bus away from home suppress BTTS even with good attack at home."
        ),
        "examples": [
            "Liverpool home (scored 95%) + Arsenal away (scored 65%) → BTTS Yes viable",
            "Chelsea home (scored 80%) + Atletico Madrid away (scored 30%) → avoid BTTS Yes",
        ],
        "tags": "btts,scoring,attack,defence",
    },
    {
        "category": "market_rules", "confidence": 0.89, "version": "1.0", "source": "aurora",
        "title": "Corners — Tactical Pattern Over Volume",
        "description": (
            "Corner markets depend on team tactical style, not just possession. "
            "High-press teams generate more corners. Set-piece focused teams attack corners. "
            "Both teams must be attack-minded for Over 9.5 to be reliable. "
            "One defensive team significantly reduces corner volume."
        ),
        "examples": [
            "Man City vs Chelsea (both attack) → average 11.2 corners expected",
            "Atletico Madrid vs Porto (one parks bus) → average 7.8 corners expected",
        ],
        "tags": "corners,tactical,style,pressing",
    },
    {
        "category": "market_rules", "confidence": 0.86, "version": "1.0", "source": "aurora",
        "title": "Asian Handicap — Only Bet When >3 Goal Class Difference",
        "description": (
            "Asian Handicap bets are only +EV when there is a clear quality gap of 3+ goal levels. "
            "Between evenly-matched teams the handicap margin eliminates most edge. "
            "Always compare season xG differentials, not just league position."
        ),
        "examples": [
            "Man City (-1.5) vs Southampton → xG differential 1.8/match → viable",
            "Arsenal (-0.5) vs Tottenham → xG differential 0.3 → no edge on handicap",
        ],
        "tags": "asian handicap,ah,class difference,xg differential",
    },

    # ── live_rules ────────────────────────────────────────────────────────────
    {
        "category": "live_rules", "confidence": 0.92, "version": "1.0", "source": "aurora",
        "title": "Minutes 30–60 Reliability Window",
        "description": (
            "Live match data becomes statistically reliable from minute 30 onwards. "
            "Before minute 30, small sample sizes produce noisy xG and possession data. "
            "The sweet spot for live betting is minutes 30–60: enough data, "
            "enough time remaining for goals."
        ),
        "examples": [
            "Minute 35, xG 1.2 vs 0.3 → strong home signal, game still open",
            "Minute 10, xG 0.8 vs 0.0 → too early, high variance",
        ],
        "tags": "live,minutes,reliability,timing",
    },
    {
        "category": "live_rules", "confidence": 0.93, "version": "1.0", "source": "aurora",
        "title": "Red Card — Complete Market Recalibration",
        "description": (
            "A red card changes the tactical shape of the match entirely. "
            "After a red card: reduce goal markets by 30–40%, "
            "reduce corners for the 10-man team by 50%, "
            "increase corners for the team with numerical advantage by 20%, "
            "increase card markets significantly."
        ),
        "examples": [
            "Home team red card minute 55 → Over 2.5 goals probability drops from 65% to 38%",
            "Away team red card minute 40 → home corners over 5.5 probability rises from 60% to 78%",
        ],
        "tags": "red card,recalibration,goals,corners,cards",
    },
    {
        "category": "live_rules", "confidence": 0.88, "version": "1.0", "source": "aurora",
        "title": "Score State Momentum Rule",
        "description": (
            "The current score creates momentum signals. "
            "A team trailing by 1 goal in minutes 60–75 increases their attacking pressure "
            "and opens space for the leading team. "
            "This typically increases total corners and chances for both teams."
        ),
        "examples": [
            "Home team 0-1 down minute 65 → expect 20% more corners in final 25 minutes",
            "Match tied 1-1 minute 75 → both teams cautious, fewer open chances",
        ],
        "tags": "score,momentum,trailing,pressure,corners",
    },

    # ── pre_match_rules ───────────────────────────────────────────────────────
    {
        "category": "pre_match_rules", "confidence": 0.91, "version": "1.0", "source": "aurora",
        "title": "Lineup Confirmation Is Mandatory",
        "description": (
            "Never bet on markets that depend on a specific player before lineups are confirmed. "
            "A key striker absence shifts BTTS probability by 8–15%. "
            "A goalkeeper change shifts clean sheet markets by 5–10%. "
            "Wait for official lineups (60 minutes before kickoff) before finalising any bet."
        ),
        "examples": [
            "Haaland absent → Man City over 2.5 goals probability drops 12%",
            "Starting goalkeeper change → clean sheet probability changes ±8%",
        ],
        "tags": "lineup,confirmed,player,absence,pre-match",
    },
    {
        "category": "pre_match_rules", "confidence": 0.85, "version": "1.0", "source": "aurora",
        "title": "Fixture Congestion — Rotation Risk",
        "description": (
            "Teams playing 3+ matches in 7 days frequently rotate. "
            "Rotation typically reduces team quality by 10–20% in terms of xG generation. "
            "Check fixture schedules for both teams — cups + league overlap is highest risk."
        ),
        "examples": [
            "Team with Cup match Wednesday and League match Saturday → expect rotation",
            "Champions League group stage + weekend league → top clubs rotate freely",
        ],
        "tags": "rotation,congestion,cup,fixture,fatigue",
    },
    {
        "category": "pre_match_rules", "confidence": 0.82, "version": "1.0", "source": "aurora",
        "title": "Weather Impact on Physical Markets",
        "description": (
            "Heavy rain reduces passing accuracy and increases long balls. "
            "This typically increases corners (+15–20%) and aerial duels, "
            "but can reduce total goals as pitches become unpredictable. "
            "Wind above 30 mph significantly impacts set pieces and shooting accuracy."
        ),
        "examples": [
            "Heavy rain forecast → Over 8.5 corners probability increases +8%",
            "Wind 35 mph → Over 2.5 goals probability decreases −5%",
        ],
        "tags": "weather,rain,wind,corners,goals",
    },

    # ── referee_rules ─────────────────────────────────────────────────────────
    {
        "category": "referee_rules", "confidence": 0.88, "version": "1.0", "source": "aurora",
        "title": "High-Card Referee Profile",
        "description": (
            "Some referees average 5+ cards per match and consistently affect card markets. "
            "Identify referees with >4.5 avg cards/90 as 'high-card officials'. "
            "When a high-card referee is assigned, Over 4.5 cards market becomes viable "
            "even in normally low-card matchups."
        ),
        "examples": [
            "Referee X avg 5.2 cards/match → Over 4.5 cards baseline probability +25%",
            "Same match with average referee (3.1 cards) → Over 4.5 cards probability baseline",
        ],
        "tags": "referee,cards,yellow,discipline,profile",
    },
    {
        "category": "referee_rules", "confidence": 0.85, "version": "1.0", "source": "aurora",
        "title": "Penalty Rate by Referee",
        "description": (
            "Penalty award rates vary by 3x between different referees in the same league. "
            "High-penalty referees (>0.4 penalties/match) increase Both Teams To Score "
            "and match winner market variance significantly. "
            "Always cross-reference referee penalty history with teams' foul rates."
        ),
        "examples": [
            "Referee Y awards 0.5 penalties/match → increase variance on match winner markets",
            "Referee Z awards 0.1 penalties/match → reduce penalty risk factor",
        ],
        "tags": "referee,penalty,variance,foul rate",
    },

    # ── league_rules ──────────────────────────────────────────────────────────
    {
        "category": "league_rules", "confidence": 0.90, "version": "1.0", "source": "aurora",
        "title": "Premier League Corners Baseline",
        "description": (
            "The Premier League averages 10.1 corners per match. "
            "Over 8.5 corners hits in approximately 68% of matches. "
            "Matches involving top-6 clubs average 11.4 corners. "
            "Matches between bottom-half clubs average 9.2 corners."
        ),
        "examples": [
            "Man City vs Liverpool (both top-6) → expect 11.8 corners baseline",
            "Bournemouth vs Brentford (both bottom-half) → expect 9.0 corners baseline",
        ],
        "tags": "premier league,corners,baseline,england",
    },
    {
        "category": "league_rules", "confidence": 0.88, "version": "1.0", "source": "aurora",
        "title": "La Liga — Low Scoring Away Matches",
        "description": (
            "La Liga away teams score in only 52% of matches, the lowest among top 5 leagues. "
            "BTTS Yes in La Liga hits at 46% vs 55% in the Premier League. "
            "Over 2.5 goals in La Liga hits at 51% vs 57% in the Bundesliga. "
            "Adjust goal market thresholds when analysing Spanish fixtures."
        ),
        "examples": [
            "La Liga away match → reduce BTTS Yes probability by 8% from model baseline",
            "Bundesliga match → increase Over 2.5 goals probability by 5% from model baseline",
        ],
        "tags": "la liga,spain,away goals,btts,scoring rate",
    },
    {
        "category": "league_rules", "confidence": 0.86, "version": "1.0", "source": "aurora",
        "title": "Serie A — Defensive Structure",
        "description": (
            "Serie A has the lowest average goals/match among top 5 leagues (2.48). "
            "Under 2.5 goals hits in 52% of Serie A matches. "
            "Teams from Serie A playing in European competition often shift to more open play. "
            "Domestic Serie A predictions should lean toward Under markets."
        ),
        "examples": [
            "Serie A match baseline → Under 2.5 goals at 52% vs 43% in Bundesliga",
            "Inter Milan home vs mid-table → Under 2.5 viable despite Inter's attack quality",
        ],
        "tags": "serie a,italy,goals,under,defensive",
    },

    # ── team_rules ────────────────────────────────────────────────────────────
    {
        "category": "team_rules", "confidence": 0.87, "version": "1.0", "source": "aurora",
        "title": "Home Fortress Teams",
        "description": (
            "Some teams are dramatically stronger at home than away. "
            "A team with home win rate >70% and away win rate <35% qualifies as a 'home fortress'. "
            "Home fortress teams should be backed heavily at home "
            "but treated as neutral-strength away from home."
        ),
        "examples": [
            "Team with 78% home wins, 28% away wins → back home, avoid away bets",
            "Boost home team probability by up to +10% for confirmed home fortresses",
        ],
        "tags": "home,fortress,home advantage,team pattern",
    },
    {
        "category": "team_rules", "confidence": 0.84, "version": "1.0", "source": "aurora",
        "title": "Set Piece Dependent Teams",
        "description": (
            "Some teams score 35%+ of their goals from set pieces. "
            "Set piece dependent teams benefit from corner markets (they take more corners to generate chances). "
            "Corners gained rate is more predictive than corners taken when evaluating set piece teams."
        ),
        "examples": [
            "Team that scores 40% from set pieces → generates high corner volume intentionally",
            "Aerial team vs weak corner defence → BTTS more likely via set piece goal",
        ],
        "tags": "set piece,corners,aerial,tactics",
    },

    # ── psychology ────────────────────────────────────────────────────────────
    {
        "category": "psychology", "confidence": 0.90, "version": "1.0", "source": "aurora",
        "title": "Recency Bias — Don't Over-Weight Last 3 Results",
        "description": (
            "Bettors consistently over-weight recent results vs season averages. "
            "A team on a 3-match losing streak is still defined by its season-long quality. "
            "Aurora uses season averages as primary signals and recent form as a secondary modifier. "
            "Never allow last 3 results to override season-level statistical evidence."
        ),
        "examples": [
            "Top team loses 3 in a row → model still rates them by season xG, not last 3 losses",
            "Bottom team wins 3 in a row → short streak unlikely to reflect true quality change",
        ],
        "tags": "recency bias,psychology,form,season average",
    },
    {
        "category": "psychology", "confidence": 0.88, "version": "1.0", "source": "aurora",
        "title": "Favourite Bias — Public Over-Bets Big Teams",
        "description": (
            "The public systematically over-bets favorites, compressing their odds by 5–12%. "
            "Big club matches (e.g. El Clásico, North London Derby) show the largest public bias. "
            "Value in big matches often lies with the underdog or draw, not the favorite."
        ),
        "examples": [
            "Real Madrid -1.5 in big match → odds 5-10% shorter than true probability",
            "Draw in derby match often undervalued by 3-8% due to public backing home team",
        ],
        "tags": "bias,favourite,public,big team,odds compression",
    },
    {
        "category": "psychology", "confidence": 0.85, "version": "1.0", "source": "aurora",
        "title": "Sunk Cost — Do Not Chase Losses",
        "description": (
            "Increasing stake sizes to recover losses is the most common cause of bankroll ruin. "
            "Each bet must be evaluated on its own merits, independent of previous results. "
            "Aurora never recommends increasing stakes after a losing run. "
            "The past is irrelevant to the EV of the next bet."
        ),
        "examples": [
            "Lost £100 → next bet is evaluated at same stake, not inflated",
            "3 losses in a row → reduce stake by 20% (protection mode), not increase",
        ],
        "tags": "sunk cost,chasing,loss,psychology,tilt",
    },

    # ── risk_management ────────────────────────────────────────────────────────
    {
        "category": "risk_management", "confidence": 0.92, "version": "1.0", "source": "aurora",
        "title": "Drawdown Stop-Loss",
        "description": (
            "When bankroll drawdown reaches 20%, enter protection mode: "
            "halve all stake sizes and only bet on High Confidence (≥7.0) recommendations. "
            "When drawdown reaches 30%, stop betting entirely and review strategy. "
            "Never trade through a 30%+ drawdown without methodology review."
        ),
        "examples": [
            "£1000 → £800 (20% down) → protection mode, half stakes",
            "£1000 → £700 (30% down) → full stop, methodology review required",
        ],
        "tags": "drawdown,stop loss,protection,bankroll",
    },
    {
        "category": "risk_management", "confidence": 0.89, "version": "1.0", "source": "aurora",
        "title": "Market Correlation Risk",
        "description": (
            "Over 2.5 goals and BTTS Yes are positively correlated (r ≈ 0.72). "
            "Home Win and Over 2.5 goals are also correlated when home team is dominant. "
            "Never place two highly correlated bets as if they are independent. "
            "Treat correlated bets as a single combined exposure."
        ),
        "examples": [
            "Over 2.5 + BTTS Yes in same match = combined correlated bet, size accordingly",
            "BTTS No + Under 2.5 = almost fully correlated — pick only one",
        ],
        "tags": "correlation,exposure,combined,risk",
    },
    {
        "category": "risk_management", "confidence": 0.87, "version": "1.0", "source": "aurora",
        "title": "Minimum Confidence Gate",
        "description": (
            "Aurora never recommends markets with confidence score < 5.0/10. "
            "A confidence below 5.0 means insufficient data to make a reliable prediction. "
            "This gate exists to prevent recommendations based on guesswork. "
            "The confidence gate is absolute — no exceptions regardless of EV."
        ),
        "examples": [
            "Pre-match without xG or lineup data → confidence 4.2 → no recommendation",
            "Live match minute 45 with stats → confidence 6.8 → recommendation allowed",
        ],
        "tags": "confidence gate,minimum,pre-match,live,data",
    },

    # ── red_flags ─────────────────────────────────────────────────────────────
    {
        "category": "red_flags", "confidence": 0.93, "version": "1.0", "source": "aurora",
        "title": "No xG Data Available",
        "description": (
            "When xG data is unavailable, Aurora's Poisson model relies on GPG season averages "
            "which carry significantly higher variance. "
            "All goal and BTTS probability estimates become 15–20% less reliable. "
            "Treat any recommendation made without xG data as low confidence."
        ),
        "examples": [
            "Match without xG → reduce Over/Under goal market confidence by 20%",
            "No xG and no standings → confidence cap at 4.5/10 regardless of other signals",
        ],
        "tags": "xg,missing data,confidence,low reliability,red flag",
    },
    {
        "category": "red_flags", "confidence": 0.91, "version": "1.0", "source": "aurora",
        "title": "New Manager Effect — First 3 Matches",
        "description": (
            "A new manager's first 3 matches have significantly higher variance. "
            "Tactical patterns, formations, and player roles are all in flux. "
            "Aurora's team_style and tactical_pattern models are not calibrated for new managers. "
            "Reduce all confidence by 1.5 points and avoid player markets entirely."
        ),
        "examples": [
            "New manager match 1 → avoid player to score/assist markets completely",
            "New manager match 2 → reduce recommended stake by 50%",
        ],
        "tags": "new manager,variance,uncertainty,red flag",
    },
    {
        "category": "red_flags", "confidence": 0.89, "version": "1.0", "source": "aurora",
        "title": "Low Methodology Score — Blocked Recommendation",
        "description": (
            "When Aurora's methodology score is below 5.5, the recommendation is blocked. "
            "This means the 15-category assessment found insufficient quality signals. "
            "Do not override a blocked recommendation — the block exists for a reason. "
            "A blocked recommendation is not a recommendation to bet on the opposite market."
        ),
        "examples": [
            "Methodology score 4.8 → block is correct, wait for more data (live match)",
            "Methodology score 3.2 → strong block, likely missing xG + lineup + standings",
        ],
        "tags": "methodology score,blocked,low confidence,red flag",
    },
    {
        "category": "red_flags", "confidence": 0.86, "version": "1.0", "source": "aurora",
        "title": "Match Postponement or Rearrangement Risk",
        "description": (
            "Matches played on a different date/venue than originally scheduled carry extra variance. "
            "Neutral venue matches nullify home advantage entirely. "
            "Late postponements (within 24 hours) create lineup uncertainty. "
            "Flag any match with recent schedule changes as high-uncertainty."
        ),
        "examples": [
            "Match moved to neutral venue → remove all home advantage from model",
            "Postponement with 48h notice → treat as pre-match with no lineup data",
        ],
        "tags": "postponement,neutral venue,schedule change,red flag",
    },

    # ── golden_rules ──────────────────────────────────────────────────────────
    {
        "category": "golden_rules", "confidence": 1.0, "version": "1.0", "source": "aurora",
        "title": "Never Bet Without Positive Expected Value",
        "description": (
            "This is Aurora's first and most important rule. "
            "Every bet placed must have positive expected value. "
            "Gut feeling, loyalty, and narrative do not create positive EV. "
            "If the model does not show +EV, there is no bet."
        ),
        "examples": [
            "Favourite team is playing → irrelevant if EV is negative",
            "Everyone is backing Team A → check the EV before following",
        ],
        "tags": "golden rule,ev,expected value,discipline",
    },
    {
        "category": "golden_rules", "confidence": 1.0, "version": "1.0", "source": "aurora",
        "title": "Never Bet When Confidence Is Below 5.0",
        "description": (
            "Aurora's confidence score measures data quality. Below 5.0 means Aurora is guessing. "
            "Guesses are not bets. "
            "No exceptions, no overrides. "
            "If you want to bet on a low-confidence match, that decision is yours — "
            "Aurora will not assist with bets it cannot support with data."
        ),
        "examples": [
            "Pre-match, no xG, no lineup → confidence 4.1 → NO BET",
            "Live match minute 25, stats just starting → confidence 4.8 → wait for minute 30",
        ],
        "tags": "golden rule,confidence,gate,no bet",
    },
    {
        "category": "golden_rules", "confidence": 1.0, "version": "1.0", "source": "aurora",
        "title": "Never Change Methodology Based on a Single Match",
        "description": (
            "The Aurora Evolution Engine suggests weight changes after every match. "
            "However, a single match result is statistically insignificant. "
            "Require at least 20–30 matches of consistent underperformance in a category "
            "before applying any weight change to brain/methodology.json. "
            "Single-match over-fitting is the fastest way to destroy a working model."
        ),
        "examples": [
            "xG failed in 1 match → do not reduce xG weight",
            "xG failed in 25 consecutive matches → review and adjust with evidence",
        ],
        "tags": "golden rule,methodology,overfitting,evolution,stability",
    },
    {
        "category": "golden_rules", "confidence": 1.0, "version": "1.0", "source": "aurora",
        "title": "Protect the Bankroll Above All Else",
        "description": (
            "Capital preservation comes before profit. "
            "A 50% bankroll loss requires 100% return to recover. "
            "A 20% bankroll loss requires 25% return to recover. "
            "Never risk ruin for any single bet. "
            "A smaller, protected bankroll grows steadily. A depleted bankroll cannot grow."
        ),
        "examples": [
            "Maximum single bet = 5% of bankroll, always",
            "Stop-loss at 20% drawdown — protect then rebuild",
        ],
        "tags": "golden rule,bankroll,protection,ruin,capital",
    },
]


def seed_knowledge_if_empty() -> None:
    """Populate knowledge_items with foundational rules if the table is empty."""
    existing = count_knowledge_items()
    if existing > 0:
        logger.info("Knowledge items already seeded (%d items), skipping.", existing)
        return
    for item in _SEED:
        save_knowledge_item(
            category=item["category"],
            title=item["title"],
            description=item["description"],
            examples=item.get("examples", []),
            confidence=item.get("confidence", 0.8),
            version=item.get("version", "1.0"),
            source=item.get("source", "aurora"),
            tags=item.get("tags", ""),
        )
    logger.info("Aurora knowledge base seeded with %d foundational items.", len(_SEED))


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
