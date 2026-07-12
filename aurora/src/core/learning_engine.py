"""
Learning Engine — read-only historical context from the learning database.

Queries prediction_history and learning_rules to surface:
  - Per-market historical win rates
  - League-specific accuracy
  - General performance notes

This engine READS only — it never writes to the database.
Writing (save_prediction, resolve_predictions) remains a side-effect in the
router layer so the decision pipeline stays pure and testable.

Public API
----------
  run(league=None) -> LearningContext
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent.parent / "aurora.db"


@dataclass
class LearningContext:
    """Historical performance context returned by the Learning Engine."""

    market_accuracy:  dict[str, float]   # market key → win rate % (from learning_rules)
    league_accuracy:  float | None        # accuracy % for this specific league (or None)
    league_name:      str | None
    total_resolved:   int                 # total predictions with a result in the DB
    total_pending:    int
    notes:            list[str] = field(default_factory=list)

    @property
    def has_history(self) -> bool:
        return self.total_resolved > 0

    def accuracy_for(self, market_key: str) -> float | None:
        """Return historical accuracy for a market, or None if unknown."""
        return self.market_accuracy.get(market_key)

    def confidence_modifier(self, market_key: str) -> float:
        """
        Tiny confidence boost (+0.3) when historical accuracy ≥ 60%,
        slight penalty (−0.2) when accuracy ≤ 40%.  Zero otherwise.
        Future hook for AI calibration.
        """
        acc = self.accuracy_for(market_key)
        if acc is None:
            return 0.0
        if acc >= 60.0:
            return 0.3
        if acc <= 40.0:
            return -0.2
        return 0.0


def run(league: str | None = None) -> LearningContext:
    """
    Query the learning database for historical context.

    Parameters
    ----------
    league : league name to look up league-specific accuracy (optional)
    """
    empty = LearningContext(
        market_accuracy={}, league_accuracy=None, league_name=league,
        total_resolved=0, total_pending=0, notes=[],
    )

    if not DB_PATH.exists():
        return empty

    try:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row

        # ── Per-market accuracy from learning_rules ──────────────────────────
        rule_rows = conn.execute(
            "SELECT rule, wins, losses, accuracy FROM learning_rules"
        ).fetchall()
        market_accuracy = {r["rule"]: r["accuracy"] for r in rule_rows}

        # ── Totals from prediction_history ────────────────────────────────────
        totals = conn.execute(
            """SELECT
                 SUM(CASE WHEN result IN ('win','loss') THEN 1 ELSE 0 END) AS resolved,
                 SUM(CASE WHEN result IS NULL            THEN 1 ELSE 0 END) AS pending
               FROM prediction_history"""
        ).fetchone()
        total_resolved = int(totals["resolved"] or 0)
        total_pending  = int(totals["pending"]  or 0)

        # ── League-specific accuracy ──────────────────────────────────────────
        league_accuracy = None
        if league:
            lg_row = conn.execute(
                """SELECT
                     ROUND(
                       SUM(CASE WHEN result = 'win' THEN 1.0 ELSE 0 END) /
                       NULLIF(SUM(CASE WHEN result IN ('win','loss') THEN 1 ELSE 0 END), 0)
                       * 100, 2
                     ) AS accuracy
                   FROM prediction_history
                   WHERE league = ?""",
                (league,),
            ).fetchone()
            if lg_row and lg_row["accuracy"] is not None:
                league_accuracy = float(lg_row["accuracy"])

        conn.close()

        # ── Notes ─────────────────────────────────────────────────────────────
        notes: list[str] = []
        if total_resolved > 0:
            wins = sum(1 for r in rule_rows if r["wins"] > r["losses"])
            notes.append(
                f"Based on {total_resolved} resolved prediction{'s' if total_resolved != 1 else ''}."
            )
        if league_accuracy is not None:
            notes.append(f"Historical accuracy in {league}: {league_accuracy:.1f}%.")

        return LearningContext(
            market_accuracy=market_accuracy,
            league_accuracy=league_accuracy,
            league_name=league,
            total_resolved=total_resolved,
            total_pending=total_pending,
            notes=notes,
        )

    except Exception as exc:
        logger.error("LearningEngine query failed: %s", exc)
        return empty
