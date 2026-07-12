"""
/aurora/learning — Aurora Learning Engine REST API.

Endpoints:
  GET  /aurora/learning/stats          → aggregate learning statistics
  GET  /aurora/learning/history        → recent prediction history (paginated)
  POST /aurora/learning/result         → manually record a match result
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.learning_db import (
    DB_PATH,
    MARKET_KEYS,
    get_learning_stats,
    resolve_predictions,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /aurora/learning/stats
# ---------------------------------------------------------------------------

@router.get("/learning/stats", summary="Learning Engine Statistics")
async def learning_stats():
    """
    Return Aurora's accumulated prediction performance statistics.

    Statistics are built automatically as predictions are made via
    `/aurora/score` and results are resolved when matches finish.

    **Fields:**
    - `total_predictions` — all predictions ever saved
    - `wins` / `losses` / `pending` — outcome counts
    - `current_accuracy` — wins ÷ (wins + losses) × 100 (null until first result)
    - `roi_pct` — net profit ÷ total staked × 100 (null until odds/stake recorded)
    - `avg_confidence` — mean confidence score across all predictions
    - `best_market` / `worst_market` — markets by win rate
    - `best_league` / `worst_league` — leagues by win rate
    - `market_breakdown` — per-market wins / losses / accuracy
    - `league_breakdown` — per-league wins / losses / accuracy
    """
    return get_learning_stats()


# ---------------------------------------------------------------------------
# GET /aurora/learning/history
# ---------------------------------------------------------------------------

@router.get("/learning/history", summary="Prediction History")
async def learning_history(
    limit: int = Query(50, ge=1, le=200, description="Max rows to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    market: str | None = Query(None, description="Filter by market key"),
    result: str | None = Query(None, description="Filter by result: win | loss | pending"),
):
    """
    Return recent prediction history records, newest first.

    Use `?result=pending` to see predictions still awaiting a match result.
    Use `?market=home_win` to filter by market.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row

        clauses: list[str] = []
        params: list = []

        if market:
            clauses.append("market = ?")
            params.append(market)
        if result == "pending":
            clauses.append("result IS NULL")
        elif result in ("win", "loss"):
            clauses.append("result = ?")
            params.append(result)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params += [limit, offset]

        rows = conn.execute(
            f"SELECT * FROM prediction_history {where} "
            f"ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total = conn.execute(
            f"SELECT COUNT(*) FROM prediction_history {where}",
            params[:-2],
        ).fetchone()[0]
        conn.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "records": [dict(r) for r in rows],
    }


# ---------------------------------------------------------------------------
# POST /aurora/learning/result  — manual result recording
# ---------------------------------------------------------------------------

class RecordResultRequest(BaseModel):
    fixture_id: int = Field(..., description="Fixture ID to resolve predictions for")
    home_goals: int = Field(..., ge=0, description="Final home goals")
    away_goals: int = Field(..., ge=0, description="Final away goals")
    total_corners: int | None = Field(None, ge=0, description="Total corners (if known)")
    total_cards: int | None = Field(None, ge=0, description="Total cards (if known)")
    total_goals: int | None = Field(
        None, ge=0, description="Override total goals (defaults to home + away)"
    )


@router.post("/learning/result", summary="Record Match Result", status_code=200)
async def record_result(body: RecordResultRequest):
    """
    Manually record a match result and resolve all pending predictions for that fixture.

    Aurora automatically resolves predictions when `/aurora/score` is called
    for a finished match. Use this endpoint if you want to force resolution
    or record a result for a match that was never re-queried after it finished.

    **Outcomes resolved:**
    - `home_win`: home_goals > away_goals
    - `draw`: home_goals == away_goals
    - `away_win`: away_goals > home_goals
    - `btts`: both home_goals ≥ 1 and away_goals ≥ 1
    - `over_25_goals`: total goals ≥ 3
    - `over_85_corners`: total corners ≥ 9 (requires total_corners)
    - `over_45_cards`: total cards ≥ 5 (requires total_cards)
    """
    total = body.total_goals if body.total_goals is not None else (body.home_goals + body.away_goals)

    outcomes: dict[str, bool] = {
        "home_win":        body.home_goals > body.away_goals,
        "draw":            body.home_goals == body.away_goals,
        "away_win":        body.away_goals > body.home_goals,
        "btts":            body.home_goals >= 1 and body.away_goals >= 1,
        "over_25_goals":   total >= 3,
    }
    if body.total_corners is not None:
        outcomes["over_85_corners"] = body.total_corners >= 9
    if body.total_cards is not None:
        outcomes["over_45_cards"] = body.total_cards >= 5

    resolved = resolve_predictions(body.fixture_id, outcomes)
    return {
        "fixture_id": body.fixture_id,
        "outcomes":   outcomes,
        "resolved":   len(resolved),
        "records":    resolved,
    }
