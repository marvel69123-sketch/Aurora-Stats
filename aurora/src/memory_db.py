"""
Aurora Memory Engine — permanent cross-session knowledge store.

Aurora never loses knowledge. Every prediction, lesson, and insight is written
here and recalled before any new recommendation is generated.

Collections (14)
----------------
  methodologies       — methodology versions and configuration history
  betting_patterns    — recurring patterns observed across fixtures
  successful_patterns — patterns associated with winning recommendations
  failed_patterns     — patterns associated with losing recommendations
  bankroll_sessions   — daily bankroll session summaries
  user_preferences    — user-level preferences and settings
  market_statistics   — per-market aggregate statistics
  referee_profiles    — referee card/foul tendencies
  league_profiles     — league-level scoring and style patterns
  team_profiles       — team-level historical performance summaries
  player_profiles     — player-level statistical notes
  tactical_patterns   — formation and tactical trend observations
  lessons_learned     — post-match analysis and lessons
  daily_logs          — daily activity summaries

Core API
--------
  remember(collection, content, **kwargs)  → int  (entry id)
  recall(collection, **filters)            → list[dict]
  search_memory(query, collection, limit)  → list[dict]
  learn(fixture_id, hn, an, league, ...)  → None

Auto-hooks (called by routers — never raise)
  remember_recommendation(decision)       → None
  remember_lesson(fixture_id, ...)        → None
  remember_methodology_change(info)       → None
  remember_bankroll_session(summary)      → None
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "aurora.db"

COLLECTIONS = [
    "methodologies",
    "betting_patterns",
    "successful_patterns",
    "failed_patterns",
    "bankroll_sessions",
    "user_preferences",
    "market_statistics",
    "referee_profiles",
    "league_profiles",
    "team_profiles",
    "player_profiles",
    "tactical_patterns",
    "lessons_learned",
    "daily_logs",
    "improvement_history",
]


# ---------------------------------------------------------------------------
# Database init
# ---------------------------------------------------------------------------


def init_memory_db() -> None:
    """Create the memory table and indexes if they don't exist."""
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS memory (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                collection  TEXT    NOT NULL,
                key         TEXT,
                tags        TEXT    DEFAULT '[]',
                content     TEXT    NOT NULL DEFAULT '{}',
                summary     TEXT    DEFAULT '',
                fixture_id  INTEGER,
                league      TEXT,
                team        TEXT,
                market      TEXT,
                confidence  REAL,
                importance  INTEGER DEFAULT 5,
                created_at  TEXT    NOT NULL,
                updated_at  TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_mem_collection  ON memory(collection);
            CREATE INDEX IF NOT EXISTS idx_mem_key         ON memory(collection, key);
            CREATE INDEX IF NOT EXISTS idx_mem_fixture     ON memory(fixture_id);
            CREATE INDEX IF NOT EXISTS idx_mem_league      ON memory(league);
            CREATE INDEX IF NOT EXISTS idx_mem_team        ON memory(team);
            CREATE INDEX IF NOT EXISTS idx_mem_market      ON memory(market);
            CREATE INDEX IF NOT EXISTS idx_mem_created     ON memory(created_at);
            CREATE INDEX IF NOT EXISTS idx_mem_importance  ON memory(importance DESC);
        """)
        conn.commit()
    logger.info("Aurora Memory Engine initialised — %d collections available", len(COLLECTIONS))


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    try:
        d["content"] = json.loads(d.get("content") or "{}")
    except Exception:
        pass
    try:
        d["tags"] = json.loads(d.get("tags") or "[]")
    except Exception:
        pass
    return d


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------


def remember(
    collection:  str,
    content:     dict | Any,
    summary:     str = "",
    key:         str | None = None,
    tags:        list[str] | None = None,
    fixture_id:  int | None = None,
    league:      str | None = None,
    team:        str | None = None,
    market:      str | None = None,
    confidence:  float | None = None,
    importance:  int = 5,
) -> int:
    """
    Save a memory entry to the specified collection.

    If `key` is provided and a record with that (collection, key) already
    exists, the existing record is updated rather than duplicated.

    Returns the row id of the saved entry.
    """
    if collection not in COLLECTIONS:
        raise ValueError(f"Unknown collection '{collection}'. Valid: {COLLECTIONS}")

    content_json = json.dumps(content, default=str, ensure_ascii=False)
    tags_json    = json.dumps(tags or [], ensure_ascii=False)
    now          = _now()

    with _conn() as conn:
        if key:
            existing = conn.execute(
                "SELECT id FROM memory WHERE collection = ? AND key = ?",
                (collection, key),
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE memory
                       SET content=?, summary=?, tags=?, fixture_id=?, league=?,
                           team=?, market=?, confidence=?, importance=?, updated_at=?
                       WHERE id=?""",
                    (content_json, summary, tags_json, fixture_id, league,
                     team, market, confidence, importance, now, existing["id"]),
                )
                conn.commit()
                return existing["id"]

        cursor = conn.execute(
            """INSERT INTO memory
               (collection, key, tags, content, summary, fixture_id, league,
                team, market, confidence, importance, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (collection, key, tags_json, content_json, summary,
             fixture_id, league, team, market, confidence, importance, now),
        )
        conn.commit()
        return cursor.lastrowid or 0


def recall(
    collection:  str,
    key:         str | None = None,
    fixture_id:  int | None = None,
    league:      str | None = None,
    team:        str | None = None,
    market:      str | None = None,
    importance_gte: int = 0,
    limit:       int = 20,
    offset:      int = 0,
) -> list[dict]:
    """
    Retrieve memory entries from a collection with optional filters.

    Results are ordered by importance (desc) then created_at (desc).
    """
    clauses = ["collection = ?"]
    params:  list[Any] = [collection]

    if key:
        clauses.append("key = ?");          params.append(key)
    if fixture_id is not None:
        clauses.append("fixture_id = ?");   params.append(fixture_id)
    if league:
        clauses.append("league = ?");       params.append(league)
    if team:
        clauses.append("team = ?");         params.append(team)
    if market:
        clauses.append("market = ?");       params.append(market)
    if importance_gte > 0:
        clauses.append("importance >= ?");  params.append(importance_gte)

    where = " AND ".join(clauses)
    params += [limit, offset]

    with _conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM memory WHERE {where} "
            f"ORDER BY importance DESC, created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def search_memory(
    query:       str,
    collection:  str | None = None,
    tags:        list[str] | None = None,
    league:      str | None = None,
    team:        str | None = None,
    limit:       int = 20,
    offset:      int = 0,
) -> list[dict]:
    """
    Full-text search across memory entries.

    Searches: summary, content (JSON text), tags.
    Filters by collection, league, and team if provided.
    Results ranked by importance then recency.
    """
    like  = f"%{query}%"
    clauses = ["(summary LIKE ? OR content LIKE ? OR tags LIKE ?)"]
    params: list[Any] = [like, like, like]

    if collection:
        clauses.append("collection = ?"); params.append(collection)
    if league:
        clauses.append("league = ?");     params.append(league)
    if team:
        clauses.append("team = ?");       params.append(team)
    if tags:
        for tag in tags:
            clauses.append("tags LIKE ?"); params.append(f'%"{tag}"%')

    where = " AND ".join(clauses)
    params += [limit, offset]

    with _conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM memory WHERE {where} "
            f"ORDER BY importance DESC, created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_history(
    collection:  str | None = None,
    limit:       int = 50,
    offset:      int = 0,
) -> dict:
    """Return paginated history across one or all collections."""
    clauses: list[str] = []
    params:  list[Any] = []

    if collection and collection != "all":
        clauses.append("collection = ?"); params.append(collection)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params += [limit, offset]

    with _conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM memory {where}", params[:-2] or []
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM memory {where} "
            f"ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "collection": collection or "all",
        "records": [_row_to_dict(r) for r in rows],
    }


def collection_stats() -> list[dict]:
    """Return entry counts and latest timestamp per collection."""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT collection,
                      COUNT(*) AS total,
                      MAX(created_at) AS latest,
                      AVG(importance) AS avg_importance
               FROM memory
               GROUP BY collection
               ORDER BY collection"""
        ).fetchall()
    counts = {r["collection"]: dict(r) for r in rows}
    return [
        {
            "collection":    col,
            "total":         counts.get(col, {}).get("total", 0),
            "latest":        counts.get(col, {}).get("latest"),
            "avg_importance": round(counts.get(col, {}).get("avg_importance") or 0, 1),
        }
        for col in COLLECTIONS
    ]


# ---------------------------------------------------------------------------
# learn() — generate a post-match lesson
# ---------------------------------------------------------------------------


def learn(
    fixture_id: int,
    hn:         str,
    an:         str,
    league:     str | None,
    methodology_score: float,
    overall_confidence: float,
    best_market:   str,
    market_prob:   float,
    risk_level:    str,
    is_finished:   bool,
    h_goals:       int,
    a_goals:       int,
    total_corners: int,
    total_cards:   int,
    methodology_categories: dict | None = None,
    outcomes:      dict | None = None,
) -> None:
    """
    Generate and store a lesson from a match — called automatically for
    every finished fixture that passes through Aurora.

    The lesson captures: prediction context, match outcome, which signals
    were strong, and what Aurora should remember for similar situations.
    """
    result_str = f"{h_goals}–{a_goals}" if is_finished else "upcoming"

    # Determine what the actual outcome was for the best market
    outcome_hit: bool | None = None
    if is_finished and outcomes:
        market_key = best_market.lower().replace(" ", "_").replace(".", "")
        outcome_hit = outcomes.get(market_key)

    # Identify strongest methodology categories
    strong_signals: list[str] = []
    weak_signals:   list[str] = []
    if methodology_categories:
        for key, cat in methodology_categories.items():
            score = cat.get("score", 5.0) if isinstance(cat, dict) else getattr(cat, "score", 5.0)
            name  = cat.get("name", key) if isinstance(cat, dict) else getattr(cat, "name", key)
            if score >= 7.0:
                strong_signals.append(f"{name} ({score:.1f})")
            elif score <= 3.0:
                weak_signals.append(f"{name} ({score:.1f})")

    lesson_text = (
        f"{hn} vs {an} · {result_str} · "
        f"Best market: {best_market} ({market_prob:.0f}%) · "
        f"Methodology score: {methodology_score:.2f} · "
        f"Confidence: {overall_confidence:.1f}/10 · "
        f"Risk: {risk_level}."
    )
    if strong_signals:
        lesson_text += f" Strong signals: {', '.join(strong_signals[:3])}."
    if weak_signals:
        lesson_text += f" Weak signals: {', '.join(weak_signals[:2])}."
    if outcome_hit is not None:
        lesson_text += f" Outcome: {'✅ WIN' if outcome_hit else '❌ LOSS'}."

    content = {
        "fixture_id":           fixture_id,
        "home":                 hn,
        "away":                 an,
        "result":               result_str,
        "best_market":          best_market,
        "market_probability":   market_prob,
        "methodology_score":    methodology_score,
        "overall_confidence":   overall_confidence,
        "risk_level":           risk_level,
        "outcome_hit":          outcome_hit,
        "strong_signals":       strong_signals,
        "weak_signals":         weak_signals,
        "corners":              total_corners,
        "cards":                total_cards,
    }

    importance = 8 if outcome_hit is not None else 6

    remember(
        collection="lessons_learned",
        content=content,
        summary=lesson_text,
        key=f"fixture_{fixture_id}_{best_market.replace(' ', '_')}",
        tags=[hn, an, league or "", best_market, risk_level,
              "win" if outcome_hit else ("loss" if outcome_hit is False else "pending")],
        fixture_id=fixture_id,
        league=league,
        team=hn,
        market=best_market,
        confidence=overall_confidence,
        importance=importance,
    )

    # Also update collection-level patterns
    if outcome_hit is True:
        _upsert_successful_pattern(hn, an, league, best_market, strong_signals)
    elif outcome_hit is False:
        _upsert_failed_pattern(hn, an, league, best_market, weak_signals)


def _upsert_successful_pattern(hn, an, league, market, strong_signals):
    remember(
        collection="successful_patterns",
        content={
            "market": market,
            "league": league,
            "strong_signals": strong_signals,
            "example": f"{hn} vs {an}",
        },
        summary=f"Winning pattern: {market} with signals {', '.join(strong_signals[:2])}.",
        tags=[market, league or "", "win"] + strong_signals[:2],
        league=league,
        market=market,
        importance=7,
    )


def _upsert_failed_pattern(hn, an, league, market, weak_signals):
    remember(
        collection="failed_patterns",
        content={
            "market": market,
            "league": league,
            "weak_signals": weak_signals,
            "example": f"{hn} vs {an}",
        },
        summary=f"Failed pattern: {market} with weak signals {', '.join(weak_signals[:2])}.",
        tags=[market, league or "", "loss"] + weak_signals[:2],
        league=league,
        market=market,
        importance=7,
    )


# ---------------------------------------------------------------------------
# Auto-hooks — called from routers, never raise
# ---------------------------------------------------------------------------


def remember_recommendation(
    fixture_id:         int,
    hn:                 str,
    an:                 str,
    league:             str | None,
    best_market:        str,
    market_prob:        float,
    market_key:         str,
    confidence:         float,
    risk:               str,
    methodology_score:  float,
    methodology_passed: bool,
    recommended_market: str | None,
    summary:            str,
    category_scores:    dict | None = None,
) -> None:
    """
    Store every recommendation Aurora generates in betting_patterns.
    Never raises — swallows all exceptions.
    """
    try:
        content = {
            "fixture_id":          fixture_id,
            "home":                hn,
            "away":                an,
            "league":              league,
            "best_market":         best_market,
            "market_key":          market_key,
            "probability":         market_prob,
            "confidence":          confidence,
            "risk":                risk,
            "methodology_score":   methodology_score,
            "methodology_passed":  methodology_passed,
            "recommended_market":  recommended_market,
            "summary":             summary,
            "top_categories":      {
                k: {"score": v["score"], "name": v["name"]}
                for k, v in (category_scores or {}).items()
                if v.get("score", 0) >= 7.0
            },
            "timestamp": _now(),
        }
        remember(
            collection="betting_patterns",
            content=content,
            summary=summary,
            key=f"fixture_{fixture_id}_{market_key}",
            tags=[hn, an, league or "", best_market, risk],
            fixture_id=fixture_id,
            league=league,
            team=hn,
            market=market_key,
            confidence=confidence,
            importance=6 if methodology_passed else 4,
        )

        # Update market statistics aggregate
        _update_market_stats(market_key, best_market, market_prob, confidence, league)

        # Update team profiles
        _upsert_team_profile(hn, league)
        _upsert_team_profile(an, league)

        # Update league profile
        if league:
            _upsert_league_profile(league)

    except Exception as exc:
        logger.error("Memory: remember_recommendation failed: %s", exc)


def remember_lesson_from_finished(
    fixture_id:         int,
    hn:                 str,
    an:                 str,
    league:             str | None,
    methodology_score:  float,
    overall_confidence: float,
    best_market:        str,
    market_prob:        float,
    risk_level:         str,
    h_goals:            int,
    a_goals:            int,
    total_corners:      int,
    total_cards:        int,
    category_scores:    dict | None = None,
) -> None:
    """Auto-hook: generate and store a lesson for every finished match."""
    try:
        outcomes = {
            "home_win":          h_goals > a_goals,
            "draw":              h_goals == a_goals,
            "away_win":          a_goals > h_goals,
            "btts":              h_goals >= 1 and a_goals >= 1,
            "over_25_goals":     (h_goals + a_goals) >= 3,
            "over_85_corners":   total_corners >= 9,
            "over_45_cards":     total_cards >= 5,
        }
        learn(
            fixture_id=fixture_id,
            hn=hn,
            an=an,
            league=league,
            methodology_score=methodology_score,
            overall_confidence=overall_confidence,
            best_market=best_market,
            market_prob=market_prob,
            risk_level=risk_level,
            is_finished=True,
            h_goals=h_goals,
            a_goals=a_goals,
            total_corners=total_corners,
            total_cards=total_cards,
            methodology_categories=category_scores,
            outcomes=outcomes,
        )

        # Write daily log entry
        _write_daily_log(hn, an, league, best_market, market_prob, "finished")

    except Exception as exc:
        logger.error("Memory: remember_lesson_from_finished failed: %s", exc)


def remember_methodology_change(
    version: str,
    weights: dict,
    thresholds: dict,
    changed_by: str = "system",
    notes: str = "",
) -> None:
    """Store every methodology version in the methodologies collection."""
    try:
        remember(
            collection="methodologies",
            content={
                "version":    version,
                "weights":    weights,
                "thresholds": thresholds,
                "changed_by": changed_by,
                "notes":      notes,
                "timestamp":  _now(),
            },
            summary=f"Methodology v{version} loaded — {len(weights)} category weights.",
            key=f"methodology_v{version}_{_now()[:10]}",
            tags=["methodology", f"v{version}", changed_by],
            importance=9,
        )
    except Exception as exc:
        logger.error("Memory: remember_methodology_change failed: %s", exc)


def remember_bankroll_session(
    total_recommendations: int,
    passed_methodology:    int,
    markets_breakdown:     dict,
    league:                str | None = None,
    notes:                 str = "",
) -> None:
    """Store a bankroll session summary for today."""
    try:
        today = date.today().isoformat()
        remember(
            collection="bankroll_sessions",
            content={
                "date":                  today,
                "total_recommendations": total_recommendations,
                "passed_methodology":    passed_methodology,
                "pass_rate":             round(passed_methodology / max(total_recommendations, 1) * 100, 1),
                "markets_breakdown":     markets_breakdown,
                "league":                league,
                "notes":                 notes,
            },
            summary=(
                f"Session {today}: {total_recommendations} recommendations, "
                f"{passed_methodology} passed methodology ({round(passed_methodology / max(total_recommendations, 1) * 100)}%)."
            ),
            key=f"session_{today}",
            tags=["bankroll", today, league or "all"],
            league=league,
            importance=7,
        )
    except Exception as exc:
        logger.error("Memory: remember_bankroll_session failed: %s", exc)


# ---------------------------------------------------------------------------
# Profile upserts — background aggregation
# ---------------------------------------------------------------------------


def _update_market_stats(
    market_key: str, market_label: str, prob: float, conf: float, league: str | None
) -> None:
    """Increment call count and update running average for a market."""
    try:
        existing = recall("market_statistics", key=market_key, limit=1)
        if existing:
            old = existing[0]["content"]
            count  = old.get("count", 0) + 1
            avg_prob = round((old.get("avg_probability", prob) * (count - 1) + prob) / count, 2)
            avg_conf = round((old.get("avg_confidence", conf) * (count - 1) + conf) / count, 2)
            leagues  = list(set(old.get("leagues", []) + ([league] if league else [])))
        else:
            count, avg_prob, avg_conf, leagues = 1, prob, conf, [league] if league else []

        remember(
            collection="market_statistics",
            content={
                "market_key":      market_key,
                "market_label":    market_label,
                "count":           count,
                "avg_probability": avg_prob,
                "avg_confidence":  avg_conf,
                "leagues":         leagues[:20],
            },
            summary=f"{market_label}: {count} analyses, avg prob {avg_prob:.1f}%, avg conf {avg_conf:.1f}/10.",
            key=market_key,
            market=market_key,
            importance=5,
        )
    except Exception as exc:
        logger.debug("Memory: _update_market_stats: %s", exc)


def _upsert_team_profile(team: str, league: str | None) -> None:
    try:
        existing = recall("team_profiles", key=team, limit=1)
        if existing:
            old     = existing[0]["content"]
            count   = old.get("appearances", 0) + 1
            leagues = list(set(old.get("leagues", []) + ([league] if league else [])))
        else:
            count, leagues = 1, [league] if league else []

        remember(
            collection="team_profiles",
            content={
                "team":        team,
                "appearances": count,
                "leagues":     leagues[:10],
                "last_seen":   _now()[:10],
            },
            summary=f"{team}: {count} Aurora analyses.",
            key=team,
            team=team,
            league=league,
            importance=4,
        )
    except Exception as exc:
        logger.debug("Memory: _upsert_team_profile: %s", exc)


def _upsert_league_profile(league: str) -> None:
    try:
        existing = recall("league_profiles", key=league, limit=1)
        count = (existing[0]["content"].get("analyses", 0) + 1) if existing else 1
        remember(
            collection="league_profiles",
            content={
                "league":    league,
                "analyses":  count,
                "last_seen": _now()[:10],
            },
            summary=f"{league}: {count} Aurora analyses.",
            key=league,
            league=league,
            importance=4,
        )
    except Exception as exc:
        logger.debug("Memory: _upsert_league_profile: %s", exc)


def _write_daily_log(hn, an, league, market, prob, event_type) -> None:
    try:
        today = date.today().isoformat()
        remember(
            collection="daily_logs",
            content={
                "event":   event_type,
                "home":    hn,
                "away":    an,
                "league":  league,
                "market":  market,
                "prob":    prob,
                "date":    today,
            },
            summary=f"[{event_type.upper()}] {hn} vs {an} — {market} ({prob:.0f}%)",
            tags=[today, event_type, league or "", hn, an],
            league=league,
            team=hn,
            market=market,
            importance=3,
        )
    except Exception as exc:
        logger.debug("Memory: _write_daily_log: %s", exc)


# ---------------------------------------------------------------------------
# recall_context — called by decision_engine before generating a recommendation
# ---------------------------------------------------------------------------


def recall_context(
    hn:      str,
    an:      str,
    league:  str | None,
) -> dict:
    """
    Retrieve relevant memory context before generating a recommendation.

    Used by the decision_engine to surface:
      - Past lessons for these teams
      - League profile
      - Team profiles
      - Recent successful/failed patterns for the league

    Returns a compact dict suitable for embedding in the decision pipeline.
    Never raises.
    """
    try:
        past_lessons = recall("lessons_learned", team=hn, league=league, limit=3)
        past_lessons += [r for r in recall("lessons_learned", team=an, limit=3)
                         if r not in past_lessons]

        team_h = recall("team_profiles", key=hn, limit=1)
        team_a = recall("team_profiles", key=an, limit=1)
        league_profile = recall("league_profiles", key=league, limit=1) if league else []

        winning = recall("successful_patterns", league=league, limit=3)
        losing  = recall("failed_patterns",     league=league, limit=3)

        return {
            "past_lessons":     past_lessons[:4],
            "team_home":        team_h[0] if team_h else None,
            "team_away":        team_a[0] if team_a else None,
            "league_profile":   league_profile[0] if league_profile else None,
            "winning_patterns": winning,
            "losing_patterns":  losing,
            "has_context":      bool(past_lessons or team_h or league_profile),
        }
    except Exception as exc:
        logger.error("Memory: recall_context failed: %s", exc)
        return {"has_context": False}
