"""
Aurora Learning Engine — SQLite persistence layer.

Two tables:
  prediction_history  — one row per prediction Aurora makes
  learning_rules      — per-market win/loss/accuracy aggregates (auto-maintained)

Public API
----------
init_learning_db()
save_prediction(...)                  — called automatically after every /aurora/score
resolve_predictions(fixture_id, outcomes)  — called automatically when match finishes
get_learning_stats()                  — powers GET /aurora/learning/stats

Design rules
------------
- Never raises exceptions into callers: every public function catches and logs errors.
  The learning engine must never cause a prediction endpoint to fail.
- Atomic: resolve_predictions() updates prediction_history AND learning_rules in one
  transaction so stats are always consistent.
- Idempotent: if a fixture's predictions are already resolved, resolve_predictions()
  is a no-op.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "aurora.db"

# ---------------------------------------------------------------------------
# Canonical market keys — used to interpret outcomes dict from score.py
# ---------------------------------------------------------------------------

MARKET_KEYS = [
    "home_win",
    "draw",
    "away_win",
    "btts",
    "over_25_goals",
    "over_85_corners",
    "over_45_cards",
]

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _row(r: sqlite3.Row) -> dict:
    return dict(r)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_CREATE_PREDICTION_HISTORY = """
CREATE TABLE IF NOT EXISTS prediction_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id  INTEGER NOT NULL,
    date        TEXT,
    home_team   TEXT,
    away_team   TEXT,
    league      TEXT,
    market      TEXT    NOT NULL,
    prediction  TEXT    NOT NULL,
    confidence  REAL,
    risk        TEXT,
    odds        REAL,
    stake       REAL,
    result      TEXT,
    profit      REAL,
    reason      TEXT,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
"""

_CREATE_PREDICTION_IDX = """
CREATE INDEX IF NOT EXISTS idx_ph_fixture ON prediction_history (fixture_id);
"""

_CREATE_LEARNING_RULES = """
CREATE TABLE IF NOT EXISTS learning_rules (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    rule         TEXT    NOT NULL UNIQUE,
    wins         INTEGER NOT NULL DEFAULT 0,
    losses       INTEGER NOT NULL DEFAULT 0,
    accuracy     REAL    NOT NULL DEFAULT 0.0,
    last_updated TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
"""


def init_learning_db() -> None:
    """Create prediction_history and learning_rules tables if they don't exist."""
    try:
        with _conn() as conn:
            conn.execute(_CREATE_PREDICTION_HISTORY)
            conn.execute(_CREATE_PREDICTION_IDX)
            conn.execute(_CREATE_LEARNING_RULES)
            conn.commit()
        logger.info("Aurora Learning DB initialised at %s", DB_PATH)
    except Exception as exc:
        logger.error("Failed to initialise learning DB: %s", exc)


# ---------------------------------------------------------------------------
# save_prediction — called after every /aurora/score
# ---------------------------------------------------------------------------


def save_prediction(
    *,
    fixture_id: int,
    date: str | None,
    home_team: str,
    away_team: str,
    league: str | None,
    market: str,
    prediction: str,
    confidence: float,
    risk: str,
    odds: float | None = None,
    stake: float | None = None,
    reason: str | None = None,
) -> int | None:
    """
    Insert a new pending prediction row.

    If a pending prediction already exists for this (fixture_id, market) pair,
    the insert is skipped to avoid duplicating identical pre-match calls.
    Returns the new row id, or None on skip/error.
    """
    try:
        with _conn() as conn:
            existing = conn.execute(
                "SELECT id FROM prediction_history "
                "WHERE fixture_id = ? AND market = ? AND result IS NULL",
                (fixture_id, market),
            ).fetchone()
            if existing:
                return None  # already have a pending prediction for this market

            cur = conn.execute(
                """INSERT INTO prediction_history
                   (fixture_id, date, home_team, away_team, league,
                    market, prediction, confidence, risk, odds, stake, reason, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    fixture_id, date, home_team, away_team, league,
                    market, prediction, confidence, risk, odds, stake, reason, _now(),
                ),
            )
            conn.commit()
            return cur.lastrowid
    except Exception as exc:
        logger.error("save_prediction failed for fixture %s market %s: %s", fixture_id, market, exc)
        return None


# ---------------------------------------------------------------------------
# resolve_predictions — called when match is finished
# ---------------------------------------------------------------------------


def resolve_predictions(fixture_id: int, outcomes: dict[str, bool]) -> list[dict]:
    """
    Compare pending predictions for *fixture_id* against the actual match outcomes.

    outcomes: mapping of market key → True (prediction correct / win) | False (loss)
    Example:
        {"home_win": True, "btts": False, "over_25_goals": True, ...}

    Returns the list of resolved prediction rows (empty if none pending).
    Raises nothing — errors are logged only.
    """
    resolved: list[dict] = []
    try:
        with _conn() as conn:
            pending = conn.execute(
                "SELECT * FROM prediction_history "
                "WHERE fixture_id = ? AND result IS NULL",
                (fixture_id,),
            ).fetchall()

            if not pending:
                return []

            for row in pending:
                market_key = row["market"]
                if market_key not in outcomes:
                    continue
                won = outcomes[market_key]
                result_str = "win" if won else "loss"

                # profit: odds-based if odds available, else +1 / -1 unit
                odds_val = row["odds"]
                stake_val = row["stake"] or 1.0
                if won:
                    profit = round(stake_val * ((odds_val - 1) if odds_val else 1.0), 4)
                else:
                    profit = -stake_val

                conn.execute(
                    "UPDATE prediction_history SET result = ?, profit = ? WHERE id = ?",
                    (result_str, profit, row["id"]),
                )
                _upsert_learning_rule(conn, market_key, won)
                resolved.append({**_row(row), "result": result_str, "profit": profit})

            conn.commit()
    except Exception as exc:
        logger.error("resolve_predictions failed for fixture %s: %s", fixture_id, exc)

    return resolved


def _upsert_learning_rule(conn: sqlite3.Connection, market: str, won: bool) -> None:
    """Insert or update the win/loss/accuracy record for a market rule."""
    existing = conn.execute(
        "SELECT id, wins, losses FROM learning_rules WHERE rule = ?", (market,)
    ).fetchone()
    now = _now()
    if existing:
        wins = existing["wins"] + (1 if won else 0)
        losses = existing["losses"] + (0 if won else 1)
        total = wins + losses
        accuracy = round(wins / total * 100, 2) if total > 0 else 0.0
        conn.execute(
            "UPDATE learning_rules SET wins = ?, losses = ?, accuracy = ?, last_updated = ? "
            "WHERE rule = ?",
            (wins, losses, accuracy, now, market),
        )
    else:
        wins = 1 if won else 0
        losses = 0 if won else 1
        accuracy = 100.0 if won else 0.0
        conn.execute(
            "INSERT INTO learning_rules (rule, wins, losses, accuracy, last_updated) "
            "VALUES (?, ?, ?, ?, ?)",
            (market, wins, losses, accuracy, now),
        )


# ---------------------------------------------------------------------------
# get_learning_stats — powers GET /aurora/learning/stats
# ---------------------------------------------------------------------------


def get_learning_stats() -> dict:
    """
    Compute aggregate learning statistics from prediction_history and learning_rules.

    Returns a dict with:
      total_predictions, wins, losses, pending, roi_pct, avg_confidence,
      current_accuracy, best_market, worst_market, best_league, worst_league,
      market_breakdown, league_breakdown.
    """
    try:
        with _conn() as conn:
            # ── Totals ──────────────────────────────────────────────────────
            totals = _row(conn.execute(
                """SELECT
                     COUNT(*) AS total,
                     SUM(CASE WHEN result = 'win'  THEN 1 ELSE 0 END) AS wins,
                     SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) AS losses,
                     SUM(CASE WHEN result IS NULL  THEN 1 ELSE 0 END) AS pending,
                     ROUND(AVG(confidence), 2)                         AS avg_confidence,
                     ROUND(SUM(COALESCE(profit, 0)), 4)                AS total_profit,
                     ROUND(SUM(COALESCE(stake,  1)), 4)                AS total_staked
                   FROM prediction_history"""
            ).fetchone())

            wins = totals["wins"] or 0
            losses = totals["losses"] or 0
            decided = wins + losses
            current_accuracy = round(wins / decided * 100, 2) if decided > 0 else None

            total_profit = totals["total_profit"] or 0.0
            total_staked = totals["total_staked"] or 0.0
            roi_pct = round(total_profit / total_staked * 100, 2) if total_staked > 0 else None

            # ── Market breakdown from learning_rules ─────────────────────────
            rules = [
                _row(r) for r in conn.execute(
                    "SELECT rule, wins, losses, accuracy FROM learning_rules ORDER BY accuracy DESC"
                ).fetchall()
            ]

            best_market = rules[0]["rule"] if rules else None
            worst_market = rules[-1]["rule"] if len(rules) > 1 else None

            # ── League breakdown ─────────────────────────────────────────────
            league_rows = [
                _row(r) for r in conn.execute(
                    """SELECT
                         league,
                         COUNT(*) AS total,
                         SUM(CASE WHEN result = 'win'  THEN 1 ELSE 0 END) AS wins,
                         SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) AS losses,
                         ROUND(
                           SUM(CASE WHEN result = 'win' THEN 1.0 ELSE 0 END) /
                           NULLIF(
                             SUM(CASE WHEN result IN ('win','loss') THEN 1 ELSE 0 END), 0
                           ) * 100, 2
                         ) AS accuracy
                       FROM prediction_history
                       WHERE league IS NOT NULL
                       GROUP BY league
                       HAVING SUM(CASE WHEN result IN ('win','loss') THEN 1 ELSE 0 END) > 0
                       ORDER BY accuracy DESC"""
                ).fetchall()
            ]

            best_league = league_rows[0]["league"] if league_rows else None
            worst_league = league_rows[-1]["league"] if len(league_rows) > 1 else None

        return {
            "total_predictions":  totals["total"] or 0,
            "wins":               wins,
            "losses":             losses,
            "pending":            totals["pending"] or 0,
            "current_accuracy":   current_accuracy,
            "roi_pct":            roi_pct,
            "avg_confidence":     totals["avg_confidence"],
            "best_market":        best_market,
            "worst_market":       worst_market,
            "best_league":        best_league,
            "worst_league":       worst_league,
            "market_breakdown":   rules,
            "league_breakdown":   league_rows,
        }

    except Exception as exc:
        logger.error("get_learning_stats failed: %s", exc)
        return {"error": str(exc)}
