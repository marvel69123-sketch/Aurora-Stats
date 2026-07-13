"""
/aurora/evolution — Aurora Auto Evolution Engine REST API.

Endpoints:
  GET  /aurora/evolution/report          → analyze a finished match and return improvement report
  GET  /aurora/evolution/history         → paginated history of all improvement reports
  GET  /aurora/evolution/calibration     → calibration statistics across all reports
  POST /aurora/evolution/simulate        → simulate proposed weight changes (never applies them)

All analysis is READ + SUGGEST only.
Aurora NEVER modifies brain files or methodology automatically.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.brain import get_brain_meta, get_config, get_methodology_config
from src.core import confidence_engine, learning_engine, market_engine, methodology_engine
from src.core.evolution_engine import (
    CalibrationStats,
    CategoryVerdict,
    EvolutionAnalysis,
    ImprovementReport,
    MarketAccuracy,
    SimulationMatch,
    SimulationReport,
    analyze,
    calibrate_from_history,
    generate_report,
    simulate_weights,
)
from src.core.methodology_v1 import run as _mv1_run
from src.memory_db import get_history, recall, remember
from src.routers.analyze import analyze_fixture

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class MarketAccuracyRow(BaseModel):
    market_key:     str
    market_name:    str
    predicted_prob: float
    outcome:        bool
    brier:          float
    log_loss:       float
    correct:        bool


class CategoryVerdictRow(BaseModel):
    key:         str
    name:        str
    score:       float
    weight:      float
    verdict:     str
    explanation: str


class ImprovementReportResponse(BaseModel):
    report_id:    str
    generated_at: str
    headline:     str
    summary:      str

    # Match identity
    fixture_id:    int
    match:         str
    league:        str | None
    result:        str
    data_richness: str
    methodology_score: float

    # Prediction accuracy
    best_market:          str
    best_market_correct:  bool
    markets_correct:      list[str]
    markets_wrong:        list[str]
    market_accuracies:    list[MarketAccuracyRow]
    brier_score:          float
    log_loss:             float
    calibration_error:    float

    # Category analysis
    correct_categories: list[CategoryVerdictRow]
    failed_categories:  list[CategoryVerdictRow]
    all_category_verdicts: list[CategoryVerdictRow]

    # Improvement intelligence
    correct_assumptions:      list[str]
    wrong_assumptions:        list[str]
    possible_biases:          list[str]
    missing_data:             list[str]
    suggested_weight_changes: dict[str, float]
    suggested_new_rules:      list[str]

    brain: dict[str, Any]


class SimulateRequest(BaseModel):
    new_weights: dict[str, float] = Field(
        ...,
        description=(
            "Proposed weight changes. Can be partial — only supply the categories you want "
            "to test. Missing categories keep their current weight. "
            "Example: {'xg_analysis': 0.15, 'corners_pattern': 0.08}"
        ),
    )
    test_on_last_n: int = Field(
        default=20,
        ge=1,
        le=200,
        description="Number of most recent improvement_history records to test against.",
    )


class SimulationMatchRow(BaseModel):
    fixture_id:          int
    match:               str
    old_score:           float
    new_score:           float
    old_passes:          bool
    new_passes:          bool
    best_market_correct: bool
    delta_score:         float


class SimulationReportResponse(BaseModel):
    proposed_weights:    dict[str, float]
    weight_deltas:       dict[str, float]
    test_on_n:           int
    old_pass_rate:       float
    new_pass_rate:       float
    old_correct_rate:    float
    new_correct_rate:    float
    delta_pass_rate:     float
    delta_correct_rate:  float
    verdict:             str
    recommendation:      str
    matches:             list[SimulationMatchRow]
    brain:               dict[str, Any]


class CalibrationResponse(BaseModel):
    total_records:        int
    mean_brier:           float
    mean_log_loss:        float
    mean_calibration_error: float
    calibration_grade:    str
    best_market_accuracy: float
    over_confident:       bool
    markets_correct_rate: dict[str, float]
    interpretation:       str
    brain:                dict[str, Any]


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _to_market_row(ma: MarketAccuracy) -> MarketAccuracyRow:
    return MarketAccuracyRow(
        market_key=ma.market_key, market_name=ma.market_name,
        predicted_prob=ma.predicted_prob, outcome=ma.outcome,
        brier=ma.brier, log_loss=ma.log_loss, correct=ma.correct,
    )


def _to_cat_row(cv: CategoryVerdict) -> CategoryVerdictRow:
    return CategoryVerdictRow(
        key=cv.key, name=cv.name, score=cv.score,
        weight=cv.weight, verdict=cv.verdict, explanation=cv.explanation,
    )


def _to_report_response(rpt: ImprovementReport) -> ImprovementReportResponse:
    a = rpt.analysis
    return ImprovementReportResponse(
        report_id=rpt.report_id,
        generated_at=rpt.generated_at,
        headline=rpt.headline,
        summary=rpt.summary,
        fixture_id=a.fixture_id,
        match=a.match,
        league=a.league,
        result=a.result_str,
        data_richness=a.data_richness,
        methodology_score=a.methodology_score,
        best_market=a.best_market_key,
        best_market_correct=a.best_market_correct,
        markets_correct=a.markets_correct,
        markets_wrong=a.markets_wrong,
        market_accuracies=[_to_market_row(m) for m in a.market_accuracies],
        brier_score=a.brier_score,
        log_loss=a.log_loss,
        calibration_error=a.calibration_error,
        correct_categories=[_to_cat_row(c) for c in a.correct_categories],
        failed_categories=[_to_cat_row(c) for c in a.failed_categories],
        all_category_verdicts=[_to_cat_row(c) for c in a.category_verdicts],
        correct_assumptions=a.correct_assumptions,
        wrong_assumptions=a.wrong_assumptions,
        possible_biases=a.possible_biases,
        missing_data=a.missing_data,
        suggested_weight_changes=a.suggested_weight_changes,
        suggested_new_rules=a.suggested_new_rules,
        brain=get_brain_meta(),
    )


def _persist_report(rpt: ImprovementReport) -> None:
    """Save the improvement report to improvement_history. Never raises."""
    try:
        a = rpt.analysis
        remember(
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
            key=f"evo_{a.fixture_id}",   # one report per fixture, immutable key
            tags=[a.match, a.league or "", a.best_market_key,
                  "correct" if a.best_market_correct else "wrong",
                  f"brier_{a.brier_score:.3f}"],
            fixture_id=a.fixture_id,
            league=a.league,
            confidence=a.methodology_score,
            importance=8,
        )
    except Exception as exc:
        logger.error("Evolution: failed to persist report: %s", exc)


async def _run_evolution(home: str, away: str) -> tuple[ImprovementReportResponse, ImprovementReport]:
    """Shared pipeline for the report endpoint."""
    data = await analyze_fixture(home=home, away=away)
    fx   = data["fixture"]

    if fx["status"]["short"] not in {"FT", "AET", "PEN", "AWD", "WO"}:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Match {home} vs {away} is not finished "
                f"(status: {fx['status']['long']}). "
                "Evolution analysis requires a completed match with a known result."
            ),
        )

    cfg  = get_config()
    mcfg = get_methodology_config()
    hn   = data["teams"]["home"]["name"]
    an   = data["teams"]["away"]["name"]
    lg   = (data.get("league") or {}).get("name")

    meth     = methodology_engine.run(data, cfg)
    learning = learning_engine.run(league=lg)
    conf     = confidence_engine.run(meth, cfg)
    mkts     = market_engine.run(hn, an, data, meth, conf, cfg)
    mv1      = _mv1_run(
        data=data, hn=hn, an=an,
        meth=meth, conf=conf, market=mkts,
        learning=learning, mcfg=mcfg, brain_cfg=cfg,
    )

    evolution = analyze(
        data=data, hn=hn, an=an,
        markets=mkts, mv1=mv1, meth=meth,
        league=lg, cfg=cfg, mcfg=mcfg,
    )
    rpt = generate_report(evolution)
    return _to_report_response(rpt), rpt


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/evolution/report", response_model=ImprovementReportResponse, summary="Post-Match Evolution Report")
async def evolution_report(
    home: str = Query(..., description="Home team name"),
    away: str = Query(..., description="Away team name"),
) -> ImprovementReportResponse:
    """
    Generate an Aurora Auto Evolution report for a **finished** match.

    Runs the full post-match self-improvement analysis:

    1. **Compare** prediction vs real result for all 7 markets
    2. **Detect** which methodology categories gave correct/wrong signals
    3. **Calculate** prediction error (Brier score, log-loss, calibration)
    4. **Identify** correct assumptions, wrong assumptions, possible biases, missing data
    5. **Suggest** methodology weight changes and new rules (never applied automatically)

    The report is permanently stored in `improvement_history` memory
    and never overwritten (key = `evo_{fixture_id}`).

    Returns HTTP 422 if the match has not finished yet.
    """
    response, rpt = await _run_evolution(home=home, away=away)
    _persist_report(rpt)
    return response


@router.get("/evolution/history", summary="Evolution Report History")
async def evolution_history(
    limit:  int = Query(50, ge=1, le=200),
    offset: int = Query(0,  ge=0),
    league: str | None = Query(None, description="Filter by league"),
) -> dict:
    """
    Return paginated history of all Aurora evolution reports.

    Each record contains:
    - Brier score, log-loss, calibration error for that fixture
    - Which markets were correct/wrong
    - Suggested weight changes
    - Category verdicts (correct_bullish, missed_bullish, etc.)

    Records are ordered newest first and never overwritten.
    Use `GET /aurora/evolution/calibration` for aggregate accuracy stats.
    """
    result = get_history(collection="improvement_history", limit=limit, offset=offset)
    # Enrich with league filter if provided
    if league:
        result["records"] = [
            r for r in result["records"]
            if (r.get("content") or {}).get("league") == league
        ]
        result["total"] = len(result["records"])
    result["brain"] = get_brain_meta()
    return result


@router.get("/evolution/calibration", response_model=CalibrationResponse, summary="Calibration Statistics")
async def evolution_calibration() -> CalibrationResponse:
    """
    Aggregate calibration statistics computed across all evolution reports.

    **Calibration grade (based on mean |predicted% − actual hit%|):**
    - A: ≤5%   — Excellent — Aurora's confidence accurately reflects real accuracy
    - B: ≤10%  — Good      — Minor over/under confidence
    - C: ≤20%  — Fair      — Notable miscalibration, review category weights
    - D: >20%  — Poor      — Systematic overconfidence, weight review required

    Requires at least 2 historical reports for meaningful statistics.
    """
    records = get_history(collection="improvement_history", limit=200)["records"]

    cal = calibrate_from_history(records)

    interpretation = (
        f"Aurora has generated {cal.total_records} improvement report(s). "
    )
    if cal.total_records < 5:
        interpretation += (
            f"Calibration grade {cal.calibration_grade} — insufficient data for reliable statistics "
            f"(need ≥5 records). Current mean Brier score: {cal.mean_brier:.4f}."
        )
    else:
        interpretation += (
            f"Calibration grade {cal.calibration_grade} (mean error {cal.mean_cal_error:.1f}%). "
            f"Best-market accuracy: {cal.best_market_accuracy:.1f}%. "
            f"Mean Brier: {cal.mean_brier:.4f} "
            f"({'Excellent' if cal.mean_brier < 0.05 else 'Good' if cal.mean_brier < 0.15 else 'Needs improvement'}). "
        )
        if cal.over_confident:
            interpretation += (
                "ALERT: Aurora is OVER-CONFIDENT — predicted probabilities are systematically "
                "higher than actual outcomes. Review high-scoring categories in brain/methodology.json."
            )
        else:
            interpretation += "Calibration is within acceptable bounds."

    return CalibrationResponse(
        total_records=cal.total_records,
        mean_brier=cal.mean_brier,
        mean_log_loss=cal.mean_log_loss,
        mean_calibration_error=cal.mean_cal_error,
        calibration_grade=cal.calibration_grade,
        best_market_accuracy=cal.best_market_accuracy,
        over_confident=cal.over_confident,
        markets_correct_rate=cal.markets_correct_rate,
        interpretation=interpretation,
        brain=get_brain_meta(),
    )


@router.post("/evolution/simulate", response_model=SimulationReportResponse, summary="Simulate Weight Changes")
async def evolution_simulate(body: SimulateRequest) -> SimulationReportResponse:
    """
    Simulate the impact of proposed methodology weight changes on historical data.

    **This endpoint NEVER applies changes** — it only reports what would have happened.
    To apply approved changes, edit `brain/methodology.json` manually and call
    `POST /aurora/brain/reload`.

    **How it works:**
    1. Reads the last N improvement reports from `improvement_history`
    2. For each historical match, re-computes the methodology score using proposed weights
    3. Checks if the recommendation decision (pass/fail gate) would have changed
    4. Compares accuracy before and after for matches that passed the gate

    **Input:** Partial weights — only supply the categories you want to change.
    Missing categories automatically retain their current weight from brain/methodology.json.
    Weights are re-normalised to sum=1.0 if needed.

    **Verdict:** Improved | Worse | Neutral (requires ≥2 records with known outcomes).
    """
    mcfg = get_methodology_config()
    records = recall(
        "improvement_history",
        limit=body.test_on_last_n,
        importance_gte=0,
    )

    sim = simulate_weights(
        new_weights=body.new_weights,
        history_records=records,
        mcfg=mcfg,
    )

    return SimulationReportResponse(
        proposed_weights=sim.proposed_weights,
        weight_deltas=sim.weight_deltas,
        test_on_n=sim.test_on_n,
        old_pass_rate=sim.old_pass_rate,
        new_pass_rate=sim.new_pass_rate,
        old_correct_rate=sim.old_correct_rate,
        new_correct_rate=sim.new_correct_rate,
        delta_pass_rate=sim.delta_pass_rate,
        delta_correct_rate=sim.delta_correct_rate,
        verdict=sim.verdict,
        recommendation=sim.recommendation,
        matches=[
            SimulationMatchRow(
                fixture_id=m.fixture_id,
                match=m.match,
                old_score=m.old_score,
                new_score=m.new_score,
                old_passes=m.old_passes,
                new_passes=m.new_passes,
                best_market_correct=m.best_market_correct,
                delta_score=m.delta_score,
            )
            for m in sim.matches
        ],
        brain=get_brain_meta(),
    )
