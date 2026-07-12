"""
/aurora/score — Betting-grade probability scores for a fixture.

All business logic lives in src/core/. This router:
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
from src.core import confidence_engine, learning_engine, market_engine, methodology_engine
from src.core.evolution_engine import analyze as _evo_analyze, generate_report as _evo_report
from src.core.knowledge_engine import consult as _knowledge_consult
from src.core.methodology_v1 import run as _mv1_run
from src.brain import get_config as _get_cfg, get_methodology_config as _get_mcfg
from src.learning_db import resolve_predictions as _lrn_resolve
from src.learning_db import save_prediction as _lrn_save
from src.memory_db import (
    recall_context as _mem_context,
    remember_lesson_from_finished as _mem_lesson,
    remember_recommendation as _mem_rec,
    remember as _mem_remember,
)
from src.routers.analyze import analyze_fixture

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Response schema  (API contract — never change field names)
# ---------------------------------------------------------------------------


class MarketScore(BaseModel):
    probability: float
    confidence:  float
    risk:        str
    actionable:  bool
    explanation: str


class CategoryResult(BaseModel):
    name:         str
    score:        float
    weight:       float
    contribution: float
    reason:       str


class MethodologyV1Response(BaseModel):
    """Aurora Methodology v1 — 15-category weighted assessment."""
    overall_score:      float
    confidence:         float
    risk:               str
    recommended_market: str | None
    blocked_markets:    list[str]
    reasons:            list[str]
    passed:             bool
    categories:         dict[str, CategoryResult]


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

    methodology:      MethodologyV1Response
    knowledge_notes:  list[str]
    brain:            dict[str, Any]


# ---------------------------------------------------------------------------
# DecisionResult → ScoreResponse mapper
# ---------------------------------------------------------------------------


def _ms(key: str, decision: DecisionResult) -> MarketScore:
    ms = decision.markets.markets[key]
    return MarketScore(
        probability=ms.probability,
        confidence=ms.confidence,
        risk=ms.risk,
        actionable=ms.actionable,
        explanation=ms.explanation,
    )


def _methodology_response(decision: DecisionResult) -> MethodologyV1Response:
    mv1 = decision.methodology_v1
    return MethodologyV1Response(
        overall_score=mv1.overall_score,
        confidence=mv1.confidence,
        risk=mv1.risk,
        recommended_market=mv1.recommended_market,
        blocked_markets=mv1.blocked_markets,
        reasons=mv1.reasons,
        passed=mv1.passed,
        categories={
            key: CategoryResult(
                name=cs.name,
                score=cs.score,
                weight=cs.weight,
                contribution=cs.contribution,
                reason=cs.reason,
            )
            for key, cs in mv1.categories.items()
        },
    )


def _to_score_response(decision: DecisionResult, knowledge_notes: list[str] | None = None) -> ScoreResponse:
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
        methodology=_methodology_response(decision),
        knowledge_notes=knowledge_notes or [],
        brain=decision.brain_meta,
    )


# ---------------------------------------------------------------------------
# Memory hook — consult memory before, write memory after every prediction
# ---------------------------------------------------------------------------


def _memory_hook(decision: DecisionResult) -> None:
    """
    Write every prediction into Aurora's permanent memory.
    For finished matches, generate and store a lesson.
    Never raises — swallows all exceptions.
    """
    try:
        bm   = decision.markets.best
        mv1  = decision.methodology_v1
        meth = decision.methodology

        cat_scores = {
            key: {"name": cs.name, "score": cs.score}
            for key, cs in mv1.categories.items()
        }

        _mem_rec(
            fixture_id=decision.fixture_id,
            hn=decision.hn,
            an=decision.an,
            league=decision.league,
            best_market=bm.label,
            market_prob=bm.probability,
            market_key=bm.key,
            confidence=bm.confidence,
            risk=bm.risk,
            methodology_score=mv1.overall_score,
            methodology_passed=mv1.passed,
            recommended_market=mv1.recommended_market,
            summary=decision.summary,
            category_scores=cat_scores,
        )

        if meth.is_finished and meth.has_score:
            _mem_lesson(
                fixture_id=decision.fixture_id,
                hn=decision.hn,
                an=decision.an,
                league=decision.league,
                methodology_score=mv1.overall_score,
                overall_confidence=decision.overall_confidence,
                best_market=bm.label,
                market_prob=bm.probability,
                risk_level=decision.risk_level,
                h_goals=meth.h_goals,
                a_goals=meth.a_goals,
                total_corners=meth.total_corners,
                total_cards=meth.total_cards,
                category_scores=cat_scores,
            )
    except Exception as exc:
        logger.error("Memory hook error: %s", exc)


# ---------------------------------------------------------------------------
# Learning hook — fires after every prediction, never raises
# ---------------------------------------------------------------------------


def _learning_hook(decision: DecisionResult) -> None:
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
# Evolution hook — fires after every FINISHED match, never raises
# ---------------------------------------------------------------------------


def _evolution_hook(decision: DecisionResult, data: dict) -> None:
    """
    Auto-run the Evolution Engine after every finished match.
    Persists the improvement report to improvement_history memory.
    Never modifies methodology — read + suggest only.
    """
    try:
        m = decision.methodology
        if not (m.is_finished and m.has_score):
            return

        cfg  = _get_cfg()
        mcfg = _get_mcfg()
        hn   = decision.hn
        an   = decision.an
        lg   = decision.league

        meth     = methodology_engine.run(data, cfg)
        learning = learning_engine.run(league=lg)
        conf     = confidence_engine.run(meth, cfg)
        mkts     = market_engine.run(hn, an, data, meth, conf, cfg)
        mv1      = _mv1_run(
            data=data, hn=hn, an=an,
            meth=meth, conf=conf, market=mkts,
            learning=learning, mcfg=mcfg, brain_cfg=cfg,
        )

        evolution = _evo_analyze(
            data=data, hn=hn, an=an,
            markets=mkts, mv1=mv1, meth=meth,
            league=lg, cfg=cfg, mcfg=mcfg,
        )
        rpt = _evo_report(evolution)
        a   = rpt.analysis

        _mem_remember(
            collection="improvement_history",
            content={
                "report_id":              rpt.report_id,
                "fixture_id":             a.fixture_id,
                "match":                  a.match,
                "league":                 a.league,
                "result":                 a.result_str,
                "methodology_score":      a.methodology_score,
                "data_richness":          a.data_richness,
                "brier_score":            a.brier_score,
                "log_loss":               a.log_loss,
                "calibration_error":      a.calibration_error,
                "best_market":            a.best_market_key,
                "best_market_correct":    a.best_market_correct,
                "markets_correct":        a.markets_correct,
                "markets_wrong":          a.markets_wrong,
                "category_scores":        a.category_scores,
                "actual_outcomes":        {k: bool(v) for k, v in a.actual_outcomes.items()},
                "correct_assumptions":    a.correct_assumptions,
                "wrong_assumptions":      a.wrong_assumptions,
                "possible_biases":        a.possible_biases,
                "missing_data":           a.missing_data,
                "suggested_weight_changes": a.suggested_weight_changes,
                "suggested_new_rules":    a.suggested_new_rules,
                "category_verdicts":      {
                    cv.key: {"verdict": cv.verdict, "score": cv.score}
                    for cv in a.category_verdicts
                },
                "generated_at":           rpt.generated_at,
                "headline":               rpt.headline,
            },
            summary=rpt.headline,
            key=f"evo_{a.fixture_id}",
            tags=[a.match, a.league or "", a.best_market_key,
                  "correct" if a.best_market_correct else "wrong",
                  f"brier_{a.brier_score:.3f}"],
            fixture_id=a.fixture_id,
            league=a.league,
            confidence=a.methodology_score,
            importance=8,
        )
        logger.info(
            "Evolution hook: %s [%s] brier=%.4f best_market_correct=%s",
            a.match, a.result_str, a.brier_score, a.best_market_correct,
        )
    except Exception as exc:
        logger.error("Evolution hook error: %s", exc)


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

    **AURORA_BRAIN** operational parameters and **Methodology v1** weights are
    loaded before every prediction — nothing is hardcoded.

    **Decision pipeline:**
    1. Collect data (analyze_fixture)
    2. Load Aurora Brain knowledge (version.json + methodology.json)
    3. Methodology Engine — three-layer Poisson model
    4. Learning Engine   — historical accuracy context
    5. Confidence Engine — data-richness scoring
    6. Market Engine     — rank all seven markets
    7. **Methodology v1** — 15-category weighted gate (blocks low-quality bets)
    8. Bankroll Engine   — stake sizing
    9. Report Engine     — explanations + summary

    The `methodology` field in the response shows all 15 category scores,
    the overall weighted score, and which markets passed or were blocked.

    **Automatic learning:**
    Every call saves the best-market prediction to the learning engine.
    Finished matches are auto-resolved and update accuracy statistics
    visible at `GET /aurora/learning/stats`.
    """
    data   = await analyze_fixture(home=home, away=away)
    league = data.get("league", {}).get("name")

    _mem_context(hn=home, an=away, league=league)
    decision = _decide(data)
    knowledge = _knowledge_consult(
        hn=home, an=away, league=league,
        is_live=decision.methodology.is_live,
        has_xg=decision.methodology.has_xg,
        has_referee=bool(data.get("fixture", {}).get("referee")),
    )

    result   = _to_score_response(decision, knowledge_notes=knowledge.knowledge_notes)
    _learning_hook(decision)
    _memory_hook(decision)
    _evolution_hook(decision, data)
    return result
