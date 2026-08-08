"""
Aurora v4.5 — Prediction / Experience Memory Foundation (PASSIVE).

Stores conversational predictions and entity experience.
Does NOT alter weights, probabilities, confidence, methodology, or learning engines.

Fail-open. Additive. Reversible.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parents[2] / "prediction_experience.db"

_LOCK = threading.RLock()
_INITIALIZED = False

# v4.5.1 — growth guards (passive store only)
PREDICTION_TTL_DAYS = 30
EXPERIENCE_TTL_DAYS = 60
MAX_PREDICTIONS = 5000
MAX_EXPERIENCE_ROWS = 2000

_CREATE_PREDICTIONS = """
CREATE TABLE IF NOT EXISTS predictions (
    prediction_id TEXT PRIMARY KEY,
    fixture TEXT,
    market TEXT,
    recommendation TEXT,
    confidence REAL,
    reasoning_summary TEXT,
    created_at TEXT NOT NULL,
    result TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    session_id TEXT,
    home TEXT,
    away TEXT
)
"""

_CREATE_EXPERIENCE = """
CREATE TABLE IF NOT EXISTS experience_memory (
    entity TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    times_seen INTEGER NOT NULL DEFAULT 0,
    last_seen TEXT,
    success_rate REAL,
    notes TEXT,
    PRIMARY KEY (entity, entity_type)
)
"""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return None


def purge_prediction_memory(
    *,
    prediction_ttl_days: int = PREDICTION_TTL_DAYS,
    experience_ttl_days: int = EXPERIENCE_TTL_DAYS,
    max_predictions: int = MAX_PREDICTIONS,
    max_experience: int = MAX_EXPERIENCE_ROWS,
) -> dict[str, int]:
    """
    Delete expired / excess rows. Fail-open. Does not touch learning engines.
    Does NOT call init_prediction_memory (avoids recursion).
    """
    stats = {"predictions_deleted": 0, "experience_deleted": 0, "trimmed": 0}
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            with _conn() as conn:
                conn.execute(_CREATE_PREDICTIONS)
                conn.execute(_CREATE_EXPERIENCE)
                now = datetime.now(timezone.utc)
                pred_cut = now.timestamp() - prediction_ttl_days * 86400
                exp_cut = now.timestamp() - experience_ttl_days * 86400
                rows = conn.execute(
                    "SELECT prediction_id, created_at FROM predictions"
                ).fetchall()
                for r in rows:
                    ts = _parse_ts(r["created_at"])
                    if ts and ts.timestamp() < pred_cut:
                        conn.execute(
                            "DELETE FROM predictions WHERE prediction_id = ?",
                            (r["prediction_id"],),
                        )
                        stats["predictions_deleted"] += 1
                count = conn.execute("SELECT COUNT(*) AS c FROM predictions").fetchone()["c"]
                if count > max_predictions:
                    overflow = int(count) - int(max_predictions)
                    old = conn.execute(
                        """
                        SELECT prediction_id FROM predictions
                        ORDER BY created_at ASC
                        LIMIT ?
                        """,
                        (overflow,),
                    ).fetchall()
                    for o in old:
                        conn.execute(
                            "DELETE FROM predictions WHERE prediction_id = ?",
                            (o["prediction_id"],),
                        )
                        stats["trimmed"] += 1
                erows = conn.execute(
                    "SELECT entity, entity_type, last_seen FROM experience_memory"
                ).fetchall()
                for r in erows:
                    ts = _parse_ts(r["last_seen"])
                    if ts and ts.timestamp() < exp_cut:
                        conn.execute(
                            """
                            DELETE FROM experience_memory
                            WHERE entity = ? AND entity_type = ?
                            """,
                            (r["entity"], r["entity_type"]),
                        )
                        stats["experience_deleted"] += 1
                ecount = conn.execute(
                    "SELECT COUNT(*) AS c FROM experience_memory"
                ).fetchone()["c"]
                if ecount > max_experience:
                    overflow = int(ecount) - int(max_experience)
                    old = conn.execute(
                        """
                        SELECT entity, entity_type FROM experience_memory
                        ORDER BY COALESCE(last_seen, '') ASC
                        LIMIT ?
                        """,
                        (overflow,),
                    ).fetchall()
                    for o in old:
                        conn.execute(
                            """
                            DELETE FROM experience_memory
                            WHERE entity = ? AND entity_type = ?
                            """,
                            (o["entity"], o["entity_type"]),
                        )
                        stats["trimmed"] += 1
                conn.commit()
        return stats
    except Exception as exc:
        logger.warning("purge_prediction_memory fail-open: %s", exc)
        return stats


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_prediction_memory() -> None:
    global _INITIALIZED
    with _LOCK:
        if _INITIALIZED:
            return
        try:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            with _conn() as conn:
                conn.execute(_CREATE_PREDICTIONS)
                conn.execute(_CREATE_EXPERIENCE)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_pred_fixture ON predictions(fixture)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_pred_market ON predictions(market)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_pred_status ON predictions(status)"
                )
                conn.commit()
            _INITIALIZED = True
            try:
                purge_prediction_memory()
            except Exception:
                pass
        except Exception as exc:
            logger.warning("init_prediction_memory fail-open: %s", exc)


def save_prediction(
    *,
    fixture: str | None = None,
    market: str | None = None,
    recommendation: str | None = None,
    confidence: float | None = None,
    reasoning_summary: str | None = None,
    session_id: str | None = None,
    home: str | None = None,
    away: str | None = None,
    status: str = "open",
) -> str | None:
    """Persist a conversational prediction. Returns prediction_id or None."""
    try:
        init_prediction_memory()
        pid = str(uuid.uuid4())
        with _LOCK:
            with _conn() as conn:
                conn.execute(
                    """
                    INSERT INTO predictions (
                        prediction_id, fixture, market, recommendation, confidence,
                        reasoning_summary, created_at, result, status,
                        session_id, home, away
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)
                    """,
                    (
                        pid,
                        fixture,
                        market,
                        recommendation,
                        float(confidence) if confidence is not None else None,
                        (reasoning_summary or "")[:1200] or None,
                        _now(),
                        status or "open",
                        session_id,
                        home,
                        away,
                    ),
                )
                conn.commit()
        # Passive experience touch — no weight changes
        if fixture:
            touch_experience(fixture, "fixture", note="prediction_saved")
        if market:
            touch_experience(market, "market", note="prediction_saved")
        if home:
            touch_experience(home, "team", note="prediction_saved")
        if away:
            touch_experience(away, "team", note="prediction_saved")
        return pid
    except Exception as exc:
        logger.warning("save_prediction fail-open: %s", exc)
        return None


def save_reasoning(
    *,
    fixture: str | None = None,
    market: str | None = None,
    reasoning_summary: str,
    session_id: str | None = None,
    confidence: float | None = None,
) -> str | None:
    """Store a reasoning snapshot as an open prediction row (passive)."""
    return save_prediction(
        fixture=fixture,
        market=market,
        recommendation=None,
        confidence=confidence,
        reasoning_summary=reasoning_summary,
        session_id=session_id,
        status="reasoning",
    )


def resolve_prediction(
    prediction_id: str,
    *,
    result: str,
    status: str = "resolved",
) -> bool:
    """Mark a prediction resolved. Does NOT feed learning engines."""
    try:
        init_prediction_memory()
        with _LOCK:
            with _conn() as conn:
                cur = conn.execute(
                    """
                    UPDATE predictions
                    SET result = ?, status = ?
                    WHERE prediction_id = ?
                    """,
                    (result, status, prediction_id),
                )
                conn.commit()
                return cur.rowcount > 0
    except Exception as exc:
        logger.warning("resolve_prediction fail-open: %s", exc)
        return False


def touch_experience(
    entity: str,
    entity_type: str,
    *,
    note: str | None = None,
) -> None:
    """Increment times_seen / last_seen. Never mutates success_rate from outcomes here."""
    try:
        if not entity or not entity_type:
            return
        init_prediction_memory()
        now = _now()
        with _LOCK:
            with _conn() as conn:
                row = conn.execute(
                    """
                    SELECT times_seen, notes FROM experience_memory
                    WHERE entity = ? AND entity_type = ?
                    """,
                    (entity, entity_type),
                ).fetchone()
                if row:
                    notes = row["notes"] or ""
                    if note and note not in notes:
                        notes = (notes + " | " + note).strip(" |")[:500]
                    conn.execute(
                        """
                        UPDATE experience_memory
                        SET times_seen = ?, last_seen = ?, notes = ?
                        WHERE entity = ? AND entity_type = ?
                        """,
                        (int(row["times_seen"] or 0) + 1, now, notes or None, entity, entity_type),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO experience_memory (
                            entity, entity_type, times_seen, last_seen, success_rate, notes
                        ) VALUES (?, ?, 1, ?, NULL, ?)
                        """,
                        (entity, entity_type, now, note),
                    )
                conn.commit()
    except Exception as exc:
        logger.warning("touch_experience fail-open: %s", exc)


def get_market_history(market: str, *, limit: int = 20) -> list[dict[str, Any]]:
    try:
        init_prediction_memory()
        with _conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM predictions
                WHERE market = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (market, int(limit)),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception as exc:
        logger.warning("get_market_history fail-open: %s", exc)
        return []


def get_team_history(team: str, *, limit: int = 20) -> list[dict[str, Any]]:
    try:
        init_prediction_memory()
        with _conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM predictions
                WHERE home = ? OR away = ? OR fixture LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (team, team, f"%{team}%", int(limit)),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception as exc:
        logger.warning("get_team_history fail-open: %s", exc)
        return []


def get_experience(entity: str, entity_type: str | None = None) -> dict[str, Any] | None:
    try:
        init_prediction_memory()
        with _conn() as conn:
            if entity_type:
                row = conn.execute(
                    """
                    SELECT * FROM experience_memory
                    WHERE entity = ? AND entity_type = ?
                    """,
                    (entity, entity_type),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT * FROM experience_memory
                    WHERE entity = ?
                    ORDER BY times_seen DESC
                    LIMIT 1
                    """,
                    (entity,),
                ).fetchone()
            return dict(row) if row else None
    except Exception as exc:
        logger.warning("get_experience fail-open: %s", exc)
        return None


_STORE_COUNTER = 0


def maybe_store_from_turn(
    *,
    message: str,
    payload: dict[str, Any] | None,
    ctx: dict[str, Any] | None,
    session_id: str | None = None,
    reflection: dict[str, Any] | None = None,
) -> str | None:
    """
    Passive hook after a turn. Stores experience when there is a fixture/market
    or a deep-reasoning conclusion. Never changes decisions.
    """
    try:
        payload = payload or {}
        ctx = ctx or {}
        intent = str(payload.get("intent") or "")
        if intent in {"small_talk", "greeting", "emotional", "help", "identity"}:
            return None

        fx = None
        market = None
        home = None
        away = None
        try:
            from src.conversation.conversation_state import get_state

            st = get_state(ctx) or {}
            fx = st.get("active_fixture") or ctx.get("last_match")
            market = st.get("active_market")
            home = st.get("active_home") or ctx.get("last_home")
            away = st.get("active_away") or ctx.get("last_away")
        except Exception:
            fx = ctx.get("last_match")
            home = ctx.get("last_home")
            away = ctx.get("last_away")

        rec = payload.get("final_recommendation") or ""
        if isinstance(payload.get("best_markets"), list) and payload["best_markets"]:
            top = payload["best_markets"][0]
            if isinstance(top, dict):
                market = market or top.get("market")
                if not rec:
                    rec = str(top.get("market") or "")

        conf = None
        csec = payload.get("confidence")
        if isinstance(csec, dict):
            try:
                conf = float(csec.get("score") or 0) or None
            except (TypeError, ValueError):
                conf = None

        deep = (reflection or {}).get("deep") if isinstance(reflection, dict) else None
        reasoning = ""
        if isinstance(deep, dict):
            reasoning = str(deep.get("final_position") or deep.get("user_goal") or "")
            if not reasoning:
                bits = []
                for k in ("positive_factors", "negative_factors", "risk_scenarios"):
                    vals = deep.get(k) or []
                    if vals:
                        bits.append(f"{k}: {', '.join(str(v) for v in vals[:3])}")
                reasoning = " | ".join(bits)
        if not reasoning:
            reasoning = str(
                (reflection or {}).get("why_this_answer")
                or payload.get("executive_summary")
                or ""
            )[:800]

        # Touch entities even without full prediction
        if fx:
            touch_experience(str(fx), "fixture", note="turn_seen")
        if market:
            touch_experience(str(market), "market", note="turn_seen")
        if home:
            touch_experience(str(home), "team", note="turn_seen")
        if away:
            touch_experience(str(away), "team", note="turn_seen")

        # Opportunistic purge every ~25 stores
        global _STORE_COUNTER
        _STORE_COUNTER += 1
        if _STORE_COUNTER % 25 == 0:
            try:
                purge_prediction_memory()
            except Exception:
                pass

        if not (fx or market or reasoning):
            return None

        # Prefer storing when we have a real recommendation or deep position
        has_depth = bool(isinstance(deep, dict) and deep.get("final_position"))
        has_analysis = intent in {
            "analyze_match",
            "follow_up",
            "live_opportunities",
            "conversation_assist",
        }
        if not (has_depth or has_analysis or rec):
            return None

        return save_prediction(
            fixture=str(fx) if fx else None,
            market=str(market) if market else None,
            recommendation=str(rec)[:400] if rec else None,
            confidence=conf,
            reasoning_summary=reasoning[:1200] if reasoning else None,
            session_id=session_id,
            home=str(home) if home else None,
            away=str(away) if away else None,
            status="open" if rec else "reasoning",
        )
    except Exception as exc:
        logger.warning("maybe_store_from_turn fail-open: %s", exc)
        return None
