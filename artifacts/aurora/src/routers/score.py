"""
/aurora/score — Betting-grade probability scores for a fixture.

All business logic has moved to src/core/. This router:
  1. Receives the HTTP request
  2. Fetches raw fixture data via analyze_fixture()
  3. Delegates to decision_engine.run()  ← central brain
  4. Maps the DecisionResult to the ScoreResponse schema
  5. Fires the learning hook (side-effect, never raises)
  6. Returns the response

No math, no thresholds, no model logic lives here.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.core.decision_engine import DecisionResult, run as _decide
from src.learning_db import resolve_predictions as _lrn_resolve
from src.learning_db import save_prediction as _lrn_save
from src.routers.analyze import analyze_fixture

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Response schema  (unchanged — API contract stays stable)
# ---------------------------------------------------------------------------


class MarketScore(BaseModel):
    probability: float
    confidence:  float
    risk:        str
    actionable:  bool
    explanation: str


class ScoreResponse(BaseModel):
    match:    str
    fixture_id: int
    date:     str
    status:   str
    minute:   int | None

    overall_confidence:  float
    risk_level:          str
    best_market:         str
    recommended_markets: list[str]
    summary:             str

    home_win:         MarketScore
    draw:             MarketScore
    away_win:         MarketScore
    btts:             MarketScore
    over_25_goals:    MarketScore
    over_85_corners:  MarketScore
    over_45_cards:    MarketScore

    brain: dict[str, Any]


# ---------------------------------------------------------------------------
# DecisionResult → ScoreResponse mapper
# ---------------------------------------------------------------------------


def _ms(key: str, decision: DecisionResult) -> MarketScore:
    """Pull a market from the decision and convert to the Pydantic schema."""
    ms = decision.markets.markets[key]
    return MarketScore(
        probability=ms.probability,
        confidence=ms.confidence,
        risk=ms.risk,
        actionable=ms.actionable,
        explanation=ms.explanation,
    )


def _to_score_response(decision: DecisionResult) -> ScoreResponse:
    return ScoreResponse(
        match=f"{decision.hn} vs {decision.an}",
        fixture_id=decision.fixture_id,
        date=decision.date or "",
        status=decision.status,
        minute=decision.minute,
        overall_confidence=decision.overall_confidence,
        risk_level=decision.risk_level,
        best_market=decision.best_market_label,
        recommended_markets=decision.recommended_market_labels,
        summary=decision.summary,
        home_win=_ms("home_win", decision),
        draw=_ms("draw", decision),
        away_win=_ms("away_win", decision),
        btts=_ms("btts", decision),
        over_25_goals=_ms("over_25_goals", decision),
        over_85_corners=_ms("over_85_corners", decision),
        over_45_cards=_ms("over_45_cards", decision),
        brain=decision.brain_meta,
    )


# ---------------------------------------------------------------------------
# Learning hook — fires after every prediction, never raises
# ---------------------------------------------------------------------------


def _learning_hook(decision: DecisionResult, data: dict) -> None:
    """
    Save the best-market prediction to the learning engine.
    Auto-resolve if the match is finished.
    Any exception is swallowed — never affects the response.
    """
    try:
        m  = decision.methodology
        bm = decision.markets.best

        _lrn_save(
            fixture_id=decision.fixture_id,
            date=decision.date,
            home_team=decision.hn,
            away_team=decision.an,
            league=decision.league,
            market=bm.key,
            prediction=bm.label,
            confidence=bm.confidence,
            risk=bm.risk,
            reason=decision.summary,
        )

        if m.is_finished and m.has_score:
            _lrn_resolve(decision.fixture_id, {
                "home_win":        m.h_goals > m.a_goals,
                "draw":            m.h_goals == m.a_goals,
                "away_win":        m.a_goals > m.h_goals,
                "btts":            m.h_goals >= 1 and m.a_goals >= 1,
                "over_25_goals":   m.total_goals >= 3,
                "over_85_corners": m.total_corners >= 9,
                "over_45_cards":   m.total_cards >= 5,
            })

    except Exception as exc:
        logger.error("Learning hook error: %s", exc)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/score", response_model=ScoreResponse, summary="Match Score Prediction")
async def score_fixture(
    home: str = Query(..., description="Home team name (full or partial)"),
    away: str = Query(..., description="Away team name (full or partial)"),
) -> ScoreResponse:
    """
    Compute betting-grade probability scores for a fixture.

    **AURORA_BRAIN** operational parameters are loaded before every prediction —
    thresholds, weights, and baselines are never hardcoded.

    **Decision pipeline (src/core/decision_engine.py):**
    1. Collect data (analyze_fixture)
    2. Load Aurora Brain knowledge
    3. Methodology Engine — three-layer Poisson model
    4. Learning Engine   — historical accuracy context
    5. Confidence Engine — data-richness scoring
    6. Bankroll Engine   — risk classification + stake sizing
    7. Market Engine     — rank all seven markets
    8. Report Engine     — explanations + summary
    9. Return recommendation

    **Automatic learning:**
    Every call saves the best-market prediction to the learning engine.
    Finished matches are auto-resolved and update learning statistics
    visible at `GET /aurora/learning/stats`.
    """
    data     = await analyze_fixture(home=home, away=away)
    decision = _decide(data)
    result   = _to_score_response(decision)
    _learning_hook(decision, data)
    return result
