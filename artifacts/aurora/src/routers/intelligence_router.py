"""
GET /aurora/intelligence — Aurora Intelligence Engine endpoint.

Returns 11 natural-language sections that explain every aspect of a
recommendation the way a professional analyst would:

  executive_summary        — 3-4 sentence overview
  main_factors             — top factors that drove the recommendation
  positive_factors         — supporting signals
  negative_factors         — signals arguing against
  risk_factors             — specific risks
  recommended_stake        — quarter-Kelly stake with full reasoning
  alternative_markets      — next-best options with explanations
  confidence_explanation   — why the confidence score is what it is
  invalidation_conditions  — what would make this analysis wrong
  learning_references      — Aurora's track record informs this call
  historical_matches       — relevant past fixtures from memory
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.brain import get_brain_meta, get_config, get_methodology_config
from src.core import confidence_engine, learning_engine, market_engine, methodology_engine, methodology_v1
from src.core.decision_center import run as _dc_run
from src.core.intelligence_engine import IntelligenceReport, generate as _generate
from src.core.knowledge_engine import consult as _knowledge_consult
from src.learning_db import get_learning_stats
from src.memory_db import recall_context as _mem_recall
from src.routers.analyze import analyze_fixture

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------


class IntelligenceResponse(BaseModel):
    fixture_id:   int
    match:        str
    date:         str
    status:       str
    minute:       int | None
    is_live:      bool

    primary_recommendation: str
    overall_confidence:     float
    risk_level:             str

    # 11 natural-language sections
    executive_summary:       str
    main_factors:            list[str]
    positive_factors:        list[str]
    negative_factors:        list[str]
    risk_factors:            list[str]
    recommended_stake:       str
    alternative_markets:     list[str]
    confidence_explanation:  str
    invalidation_conditions: list[str]
    learning_references:     list[str]
    historical_matches:      list[str]

    knowledge_notes:  list[str]
    generated_at:     str
    aurora_version:   str
    brain:            dict[str, Any]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/intelligence",
    response_model=IntelligenceResponse,
    summary="Aurora Intelligence Report",
)
async def intelligence(
    home: str = Query(..., description="Home team name"),
    away: str = Query(..., description="Away team name"),
) -> IntelligenceResponse:
    """
    Aurora Intelligence Engine — professional analyst reasoning for every recommendation.

    This endpoint runs the **complete Aurora pipeline** and then produces
    11 natural-language sections that explain the analysis in full:

    | Section | What it tells you |
    |---|---|
    | `executive_summary` | 3–4 sentence overview of the match and recommendation |
    | `main_factors` | Top 7 factors that drove the scoring, ranked by contribution |
    | `positive_factors` | Signals actively supporting the recommended bet |
    | `negative_factors` | Signals arguing against — risks you must know |
    | `risk_factors` | Specific flags: missing data, red flags, elevated uncertainty |
    | `recommended_stake` | Quarter-Kelly stake with bankroll examples |
    | `alternative_markets` | Next-best markets with EV, probability, and reasoning |
    | `confidence_explanation` | Why the confidence score is what it is |
    | `invalidation_conditions` | What would make this analysis wrong or obsolete |
    | `learning_references` | How Aurora's track record informs this call |
    | `historical_matches` | Relevant past fixtures and patterns from memory |

    **Pipeline (in order):**
    1. Live data fetch via `analyze_fixture`
    2. 15-category methodology scoring
    3. Memory recall — past lessons, team/league profiles
    4. Knowledge engine — 13 categories of foundational rules
    5. Learning stats — historical market accuracy
    6. 23-market decision center evaluation
    7. Intelligence Engine — natural language generation

    **Every number is explained in words. No raw arrays of statistics.**
    """
    # ── 1. Live data ───────────────────────────────────────────────────────
    data   = await analyze_fixture(home=home, away=away)
    league = (data.get("league") or {}).get("name")

    fx    = data["fixture"]
    teams = data["teams"]
    hn    = teams["home"]["name"]
    an    = teams["away"]["name"]

    # ── 2. Methodology engines ────────────────────────────────────────────
    cfg  = get_config()
    mcfg = get_methodology_config()

    meth     = methodology_engine.run(data, cfg)
    learning = learning_engine.run(league=league)
    conf     = confidence_engine.run(meth, cfg)
    mkts     = market_engine.run(hn, an, data, meth, conf, cfg)
    mv1      = methodology_v1.run(
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

    # ── 3. Memory recall ──────────────────────────────────────────────────
    mem_ctx = _mem_recall(hn=hn, an=an, league=league) or {}

    # ── 4. Knowledge engine ───────────────────────────────────────────────
    knowledge = _knowledge_consult(
        hn=hn, an=an, league=league,
        is_live=bool(fx.get("status", {}).get("elapsed")),
        has_xg=meth.has_xg,
        has_referee=bool(fx.get("referee")),
        meth_score=mv1.overall_score,
    )

    # ── 5. Learning stats ─────────────────────────────────────────────────
    learning_stats = get_learning_stats()

    # ── 6. Generate intelligence report ──────────────────────────────────
    report: IntelligenceReport = _generate(
        hn=hn, an=an, league=league,
        data=data,
        mv1=mv1,
        dc=dc,
        meth=meth,
        knowledge=knowledge,
        learning_stats=learning_stats,
        mem_ctx=mem_ctx,
    )

    return IntelligenceResponse(
        fixture_id=report.fixture_id,
        match=report.match,
        date=report.date,
        status=report.status,
        minute=report.minute,
        is_live=report.is_live,
        primary_recommendation=report.primary_recommendation,
        overall_confidence=report.overall_confidence,
        risk_level=report.risk_level,
        executive_summary=report.executive_summary,
        main_factors=report.main_factors,
        positive_factors=report.positive_factors,
        negative_factors=report.negative_factors,
        risk_factors=report.risk_factors,
        recommended_stake=report.recommended_stake,
        alternative_markets=report.alternative_markets,
        confidence_explanation=report.confidence_explanation,
        invalidation_conditions=report.invalidation_conditions,
        learning_references=report.learning_references,
        historical_matches=report.historical_matches,
        knowledge_notes=report.knowledge_notes,
        generated_at=report.generated_at,
        aurora_version=report.aurora_version,
        brain=get_brain_meta(),
    )
