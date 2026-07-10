"""
/aurora/decision   — Full multi-market decision table (all 23 markets evaluated).
/aurora/opportunities — Top 5 ranked opportunities with natural language recommendation.

Both endpoints run the complete Aurora Decision Center pipeline:

  1. Consult memory context (teams + league history)
  2. Collect data (analyze_fixture)
  3. Load Aurora Brain (BrainConfig + MethodologyConfig)
  4. Run methodology engine (Poisson math)
  5. Run confidence engine (data richness)
  6. Run methodology v1 (15-category gate)
  7. Run learning engine (historical accuracy)
  8. Run decision center (23-market evaluation, 8 dimensions each)
  9. Reject markets below minimum confidence automatically
  10. Return ranked table, best→worst

No business logic lives in this file — only HTTP serialization.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.brain import get_brain_meta, get_config, get_methodology_config
from src.core import confidence_engine, learning_engine, market_engine, methodology_engine, methodology_v1
from src.core.decision_center import DecisionCenterResult, MarketEvaluation, run as _dc_run
from src.core.knowledge_engine import KnowledgeContext, consult as _knowledge_consult
from src.memory_db import recall_context as _mem_ctx, remember as _mem_save
from src.routers.analyze import analyze_fixture

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class MarketRow(BaseModel):
    rank:                 int
    market_id:            str
    market_name:          str
    market_type:          str
    probability:          float
    confidence:           float
    live_confidence:      float
    expected_value:       float
    methodology_score:    float
    historical_accuracy:  float | None
    bankroll_suitability: str
    risk:                 str
    composite_score:      float
    explanation:          str
    actionable:           bool
    rejected_reason:      str | None


class DecisionResponse(BaseModel):
    match:            str
    fixture_id:       int
    date:             str
    status:           str
    minute:           int | None
    total_evaluated:  int
    total_actionable: int
    total_rejected:   int
    best_opportunity: MarketRow | None
    top_5:            list[MarketRow]
    all_markets:      list[MarketRow]
    rejected_markets: list[MarketRow]
    knowledge_notes:  list[str]
    brain:            dict[str, Any]


class OpportunitiesResponse(BaseModel):
    match:          str
    fixture_id:     int
    status:         str
    minute:         int | None
    total_markets_evaluated: int
    total_actionable: int
    top_5:          list[MarketRow]
    ranked_table:   str
    recommendation: str
    knowledge_notes: list[str]
    brain:           dict[str, Any]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_row(me: MarketEvaluation) -> MarketRow:
    return MarketRow(
        rank=me.rank,
        market_id=me.market_id,
        market_name=me.market_name,
        market_type=me.market_type,
        probability=me.probability,
        confidence=me.confidence,
        live_confidence=me.live_confidence,
        expected_value=me.expected_value,
        methodology_score=me.methodology_score,
        historical_accuracy=me.historical_accuracy,
        bankroll_suitability=me.bankroll_suitability,
        risk=me.risk,
        composite_score=me.composite_score,
        explanation=me.explanation,
        actionable=me.actionable,
        rejected_reason=me.rejected_reason,
    )


def _build_ranked_table(top_5: list[MarketEvaluation], hn: str, an: str) -> str:
    """Build a plain-text ASCII ranked opportunity table."""
    if not top_5:
        return "No actionable opportunities found."

    lines = [
        f"┌{'─'*78}┐",
        f"│{'AURORA DECISION CENTER — RANKED OPPORTUNITIES':^78}│",
        f"│{f'{hn} vs {an}':^78}│",
        f"├{'─'*4}┬{'─'*28}┬{'─'*8}┬{'─'*8}┬{'─'*8}┬{'─'*8}┬{'─'*8}┤",
        f"│{'Rank':^4}│{'Market':^28}│{'Prob%':^8}│{'EV%':^8}│{'Conf':^8}│{'MScore':^8}│{'Risk':^8}│",
        f"├{'─'*4}┼{'─'*28}┼{'─'*8}┼{'─'*8}┼{'─'*8}┼{'─'*8}┼{'─'*8}┤",
    ]
    for me in top_5:
        ev_str  = f"+{me.expected_value:.1f}" if me.expected_value >= 0 else f"{me.expected_value:.1f}"
        name    = me.market_name[:26] if len(me.market_name) > 26 else me.market_name
        rank_str = f"#{me.rank}" if me.rank > 0 else "—"
        lines.append(
            f"│{rank_str:^4}│{name:<28}│{me.probability:>7.1f}%│{ev_str:>7}%│"
            f"{me.confidence:>7.1f} │{me.methodology_score:>7.1f} │{me.risk:^8}│"
        )
    lines.append(f"└{'─'*4}┴{'─'*28}┴{'─'*8}┴{'─'*8}┴{'─'*8}┴{'─'*8}┴{'─'*8}┘")
    return "\n".join(lines)


def _build_recommendation(dc: DecisionCenterResult) -> str:
    """Natural language recommendation from the decision center result."""
    if not dc.best:
        return (
            f"No markets meet Aurora's minimum confidence threshold for "
            f"{dc.hn} vs {dc.an}. "
            f"{dc.total_evaluated} markets were evaluated — "
            f"all {dc.total_rejected} were rejected due to insufficient data or high risk. "
            "Monitor the match as it approaches kick-off for improved signals."
        )

    best = dc.best
    ev_str = f"+{best.expected_value:.1f}%" if best.expected_value >= 0 else f"{best.expected_value:.1f}%"
    hist_str = (
        f"Historical accuracy {best.historical_accuracy:.0f}%."
        if best.historical_accuracy is not None
        else "No prior history for this market."
    )

    lines = [
        f"🏆 TOP OPPORTUNITY: {best.market_name}",
        f"   Probability: {best.probability:.1f}% · EV: {ev_str} · "
        f"Confidence: {best.confidence:.1f}/10 · Risk: {best.risk}",
        f"   Methodology Score: {best.methodology_score:.1f}/10 · {hist_str}",
        f"   {best.explanation}",
    ]

    if len(dc.top_5) > 1:
        lines.append("")
        lines.append(f"📋 FULL TOP-5 SHORTLIST:")
        for me in dc.top_5:
            ev_s = f"+{me.expected_value:.1f}%" if me.expected_value >= 0 else f"{me.expected_value:.1f}%"
            lines.append(
                f"   #{me.rank or '—'}  {me.market_name:<30}  "
                f"prob={me.probability:.1f}%  EV={ev_s}  risk={me.risk}"
            )

    lines.append("")
    lines.append(
        f"📊 {dc.total_evaluated} markets evaluated — "
        f"{dc.total_actionable} passed all gates, "
        f"{dc.total_rejected} rejected."
    )

    return "\n".join(lines)


def _memory_hook(dc: DecisionCenterResult, match: str, date: str, league: str | None) -> None:
    """Persist decision center session to memory. Never raises."""
    try:
        _mem_save(
            collection="betting_patterns",
            content={
                "source":        "decision_center",
                "match":         match,
                "date":          date,
                "league":        league,
                "total_markets": dc.total_evaluated,
                "actionable":    dc.total_actionable,
                "top_5":         [
                    {
                        "market_id":    me.market_id,
                        "market_name":  me.market_name,
                        "probability":  me.probability,
                        "ev":           me.expected_value,
                        "composite":    me.composite_score,
                        "risk":         me.risk,
                    }
                    for me in dc.top_5
                ],
                "best_market":   dc.best.market_name if dc.best else None,
            },
            summary=(
                f"Decision Center: {match} — best {dc.best.market_name} "
                f"({dc.best.probability:.0f}%)" if dc.best else f"Decision Center: {match} — no opportunities"
            ),
            key=f"dc_{dc.fixture_id}",
            tags=[dc.hn, dc.an, league or "", "decision_center"],
            fixture_id=dc.fixture_id,
            league=league,
            team=dc.hn,
            importance=6,
        )
    except Exception as exc:
        logger.error("Decision center memory hook: %s", exc)


async def _run_pipeline(home: str, away: str) -> tuple[dict, DecisionCenterResult, str | None, KnowledgeContext]:
    """Shared pipeline for both endpoints."""
    data   = await analyze_fixture(home=home, away=away)
    league = (data.get("league") or {}).get("name")

    # Consult memory + knowledge before any recommendation
    _mem_ctx(hn=home, an=away, league=league)
    knowledge = _knowledge_consult(
        hn=home, an=away, league=league,
        is_live=bool((data.get("fixture") or {}).get("status", {}).get("elapsed")),
        has_xg=bool(data.get("statistics")),
        has_referee=bool((data.get("fixture") or {}).get("referee")),
    )

    cfg  = get_config()
    mcfg = get_methodology_config()
    fx   = data["fixture"]
    teams = data["teams"]
    hn   = teams["home"]["name"]
    an   = teams["away"]["name"]

    meth     = methodology_engine.run(data, cfg)
    learning = learning_engine.run(league=league)
    conf     = confidence_engine.run(meth, cfg)
    mkts = market_engine.run(hn, an, data, meth, conf, cfg)
    mv1  = methodology_v1.run(
        data=data, hn=hn, an=an,
        meth=meth, conf=conf,
        market=mkts,
        learning=learning, mcfg=mcfg, brain_cfg=cfg,
    )

    dc = _dc_run(
        data=data, hn=hn, an=an,
        fixture_id=fx["id"],
        meth=meth, conf=conf,
        mv1=mv1, learning=learning, cfg=cfg,
    )

    return data, dc, league, knowledge


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/decision", response_model=DecisionResponse, summary="Full Decision Table")
async def decision(
    home: str = Query(..., description="Home team name"),
    away: str = Query(..., description="Away team name"),
) -> DecisionResponse:
    """
    Aurora Decision Center — full multi-market evaluation.

    Evaluates **23 markets** across 10 market types before making any recommendation:

    | Type | Markets |
    |---|---|
    | Match Winner | Home Win, Draw, Away Win |
    | Draw No Bet | DNB Home, DNB Away |
    | Double Chance | 1X, X2, 12 |
    | Asian Handicap | AH -0.5 Home, AH +0.5 Away |
    | Goals O/U | Over 1.5 / 2.5 / 3.5 / 4.5, Under 2.5 |
    | BTTS | BTTS Yes, BTTS No |
    | Corners | Over 8.5, Over 9.5 |
    | Cards | Over 3.5, Over 4.5 |
    | Player Goals | Anytime Scorer |
    | Player Assists | Anytime Assist |

    **8 evaluation dimensions per market:**
    probability · confidence · live_confidence · expected_value ·
    methodology_score · historical_accuracy · bankroll_suitability · risk

    Markets below `min_confidence` are **automatically rejected** — they appear
    in `rejected_markets` with the specific reason.
    """
    data, dc, league, knowledge = await _run_pipeline(home=home, away=away)

    fx     = data["fixture"]
    meth_s = fx["status"]["long"]
    minute = fx["status"].get("elapsed")
    date   = fx.get("date", "")

    _memory_hook(dc, f"{dc.hn} vs {dc.an}", date, league)

    return DecisionResponse(
        match=f"{dc.hn} vs {dc.an}",
        fixture_id=dc.fixture_id,
        date=date,
        status=meth_s,
        minute=minute,
        total_evaluated=dc.total_evaluated,
        total_actionable=dc.total_actionable,
        total_rejected=dc.total_rejected,
        best_opportunity=_to_row(dc.best) if dc.best else None,
        top_5=[_to_row(m) for m in dc.top_5],
        all_markets=[_to_row(m) for m in dc.all_markets],
        rejected_markets=[_to_row(m) for m in dc.rejected],
        knowledge_notes=knowledge.knowledge_notes,
        brain=get_brain_meta(),
    )


@router.get("/opportunities", response_model=OpportunitiesResponse, summary="Top 5 Opportunities")
async def opportunities(
    home: str = Query(..., description="Home team name"),
    away: str = Query(..., description="Away team name"),
) -> OpportunitiesResponse:
    """
    Aurora Decision Center — Top 5 ranked opportunities.

    Runs the same 23-market evaluation as `/aurora/decision` but returns
    only the best 5 markets that passed all methodology gates, with:
    - A ranked ASCII table for quick scanning
    - A natural language recommendation paragraph
    - Full 8-dimension breakdown for each opportunity

    **Ranking formula (composite score):**
    ```
    score = probability×0.25 + confidence×0.20 + expected_value×0.20
              + methodology_score×0.20 + historical_accuracy×0.15
    ```

    Markets are **automatically rejected** if probability < min threshold,
    confidence < min threshold, or risk is High (configurable in brain).
    """
    data, dc, league, knowledge = await _run_pipeline(home=home, away=away)

    fx     = data["fixture"]
    meth_s = fx["status"]["long"]
    minute = fx["status"].get("elapsed")
    date   = fx.get("date", "")

    _memory_hook(dc, f"{dc.hn} vs {dc.an}", date, league)

    table          = _build_ranked_table(dc.top_5, dc.hn, dc.an)
    recommendation = _build_recommendation(dc)

    return OpportunitiesResponse(
        match=f"{dc.hn} vs {dc.an}",
        fixture_id=dc.fixture_id,
        status=meth_s,
        minute=minute,
        total_markets_evaluated=dc.total_evaluated,
        total_actionable=dc.total_actionable,
        top_5=[_to_row(m) for m in dc.top_5],
        ranked_table=table,
        recommendation=recommendation,
        knowledge_notes=knowledge.knowledge_notes,
        brain=get_brain_meta(),
    )
