"""
Aurora Copilot — Unified Integration Endpoint.

POST /aurora/copilot

Accepts natural-language input, detects intent, runs the full Aurora pipeline,
and returns a single structured JSON response designed for external AI assistant
consumption.

Response sections (all intents):
  executive_summary        — one-paragraph situation overview
  best_markets             — ranked list of actionable markets with numbers
  confidence               — score, label, explanation, data sources
  risk                     — level, flags, invalidation conditions
  bankroll_recommendation  — stake %, method, bankroll examples
  positive_factors         — NL list of favourable signals
  negative_factors         — NL list of unfavourable signals
  historical_references    — past match lessons + learning accuracy
  knowledge_notes          — applied knowledge rules
  final_recommendation     — one-sentence synthesis for direct LLM consumption
"""
from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------


class CopilotRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description=(
            "Natural-language request. Examples: "
            "\"Analyze Palmeiras vs Flamengo\", "
            "\"Best live opportunities\", "
            "\"Review bankroll\", "
            "\"What did Aurora learn today?\""
        ),
    )


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class MarketEntry(BaseModel):
    rank:           int
    market:         str
    probability:    float = Field(description="0–100 %")
    expected_value: float = Field(description="% edge vs break-even")
    confidence:     float = Field(description="0–10 data-quality score")
    risk:           str   = Field(description="Low | Medium | High")
    rationale:      str


class ConfidenceSection(BaseModel):
    score:        float  = Field(description="0–10")
    label:        str    = Field(description="strong | moderate | adequate | weak | insufficient")
    explanation:  str
    data_sources: list[str]


class RiskSection(BaseModel):
    level:                  str
    flags:                  list[str]
    invalidation_conditions: list[str]


class BankrollSection(BaseModel):
    recommended_stake_pct: float
    method:                str
    examples:              dict[str, float] = Field(
        description="Bankroll (£) → stake (£), e.g. {\"1000\": 45.0}"
    )
    reasoning:             str
    no_bet:                bool = False


class CopilotResponse(BaseModel):
    # ── Metadata ────────────────────────────────────────────────────────────
    intent:       str
    entities:     dict
    request_id:   str
    generated_at: str

    # ── Match context (populated for analyze_match; null otherwise) ─────────
    match:    str | None = None
    status:   str | None = None
    is_live:  bool       = False
    minute:   int | None = None

    # ── 10 response sections ────────────────────────────────────────────────
    executive_summary:       str
    best_markets:            list[MarketEntry]
    confidence:              ConfidenceSection
    risk:                    RiskSection
    bankroll_recommendation: BankrollSection
    positive_factors:        list[str]
    negative_factors:        list[str]
    historical_references:   list[str]
    knowledge_notes:         list[str]
    final_recommendation:    str

    # ── System ──────────────────────────────────────────────────────────────
    aurora_version: str
    brain:          dict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conf_label(score: float) -> str:
    if score >= 8:  return "strong"
    if score >= 6:  return "moderate"
    if score >= 4:  return "adequate"
    if score >= 2:  return "weak"
    return "insufficient"


def _parse_stake(stake_text: str) -> tuple[float, dict[str, float], str]:
    """
    Parse the recommended_stake NL string into (pct, examples_dict, reasoning).
    Returns (0.0, {}, stake_text) when no bet is recommended.
    """
    if "No stake recommended" in stake_text:
        return 0.0, {}, stake_text

    pct = 0.0
    m_pct = re.search(r"(\d+\.?\d*)\s*%\s+stake", stake_text)
    if m_pct:
        pct = float(m_pct.group(1))

    examples: dict[str, float] = {}
    for m in re.finditer(
        r"£([\d,]+)\s+bankroll\s+→\s+\*\*£([\d,]+(?:\.\d+)?)\*\*",
        stake_text,
    ):
        bankroll = m.group(1).replace(",", "")
        amount   = m.group(2).replace(",", "")
        examples[bankroll] = float(amount)

    # Extract the reasoning paragraph (after the last bullet/table line)
    reasoning_match = re.search(
        r"(?:£\d[\d,]*\.\n\n|£\d[\d,]*\*\*\s*\n+)(.+)",
        stake_text,
        re.DOTALL,
    )
    reasoning = reasoning_match.group(1).strip() if reasoning_match else stake_text.split("\n")[0]

    return pct, examples, reasoning


def _extract_data_sources(conf_text: str) -> list[str]:
    sources: list[str] = []
    pairs = [
        ("xG",          "Live expected-goals (xG)"),
        ("standings",   "League standings"),
        ("referee",     "Referee profile"),
        ("head-to-head","Head-to-head history"),
        ("form",        "Recent form data"),
    ]
    for keyword, label in pairs:
        if keyword.lower() in conf_text.lower() and "✓" in conf_text:
            sources.append(label)
    return sources or ["Season averages (GPG)"]


def _compose_final(
    report_or_summary: str,
    primary_mkt: str | None,
    conf_score: float,
    conf_label: str,
    stake_pct: float,
    risk_level: str,
    best_ev: float | None,
) -> str:
    if not primary_mkt or primary_mkt == "No actionable market":
        return (
            "No actionable market identified. Aurora's methodology has not found "
            "a bet with positive expected value passing all confidence and risk gates. "
            "Consider waiting for live data or confirmed lineups."
        )
    ev_str = f", EV +{best_ev:.1f}%" if best_ev and best_ev > 0 else ""
    stake_str = f", {stake_pct:.1f}% stake recommended" if stake_pct > 0 else ", no stake recommended"
    return (
        f"**{primary_mkt}** — {conf_label.title()} confidence ({conf_score:.1f}/10){stake_str}, "
        f"{risk_level} risk{ev_str}."
    )


def _empty_bankroll(reasoning: str) -> BankrollSection:
    return BankrollSection(
        recommended_stake_pct=0.0,
        method="quarter-Kelly",
        examples={},
        reasoning=reasoning,
        no_bet=True,
    )


# ---------------------------------------------------------------------------
# Pipeline helpers — one per intent
# ---------------------------------------------------------------------------


async def _run_analyze(home: str, away: str) -> dict:
    """Full intelligence pipeline for a match → structured copilot payload."""
    from src.brain import get_brain_meta, get_config, get_methodology_config
    from src.core import (
        confidence_engine,
        learning_engine,
        market_engine,
        methodology_engine,
        methodology_v1,
    )
    from src.core.decision_center import run as _dc_run
    from src.core.intelligence_engine import generate as _intel
    from src.core.knowledge_engine import consult as _kc
    from src.learning_db import get_learning_stats
    from src.memory_db import recall_context as _mem_recall
    from src.routers.analyze import analyze_fixture

    data   = await analyze_fixture(home=home, away=away)
    league = (data.get("league") or {}).get("name")
    fx     = data["fixture"]
    teams  = data["teams"]
    hn     = teams["home"]["name"]
    an     = teams["away"]["name"]

    cfg  = get_config()
    mcfg = get_methodology_config()
    meth = methodology_engine.run(data, cfg)
    lrn  = learning_engine.run(league=league)
    conf = confidence_engine.run(meth, cfg)
    mkts = market_engine.run(hn, an, data, meth, conf, cfg)
    mv1  = methodology_v1.run(
        data=data, hn=hn, an=an,
        meth=meth, conf=conf, market=mkts,
        learning=lrn, mcfg=mcfg, brain_cfg=cfg,
    )
    dc = _dc_run(
        data=data, hn=hn, an=an, fixture_id=fx["id"],
        meth=meth, conf=conf, mv1=mv1, learning=lrn, cfg=cfg,
    )
    mem_ctx   = _mem_recall(hn=hn, an=an, league=league) or {}
    knowledge = _kc(
        hn=hn, an=an, league=league,
        is_live=bool(fx.get("status", {}).get("elapsed")),
        has_xg=meth.has_xg,
        has_referee=bool(fx.get("referee")),
        meth_score=mv1.overall_score,
    )
    lstats = get_learning_stats()
    report = _intel(
        hn=hn, an=an, league=league, data=data,
        mv1=mv1, dc=dc, meth=meth,
        knowledge=knowledge, learning_stats=lstats, mem_ctx=mem_ctx,
    )

    # ── best_markets from DecisionCenter top_5 (clean numerical data) ──────
    best_markets: list[dict] = []
    for mkt in dc.top_5:
        best_markets.append({
            "rank":           mkt.rank,
            "market":         mkt.market_name,
            "probability":    round(mkt.probability, 1),
            "expected_value": round(mkt.expected_value, 1),
            "confidence":     round(mkt.confidence, 1),
            "risk":           mkt.risk,
            "rationale":      mkt.explanation,
        })

    # ── stake ────────────────────────────────────────────────────────────
    stake_pct, stake_examples, stake_reasoning = _parse_stake(report.recommended_stake)
    no_bet = stake_pct == 0.0

    # ── confidence data sources ──────────────────────────────────────────
    data_sources = _extract_data_sources(report.confidence_explanation)

    # ── risk flags ───────────────────────────────────────────────────────
    risk_flags = [
        r for r in report.risk_factors
        if not r.startswith("• No critical")
    ]

    # ── pos / neg factors ────────────────────────────────────────────────
    pos_factors = [
        p for p in report.positive_factors
        if not p.startswith("• No category")
    ]
    neg_factors = report.negative_factors

    # ── historical refs ───────────────────────────────────────────────────
    hist = report.historical_matches + report.learning_references

    # ── final recommendation ─────────────────────────────────────────────
    best_ev = dc.best.expected_value if dc.best else None
    final_rec = _compose_final(
        report_or_summary=report.executive_summary,
        primary_mkt=report.primary_recommendation,
        conf_score=report.overall_confidence,
        conf_label=_conf_label(report.overall_confidence),
        stake_pct=stake_pct,
        risk_level=report.risk_level,
        best_ev=best_ev,
    )

    return {
        "intent":    "analyze_match",
        "entities":  {"home": hn, "away": an, "league": league},
        "match":     report.match,
        "status":    report.status,
        "is_live":   report.is_live,
        "minute":    report.minute,

        "executive_summary": report.executive_summary,
        "best_markets":      best_markets,

        "confidence": {
            "score":        report.overall_confidence,
            "label":        _conf_label(report.overall_confidence),
            "explanation":  report.confidence_explanation,
            "data_sources": data_sources,
        },
        "risk": {
            "level":                  report.risk_level,
            "flags":                  risk_flags,
            "invalidation_conditions": report.invalidation_conditions,
        },
        "bankroll_recommendation": {
            "recommended_stake_pct": stake_pct,
            "method":                "quarter-Kelly",
            "examples":              stake_examples,
            "reasoning":             stake_reasoning,
            "no_bet":                no_bet,
        },

        "positive_factors":       pos_factors,
        "negative_factors":       neg_factors,
        "historical_references":  hist,
        "knowledge_notes":        report.knowledge_notes,
        "final_recommendation":   final_rec,

        "aurora_version": "Copilot v1.0",
        "brain":          get_brain_meta(),
    }


async def _run_live() -> dict:
    from src.brain import get_brain_meta
    from src.routers.live import _build_live_response

    live = await _build_live_response()
    fixtures = live.get("live_matches", [])
    count = len(fixtures)

    markets: list[dict] = []
    for i, fx in enumerate(fixtures[:5], 1):
        hn = (fx.get("teams", {}).get("home") or {}).get("name", "Home")
        an = (fx.get("teams", {}).get("away") or {}).get("name", "Away")
        minute = (fx.get("status") or {}).get("minute", "?")
        score_h = (fx.get("score", {}).get("current") or {}).get("home", 0)
        score_a = (fx.get("score", {}).get("current") or {}).get("away", 0)
        league  = (fx.get("league") or {}).get("name", "")
        markets.append({
            "rank":           i,
            "market":         f"{hn} vs {an}",
            "probability":    0.0,
            "expected_value": 0.0,
            "confidence":     0.0,
            "risk":           "Unknown",
            "rationale":      (
                f"{hn} {score_h}–{score_a} {an} · Minute {minute}"
                + (f" · {league}" if league else "")
                + ". Ask Aurora to \"Analyze [Home] vs [Away]\" for a full assessment."
            ),
        })

    summary = (
        f"{count} match{'es' if count != 1 else ''} currently live."
        if count else "No matches are currently live."
    )
    final = (
        f"Run \"Analyze [Home] vs [Away]\" on any live fixture for a full intelligence report."
        if count else "No live opportunities at this time. Check back later."
    )

    return {
        "intent":    "live_opportunities",
        "entities":  {"live_count": count},
        "match":     None,
        "status":    "Live",
        "is_live":   True,
        "minute":    None,

        "executive_summary": summary,
        "best_markets":      markets,
        "confidence": {
            "score":        0.0,
            "label":        "insufficient",
            "explanation":  "Live fixture list only. Full analysis requires a specific fixture.",
            "data_sources": ["Live API-Football feed"],
        },
        "risk": {
            "level":                  "Unknown",
            "flags":                  [],
            "invalidation_conditions": [],
        },
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0,
            "method":                "quarter-Kelly",
            "examples":              {},
            "reasoning":             "No stake recommended without full match analysis.",
            "no_bet":                True,
        },
        "positive_factors":       [],
        "negative_factors":       [],
        "historical_references":  [],
        "knowledge_notes":        [],
        "final_recommendation":   final,
        "aurora_version": "Copilot v1.0",
        "brain":          get_brain_meta(),
    }


def _run_bankroll() -> dict:
    from src.brain import get_brain_meta
    from src.learning_db import get_learning_stats

    s = get_learning_stats()
    total   = s.get("total_predictions", 0)
    wins    = s.get("wins", 0)
    losses  = s.get("losses", 0)
    pending = s.get("pending", 0)
    acc     = s.get("current_accuracy")
    roi     = s.get("roi_pct")
    best_m  = s.get("best_market", "N/A")
    worst_m = s.get("worst_market", "N/A")
    best_l  = s.get("best_league", "N/A")
    breakdown = s.get("market_breakdown", [])
    league_br = s.get("league_breakdown", [])

    acc_str = f"{acc:.1f}%" if acc is not None else "not computed"
    roi_str = f"{roi:+.1f}%" if roi is not None else "not computed"

    pos: list[str] = []
    neg: list[str] = []
    for row in breakdown:
        rule = row.get("rule", "").replace("_", " ").title()
        a    = row.get("accuracy", 0)
        w, l = row.get("wins", 0), row.get("losses", 0)
        entry = f"{rule}: {a:.1f}% ({w}W/{l}L)"
        (pos if w >= l else neg).append(entry)

    hist: list[str] = []
    for lg in league_br[:5]:
        hist.append(f"{lg.get('league','?')}: {lg.get('accuracy',0):.1f}% ({lg.get('wins',0)}W/{lg.get('losses',0)}L)")

    summary = (
        f"Aurora has tracked {total} predictions: {wins}W / {losses}L / {pending} pending. "
        f"Accuracy: {acc_str}. ROI: {roi_str}. "
        f"Best market: {best_m}. Best league: {best_l}."
    )
    final = (
        f"Performance is {'above' if (acc or 0) >= 55 else 'below'} the target accuracy threshold. "
        f"{'Maintain discipline.' if (acc or 0) >= 55 else 'Consider reducing stakes until accuracy recovers.'}"
    )

    return {
        "intent":   "bankroll_review",
        "entities": {
            "total_predictions": total,
            "wins": wins,
            "losses": losses,
            "pending": pending,
            "accuracy_pct": acc,
            "roi_pct": roi,
        },
        "match":   None, "status": None, "is_live": False, "minute": None,

        "executive_summary": summary,
        "best_markets":      [],
        "confidence": {
            "score":        min(10.0, round((total / 20) * 10, 1)) if total else 0.0,
            "label":        _conf_label(min(10.0, (total / 20) * 10) if total else 0),
            "explanation":  f"Based on {total} tracked predictions. More predictions increase statistical confidence.",
            "data_sources": ["Learning database"],
        },
        "risk": {
            "level":                  "Low" if (acc or 0) >= 55 else "High",
            "flags":                  neg[:3],
            "invalidation_conditions": [],
        },
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0,
            "method":                "quarter-Kelly",
            "examples":              {},
            "reasoning":             "Bankroll review only — no specific bet recommended. Analyze a match for a stake recommendation.",
            "no_bet":                True,
        },
        "positive_factors":      pos[:5],
        "negative_factors":      neg[:5],
        "historical_references": hist,
        "knowledge_notes":       [],
        "final_recommendation":  final,
        "aurora_version": "Copilot v1.0",
        "brain":          get_brain_meta(),
    }


def _run_learning() -> dict:
    from src.brain import get_brain_meta
    from src.learning_db import get_learning_stats

    s = get_learning_stats()
    total   = s.get("total_predictions", 0)
    wins    = s.get("wins", 0)
    losses  = s.get("losses", 0)
    acc     = s.get("current_accuracy")
    breakdown = s.get("market_breakdown", [])
    league_br = s.get("league_breakdown", [])

    working   = [r for r in breakdown if r.get("wins", 0) >= r.get("losses", 0)]
    struggling = [r for r in breakdown if r.get("losses", 0) > r.get("wins", 0)]

    hist: list[str] = []
    for lg in league_br[:6]:
        hist.append(
            f"{lg.get('league','?')}: {lg.get('accuracy',0):.1f}% accuracy "
            f"({lg.get('wins',0)}W/{lg.get('losses',0)}L)"
        )
    for r in working[:3]:
        hist.append(
            f"Market '{r.get('rule','?').replace('_',' ').title()}' — "
            f"{r.get('accuracy',0):.1f}% accuracy"
        )

    pos = [
        f"{r.get('rule','?').replace('_',' ').title()}: {r.get('accuracy',0):.1f}% ({r.get('wins',0)}W/{r.get('losses',0)}L)"
        for r in working[:5]
    ]
    neg = [
        f"{r.get('rule','?').replace('_',' ').title()}: {r.get('accuracy',0):.1f}% ({r.get('wins',0)}W/{r.get('losses',0)}L)"
        for r in struggling[:5]
    ]

    summary = (
        f"Aurora has resolved {total} predictions: {wins}W / {losses}L. "
        f"Current accuracy: {f'{acc:.1f}%' if acc is not None else 'not computed yet'}. "
        f"Aurora learns continuously — weight changes require 20+ consistent observations."
    )
    final = (
        "Learning engine active. "
        f"{'Strong markets to continue: ' + ', '.join(r.get('rule','').replace('_',' ').title() for r in working[:2]) + '.' if working else ''}"
        f"{'Markets needing caution: ' + ', '.join(r.get('rule','').replace('_',' ').title() for r in struggling[:2]) + '.' if struggling else ''}"
    ).strip()

    return {
        "intent":   "learning_recap",
        "entities": {"total_predictions": total, "wins": wins, "losses": losses, "accuracy_pct": acc},
        "match":   None, "status": None, "is_live": False, "minute": None,

        "executive_summary": summary,
        "best_markets":      [],
        "confidence": {
            "score":        min(10.0, round((total / 20) * 10, 1)) if total else 0.0,
            "label":        _conf_label(min(10.0, (total / 20) * 10) if total else 0),
            "explanation":  f"Statistical confidence grows with more resolved predictions. Currently {total} resolved.",
            "data_sources": ["Learning database", "Evolution engine"],
        },
        "risk": {
            "level":                  "Low" if (acc or 0) >= 55 else "High",
            "flags":                  neg[:3],
            "invalidation_conditions": [],
        },
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0, "method": "quarter-Kelly",
            "examples": {}, "no_bet": True,
            "reasoning": "Learning review only.",
        },
        "positive_factors":      pos,
        "negative_factors":      neg,
        "historical_references": hist,
        "knowledge_notes":       [],
        "final_recommendation":  final,
        "aurora_version": "Copilot v1.0",
        "brain":          get_brain_meta(),
    }


def _run_knowledge(query: str) -> dict:
    from src.brain import get_brain_meta
    from src.knowledge_db import search_knowledge_items

    results = search_knowledge_items(query, limit=6)
    notes: list[str] = []
    for item in results:
        cat   = item.get("category", "").replace("_", " ").title()
        title = item.get("title", "")
        desc  = item.get("description", "")
        conf  = item.get("confidence", 0)
        notes.append(f"[{cat} · {conf:.0%}] {title}: {desc}")

    summary = (
        f"Found {len(results)} knowledge item(s) for \"{query}\"."
        if results else
        f"No knowledge items matched \"{query}\"."
    )
    final = (
        f"Knowledge base has {len(results)} relevant rule(s) for \"{query}\". "
        "These are applied before every Aurora prediction."
    )

    return {
        "intent":   "knowledge_search",
        "entities": {"query": query},
        "match":   None, "status": None, "is_live": False, "minute": None,

        "executive_summary": summary,
        "best_markets":      [],
        "confidence": {
            "score": 0.0, "label": "insufficient",
            "explanation": "Knowledge search only — no match analysis performed.",
            "data_sources": ["Knowledge database"],
        },
        "risk": {
            "level": "Unknown", "flags": [],
            "invalidation_conditions": [],
        },
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0, "method": "quarter-Kelly",
            "examples": {}, "no_bet": True,
            "reasoning": "No bet recommended from knowledge search alone.",
        },
        "positive_factors":      [],
        "negative_factors":      [],
        "historical_references": [],
        "knowledge_notes":       notes,
        "final_recommendation":  final,
        "aurora_version": "Copilot v1.0",
        "brain":          get_brain_meta(),
    }


def _run_fallback(message: str, intent: str) -> dict:
    from src.brain import get_brain_meta
    return {
        "intent":   intent,
        "entities": {},
        "match":   None, "status": None, "is_live": False, "minute": None,

        "executive_summary": (
            f"Intent detected: {intent}. "
            "For a full analysis, ask: \"Analyze [Home Team] vs [Away Team]\", "
            "\"Best live opportunities\", \"Review bankroll\", or \"What did Aurora learn?\"."
        ),
        "best_markets":      [],
        "confidence": {
            "score": 0.0, "label": "insufficient",
            "explanation": "No analysis pipeline run for this intent.",
            "data_sources": [],
        },
        "risk": {
            "level": "Unknown", "flags": [],
            "invalidation_conditions": [],
        },
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0, "method": "quarter-Kelly",
            "examples": {}, "no_bet": True,
            "reasoning": "No bet recommended.",
        },
        "positive_factors":      [],
        "negative_factors":      [],
        "historical_references": [],
        "knowledge_notes":       [],
        "final_recommendation":  (
            "Please provide a specific match or intent. Examples: "
            "\"Analyze Arsenal vs Chelsea\", \"Best live opportunities\"."
        ),
        "aurora_version": "Copilot v1.0",
        "brain":          get_brain_meta(),
    }


# ---------------------------------------------------------------------------
# POST /aurora/copilot
# ---------------------------------------------------------------------------


@router.post(
    "/copilot",
    response_model=CopilotResponse,
    summary="Aurora Copilot — Unified Integration Endpoint",
)
async def copilot(body: CopilotRequest) -> CopilotResponse:
    """
    **Aurora's official integration endpoint** for external AI assistants, agents,
    and automation pipelines.

    Send any natural-language request. Aurora:
    1. Detects intent automatically
    2. Calls all required internal engines
    3. Merges outputs into one structured response

    **Supported intents (automatic detection):**
    | Example Input | Intent |
    |---|---|
    | *"Analyze Palmeiras vs Flamengo"* | `analyze_match` |
    | *"Man City x Arsenal"* | `analyze_match` |
    | *"Best live opportunities"* | `live_opportunities` |
    | *"Review bankroll"* | `bankroll_review` |
    | *"What did Aurora learn today?"* | `learning_recap` |
    | *"What do you know about BTTS?"* | `knowledge_search` |

    **Response sections** (always present, populated based on intent):
    - `executive_summary` — one-paragraph situation overview
    - `best_markets` — ranked markets with probability, EV, confidence, risk, rationale
    - `confidence` — score (0–10), label, explanation, data sources used
    - `risk` — level, risk flags, invalidation conditions
    - `bankroll_recommendation` — stake %, quarter-Kelly examples, reasoning
    - `positive_factors` — favourable signals driving the recommendation
    - `negative_factors` — unfavourable signals and weaknesses
    - `historical_references` — past match lessons and learning accuracy
    - `knowledge_notes` — applied Aurora knowledge rules (from 39-rule KB)
    - `final_recommendation` — one-sentence synthesis for direct LLM consumption

    All numerical fields are machine-readable. All string fields are human-readable.
    Designed for direct integration with GPT-4, Claude, Gemini, and custom agents.
    """
    from src.core.copilot_engine import detect_intent

    message = body.message.strip()
    intent, entities = detect_intent(message)
    request_id = secrets.token_hex(4)

    try:
        if intent == "analyze_match":
            home = entities.get("home", "")
            away = entities.get("away", "")
            if not home or not away:
                payload = _run_fallback(message, intent)
            else:
                payload = await _run_analyze(home, away)

        elif intent == "live_opportunities":
            payload = await _run_live()

        elif intent == "bankroll_review":
            payload = _run_bankroll()

        elif intent == "learning_recap":
            payload = _run_learning()

        elif intent == "knowledge_search":
            payload = _run_knowledge(entities.get("query", message))

        else:
            payload = _run_fallback(message, intent)

    except Exception as exc:
        logger.error("Copilot unified error [%s]: %s", intent, exc, exc_info=True)
        from src.brain import get_brain_meta
        payload = {
            "intent":   intent,
            "entities": entities,
            "match":   None, "status": None, "is_live": False, "minute": None,
            "executive_summary": f"Aurora encountered an error: {exc}. Check the fixture name or try again.",
            "best_markets":      [],
            "confidence": {"score": 0.0, "label": "insufficient", "explanation": str(exc), "data_sources": []},
            "risk": {"level": "Unknown", "flags": [str(exc)], "invalidation_conditions": []},
            "bankroll_recommendation": {"recommended_stake_pct": 0.0, "method": "quarter-Kelly", "examples": {}, "reasoning": "Error state.", "no_bet": True},
            "positive_factors": [], "negative_factors": [],
            "historical_references": [], "knowledge_notes": [],
            "final_recommendation": "Error — no recommendation available.",
            "aurora_version": "Copilot v1.0",
            "brain": get_brain_meta(),
        }

    return CopilotResponse(
        intent       = payload["intent"],
        entities     = payload.get("entities", entities),
        request_id   = request_id,
        generated_at = _now_iso(),
        match        = payload.get("match"),
        status       = payload.get("status"),
        is_live      = payload.get("is_live", False),
        minute       = payload.get("minute"),

        executive_summary = payload["executive_summary"],
        best_markets      = [MarketEntry(**m) for m in payload.get("best_markets", [])],
        confidence        = ConfidenceSection(**payload["confidence"]),
        risk              = RiskSection(**payload["risk"]),
        bankroll_recommendation = BankrollSection(**payload["bankroll_recommendation"]),
        positive_factors        = payload.get("positive_factors", []),
        negative_factors        = payload.get("negative_factors", []),
        historical_references   = payload.get("historical_references", []),
        knowledge_notes         = payload.get("knowledge_notes", []),
        final_recommendation    = payload["final_recommendation"],
        aurora_version          = payload.get("aurora_version", "Copilot v1.0"),
        brain                   = payload.get("brain", {}),
    )
