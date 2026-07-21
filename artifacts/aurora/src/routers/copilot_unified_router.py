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
    session_id: str | None = Field(
        None,
        description=(
            "Continue an existing conversation session. "
            "Omit or send null to start a new session. "
            "The session_id returned in each response should be sent back in the next request."
        ),
    )
    debug: bool = Field(
        False,
        description=(
            "When true, include a `debug` audit block "
            "(fixture_found, markets_source, xg_*, DATA_MISSING markers, etc.). "
            "Also enabled via AURORA_DEBUG=1 or `#debug` in the message."
        ),
    )
    # v4.5.2 — optional presentation prefs from FE (never fed into frozen engines)
    conversation_preferences: dict | None = Field(
        None,
        description=(
            "Optional UI presentation preferences: emojis, enthusiasm, structure, detail. "
            "Used only for social/presence humanization. Never alters markets/engines."
        ),
    )
    # v4.7 — About You (Identity Center). Separate from betting user_profile.
    about_you: dict | None = Field(
        None,
        description=(
            "Optional identity profile: name, role, favorite_team, project. "
            "Stored on ctx['about_you']. Never alters markets/engines."
        ),
    )
    force_refresh: bool = Field(
        False,
        description=(
            "Emergency Cost Protection: premium path — force provider refresh. "
            "When false, prefer cache/stale and suppress duplicate fetches."
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


class MatchTeamCard(BaseModel):
    name: str
    logo: str | None = None


class MatchScoreCard(BaseModel):
    home: int
    away: int


class MatchCompetitionCard(BaseModel):
    name: str
    logo: str | None = None
    country: str | None = None
    round: str | None = None


class MatchVenueCard(BaseModel):
    name: str
    city: str | None = None


class MatchMomentumCard(BaseModel):
    label: str
    side: str | None = None
    detail: str | None = None


class MatchPredictabilityCard(BaseModel):
    score: float
    label: str
    summary: str


class MatchCard(BaseModel):
    """Aurora v3.3.1-beta — rich live/prematch header (presentation only)."""
    home: MatchTeamCard
    away: MatchTeamCard
    score: MatchScoreCard | None = None
    competition: MatchCompetitionCard | None = None
    venue: MatchVenueCard | None = None
    status_label: str | None = None
    minute: int | None = None
    is_live: bool = False
    momentum: MatchMomentumCard | None = None
    predictability: MatchPredictabilityCard | None = None


class CopilotResponse(BaseModel):
    # ── Metadata ────────────────────────────────────────────────────────────
    intent:             str
    entities:           dict
    request_id:         str
    generated_at:       str
    routing_confidence: float = Field(0.0, description="NL router confidence 0.0–1.0")

    # ── Match context (populated for analyze_match; null otherwise) ─────────
    match:    str | None = None
    status:   str | None = None
    is_live:  bool       = False
    minute:   int | None = None
    match_card: MatchCard | None = Field(
        default=None,
        description="Rich match header: logos, score, competition, venue, momentum.",
    )
    fixture_status: str | None = Field(
        default=None,
        description="FOUND | PARTIAL | NOT_FOUND | FICTIONAL — Fixture Integrity Guard.",
    )
    fixture_found: bool | None = Field(
        default=None,
        description="True only when a real sports fixture was resolved.",
    )
    fixture_quality: str | None = Field(
        default=None,
        description="VALID | PARTIAL | INVALID — blocks markets/confidence when INVALID.",
    )
    # Temporary production audit — remove after version confirmation
    backend_commit: str | None = Field(
        default=None,
        description="Short git SHA of the running backend (audit only).",
    )
    frontend_commit: str | None = Field(
        default=None,
        description="UI build id / bundle hash when known to the API host (audit only).",
    )

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

    # ── Session ─────────────────────────────────────────────────────────────
    session_id: str = Field("", description="Persist this and send it back in the next request to maintain conversation context.")

    # ── System ──────────────────────────────────────────────────────────────
    aurora_version: str
    brain:          dict

    # ── Conversational guidance ──────────────────────────────────────────────
    suggested_follow_ups: list[str] = Field(
        default_factory=list,
        description=(
            "Contextual follow-up suggestions in Brazilian Portuguese. "
            "Display as quick-reply chips or a bulleted list after the main response."
        ),
    )
    response_metadata: dict = Field(
        default_factory=dict,
        description="Presentation-only metadata (public_strengths, mode, etc.).",
    )

    # ── DEBUG audit (optional) ───────────────────────────────────────────────
    debug: dict | None = Field(
        default=None,
        description=(
            "Audit provenance when debug mode is on: fixture_found, fixture_id, "
            "data_source, markets_source, market_reasoning, fallback_used, "
            "confidence_source, corner_average, goal_average, xg_home, xg_away, "
            "form_score. Missing values are the string DATA_MISSING."
        ),
    )


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


def _resolve_fixture_confidence(
    score: float,
    *,
    fixture_located: bool,
    degraded: bool,
    allow_partial_analysis: bool = False,
    data_completeness: float = 0.0,
    rate_limited: bool = False,
) -> tuple[float, str]:
    """
    Confidence must reflect fixture quality (v3.3.1-beta / 8.4-A.7).

    - Fully healthy located fixture → moderate or strong
    - Allowable PARTIAL (min signals + completeness ≥ 0.20) → weak/adequate
      preliminary band (never hard refuse at 1.5)
    - Truly insufficient / invalid → very low (insufficient)
    """
    try:
        raw = float(score)
    except (TypeError, ValueError):
        raw = 0.0

    if allow_partial_analysis:
        try:
            from src.core.partial_analysis import resolve_preliminary_confidence

            return resolve_preliminary_confidence(
                raw,
                data_completeness=data_completeness,
                rate_limited=rate_limited,
            )
        except Exception:
            capped = round(min(max(raw, 2.5), 4.5), 1)
            return capped, "weak" if capped < 4 else "adequate"

    if degraded or not fixture_located:
        capped = round(min(max(raw, 0.0), 1.5), 1)
        return capped, "insufficient"

    if raw >= 7.5:
        return round(min(raw, 10.0), 1), "strong"
    # Located fixture → at least moderate (never advertise weak as "ok")
    return round(max(raw, 6.0), 1), "moderate"


def _parse_stake(stake_text: str) -> tuple[float, dict[str, float], str]:
    """
    Parse the recommended_stake NL string into (pct, examples_dict, reasoning).
    Returns (0.0, {}, stake_text) when no bet is recommended.
    """
    # Accept both English and Portuguese "no bet" signals
    _NO_BET_PHRASES = (
        "No stake recommended", "no stake", "no bet",
        "Nenhuma stake", "sem stake", "não aposte", "não há aposta",
        "High risk", "Alto risco", "stake 0%", "0% stake",
    )
    if any(phrase.lower() in stake_text.lower() for phrase in _NO_BET_PHRASES):
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
    text_lower = conf_text.lower()
    pairs = [
        ("xg",           "Expected Goals (xG)"),
        ("expected_goal","Expected Goals (xG)"),
        ("standings",    "Classificação da liga"),
        ("tabela",       "Classificação da liga"),
        ("referee",      "Perfil do árbitro"),
        ("árbitro",      "Perfil do árbitro"),
        ("arbitro",      "Perfil do árbitro"),
        ("head-to-head", "Histórico de confrontos"),
        ("h2h",          "Histórico de confrontos"),
        ("confronto",    "Histórico de confrontos"),
        ("form",         "Forma recente"),
        ("forma",        "Forma recente"),
        ("lineup",       "Escalação confirmada"),
        ("escala",       "Escalação confirmada"),
    ]
    seen: set[str] = set()
    for keyword, label in pairs:
        if keyword in text_lower and label not in seen:
            sources.append(label)
            seen.add(label)
    return sources or ["Médias da temporada (GPG)"]


def _compose_final(
    report_or_summary: str,
    primary_mkt: str | None,
    conf_score: float,
    conf_label: str,
    stake_pct: float,
    risk_level: str,
    best_ev: float | None,
) -> str:
    _CONF_PT = {
        "strong": "forte", "moderate": "moderada", "adequate": "adequada",
        "weak": "fraca", "insufficient": "insuficiente",
    }
    _RISK_PT = {"Low": "Baixo", "Medium": "Médio", "High": "Alto"}
    if not primary_mkt or primary_mkt == "No actionable market":
        return (
            "Nenhum mercado acionável identificado. A metodologia da Aurora não encontrou "
            "uma aposta com valor esperado positivo aprovada em todos os filtros de confiança e risco. "
            "Considere aguardar dados ao vivo ou escalações confirmadas."
        )
    ev_str = f", VE +{best_ev:.1f}%" if best_ev and best_ev > 0 else ""
    stake_str = f", stake de {stake_pct:.1f}% recomendada" if stake_pct > 0 else ", sem stake recomendada"
    conf_label_pt = _CONF_PT.get(conf_label, conf_label)
    risk_level_pt = _RISK_PT.get(risk_level, risk_level)
    return (
        f"**{primary_mkt}** — Confiança {conf_label_pt} ({conf_score:.1f}/10){stake_str}, "
        f"risco {risk_level_pt}{ev_str}."
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


async def _run_analyze(
    home: str,
    away: str,
    prefer_live: bool = False,
    *,
    force_refresh: bool = False,
) -> dict:
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
    from src.core.fixture_status import fixture_is_live
    from src.core.inference_context import scan_analyze_data
    from src.core.intelligence_engine import generate as _intel
    from src.core.knowledge_engine import consult as _kc
    from src.learning_db import get_learning_stats
    from src.memory_db import recall_context as _mem_recall
    from src.routers.analyze import analyze_fixture

    # Inference Layer V2 — never abort on partial fixture data
    data = await analyze_fixture(
        home=home,
        away=away,
        prefer_live=prefer_live,
        soft=True,
        force_refresh=bool(force_refresh),
    )
    ictx = scan_analyze_data(data)
    is_partial = bool(data.get("_partial")) or (data.get("fixture") or {}).get("id") == 0

    league = (data.get("league") or {}).get("name")
    fx     = data["fixture"]
    teams  = data["teams"]
    hn     = teams["home"]["name"]
    an     = teams["away"]["name"]

    status_block = fx.get("status") or {}
    status_short = str(status_block.get("short") or "")
    api_is_live = fixture_is_live(status_block)
    api_minute = status_block.get("minute")

    fixture_id_early = (data.get("fixture") or {}).get("id") or fx.get("id") or 0
    try:
        fixture_id_early = int(fixture_id_early or 0)
    except (TypeError, ValueError):
        fixture_id_early = 0
    fixture_located_early = (not is_partial) and fixture_id_early > 0

    logger.warning(
        "[DEBUG] fixture_resolver=analyze_soft fixture_found=%s fixture_id=%s "
        "market_generation_enabled=%s partial=%s home=%r away=%r",
        fixture_located_early,
        fixture_id_early or None,
        fixture_located_early,
        is_partial,
        hn,
        an,
    )

    # INVALID only (fiction / unknown) — abort before engines.
    # PARTIAL (known teams, no fixture): continue with fallback analysis + markets.
    # Live/API rescue: if soft analyze already located a real fixture_id, do not
    # INVALID solely because the typed names lack aliases (consulta live first).
    from src.core.fixture_integrity import (
        assess_named_fixture as _assess_named_early,
        blocked_integrity_payload as _blocked_early,
    )
    from src.core.team_branding import enrich_analyze_teams as _enrich_teams

    _pre_early = _assess_named_early(home or hn, away or an)
    if _pre_early.is_blocked:
        if fixture_located_early:
            logger.warning(
                "[DEBUG] fixture_resolver=live_api_rescue fixture_quality=VALID_LOCATED "
                "fixture_id=%s home=%r away=%r (skipped INVALID early abort)",
                fixture_id_early,
                hn,
                an,
            )
        else:
            logger.warning(
                "[DEBUG] fixture_resolver=early_abort fixture_quality=INVALID reasons=%s",
                _pre_early.reasons,
            )
            return _blocked_early(_pre_early, brain=get_brain_meta())

    # Enrich logos / league hints on soft/partial payloads before engines + card
    data = _enrich_teams(data, home=home or hn, away=away or an)
    hn = (data.get("teams") or {}).get("home", {}).get("name") or hn
    an = (data.get("teams") or {}).get("away", {}).get("name") or an

    logger.info(
        "intent=analyze_match fixture=%s vs %s status=%s minute=%s is_live=%s "
        "pipeline=intelligence_engine prefer_live=%s partial=%s completeness=%.2f",
        hn, an, status_short, api_minute, api_is_live, prefer_live,
        is_partial, ictx.data_completeness,
    )

    cfg  = get_config()
    mcfg = get_methodology_config()
    meth = methodology_engine.run(data, cfg)

    # Hard guarantee: API live status ⇒ meth.is_live (never First Half + pré-jogo)
    if api_is_live and not meth.is_live:
        logger.warning(
            "intent=analyze_match FIX is_live mismatch: api=True meth=False "
            "status=%s — forcing meth.is_live=True",
            status_short,
        )
        meth.is_live = True
    if api_is_live and api_minute is not None and not meth.minute:
        try:
            meth.minute = int(api_minute)
        except (TypeError, ValueError):
            pass

    lrn  = learning_engine.run(league=league)
    conf = confidence_engine.run(meth, cfg)
    mkts = market_engine.run(hn, an, data, meth, conf, cfg)
    mv1  = methodology_v1.run(
        data=data, hn=hn, an=an,
        meth=meth, conf=conf, market=mkts,
        learning=lrn, mcfg=mcfg, brain_cfg=cfg,
    )
    dc = _dc_run(
        data=data, hn=hn, an=an, fixture_id=fx.get("id") or 0,
        meth=meth, conf=conf, mv1=mv1, learning=lrn, cfg=cfg,
    )
    mem_ctx   = _mem_recall(hn=hn, an=an, league=league) or {}
    knowledge = _kc(
        hn=hn, an=an, league=league,
        is_live=bool(meth.is_live or api_is_live),
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

    # Inference Layer V2 — apply completeness penalty to reported confidence
    raw_score = float(report.overall_confidence)
    adj_score = ictx.apply_to_score(raw_score)
    if adj_score != raw_score:
        logger.info(
            "inference: confidence %s → %s (penalty=%.2f completeness=%.2f missing=%s)",
            raw_score, adj_score, ictx.total_penalty(),
            ictx.data_completeness, ictx.missing_signals,
        )

    fixture_id = (data.get("fixture") or {}).get("id") or fx.get("id") or 0
    fixture_located = (not is_partial) and int(fixture_id or 0) > 0
    degraded = bool(
        is_partial
        or not fixture_located
        or ictx.data_completeness < 0.35
    )
    # Phase 8.4-A.7 — partial recovery: valid entities + min signals → preliminary
    _rate_limited = False
    _allow_partial = False
    try:
        from src.core.partial_analysis import (
            allow_partial_analysis as _allow_pa,
            detect_rate_limited as _detect_rl,
        )

        _rate_limited = _detect_rl(ictx) or _detect_rl(
            notes=[str(data.get("_partial_reason") or "")]
        )
        _fx_quality_guess = (
            "PARTIAL" if (is_partial or not fixture_located or degraded) else "VALID"
        )
        _allow_partial = _allow_pa(
            entity_invalid=False,
            fixture_quality=_fx_quality_guess,
            data_completeness=float(ictx.data_completeness or 0.0),
            available_signals=list(ictx.available_signals or []),
            inferred_signals=list(ictx.inferred_signals or []),
            data=data if isinstance(data, dict) else None,
            rate_limited=_rate_limited,
        )
    except Exception as _pa_exc:
        logger.warning("partial_analysis gate skipped (%s)", _pa_exc)
        _allow_partial = False
        _rate_limited = False

    conf_score, conf_label = _resolve_fixture_confidence(
        adj_score,
        fixture_located=fixture_located,
        degraded=degraded,
        allow_partial_analysis=_allow_partial,
        data_completeness=float(ictx.data_completeness or 0.0),
        rate_limited=_rate_limited,
    )
    logger.warning(
        "[AUDIT] fixture_confidence located=%s degraded=%s allow_partial=%s "
        "rate_limited=%s score=%.1f label=%s (raw=%.1f adj=%.1f completeness=%.2f)",
        fixture_located,
        degraded,
        _allow_partial,
        _rate_limited,
        conf_score,
        conf_label,
        raw_score,
        adj_score,
        ictx.data_completeness,
    )

    final_is_live = bool(report.is_live or api_is_live)
    final_minute = report.minute if report.minute is not None else api_minute
    final_status = report.status or status_block.get("long") or status_short

    if final_is_live and "pre-match" in (report.executive_summary or "").lower():
        logger.error(
            "intent=analyze_match BUG: live fixture still had pre-match summary "
            "fixture=%s vs %s status=%s",
            hn, an, status_short,
        )

    logger.info(
        "intent=analyze_match fixture=%s vs %s status=%s minute=%s is_live=%s "
        "pipeline=intelligence_engine result_ok=1",
        hn, an, status_short, final_minute, final_is_live,
    )

    # ── best_markets from DecisionCenter top_5 (clean numerical data) ──────
    best_markets: list[dict] = []
    for mkt in dc.top_5:
        best_markets.append({
            "rank":           mkt.rank,
            "market":         mkt.market_name,
            "probability":    round(mkt.probability, 1),
            "expected_value": round(mkt.expected_value, 1),
            "confidence":     round(max(0.0, mkt.confidence - ictx.total_penalty() * 0.35), 1),
            "risk":           mkt.risk,
            "rationale":      mkt.explanation,
        })

    # ── stake ────────────────────────────────────────────────────────────
    stake_pct, stake_examples, stake_reasoning = _parse_stake(report.recommended_stake)
    # Partial / heavily incomplete data → force no_bet (still return analysis)
    if is_partial or ictx.data_completeness < 0.35:
        stake_pct = 0.0
        stake_examples = {}
        stake_reasoning = (
            (stake_reasoning or "")
            + " Dados parciais — Inference Layer V2 bloqueou stake até completar sinais."
        ).strip()
    no_bet = stake_pct == 0.0

    # ── confidence data sources ──────────────────────────────────────────
    data_sources = _extract_data_sources(report.confidence_explanation)
    if is_partial and "Inference Layer V2 (dados parciais)" not in data_sources:
        data_sources = ["Inference Layer V2 (dados parciais)"] + data_sources

    # ── risk flags ───────────────────────────────────────────────────────
    risk_flags = [
        r for r in report.risk_factors
        if not r.startswith("• No critical")
    ]
    if ictx.missing_signals:
        risk_flags.append(
            f"Dados incompletos ({ictx.data_completeness * 100:.0f}%): "
            + ", ".join(ictx.missing_signals)
        )

    # ── pos / neg factors ────────────────────────────────────────────────
    pos_factors = [
        p for p in report.positive_factors
        if not p.startswith("• No category")
    ]
    neg_factors = list(report.negative_factors)
    if is_partial:
        neg_factors.insert(
            0,
            "Fixture oficial não localizada — análise em modo degradado "
            "(confiança reduzida; sem stake).",
        )

    # ── historical refs ───────────────────────────────────────────────────
    hist = report.historical_matches + report.learning_references

    # ── explainability (knowledge_notes — visible without frontend changes) ─
    k_notes = list(report.knowledge_notes) + ictx.knowledge_notes_pt()

    # ── final recommendation ─────────────────────────────────────────────
    best_ev = dc.best.expected_value if dc.best else None
    final_rec = _compose_final(
        report_or_summary=report.executive_summary,
        primary_mkt=report.primary_recommendation,
        conf_score=conf_score,
        conf_label=conf_label,
        stake_pct=stake_pct,
        risk_level=report.risk_level if not is_partial else "High",
        best_ev=best_ev,
    )
    if _allow_partial:
        final_rec = (
            f"Leitura preliminar para **{hn} x {an}** com dados parciais "
            f"(confiança {conf_label}, {conf_score:.1f}/10). "
            f"Sem stake até completar sinais. " + final_rec
        )
    elif is_partial or degraded:
        final_rec = (
            f"Análise parcial para **{hn} x {an}**: a partida não foi confirmada "
            f"na API. Confiança muito baixa ({conf_score:.1f}/10). "
            f"Tente o nome oficial dos times para dados completos. " + final_rec
        )

    conf_explanation = report.confidence_explanation or ""
    if _allow_partial:
        conf_explanation = (
            f"Análise preliminar com dados parciais "
            f"(completude {ictx.data_completeness * 100:.0f}%"
            + ("; rate limit" if _rate_limited else "")
            + f"; score {raw_score:.1f}→{conf_score:.1f}). "
            + conf_explanation
        ).strip()
    elif degraded or not fixture_located:
        conf_explanation = (
            "Fixture não localizada ou dados degradados — confiança muito baixa. "
            + conf_explanation
        ).strip()
    elif ictx.total_penalty() > 0:
        conf_explanation = (
            f"{conf_explanation} "
            f"[Inference V2: completude {ictx.data_completeness * 100:.0f}%, "
            f"penalidade −{ictx.total_penalty():.1f}, "
            f"score {raw_score:.1f}→{conf_score:.1f}]"
        ).strip()

    executive = report.executive_summary
    if _allow_partial:
        try:
            from src.core.partial_analysis import (
                build_preliminary_executive as _prelim_exec,
                strip_refusal_preamble as _strip_ref,
            )

            executive = _prelim_exec(
                hn,
                an,
                base_summary=_strip_ref(executive),
                missing_signals=list(ictx.missing_signals or []),
                available_signals=list(ictx.available_signals or []),
                data=data if isinstance(data, dict) else None,
                rate_limited=_rate_limited,
                confidence_label=conf_label,
            )
        except Exception as _prelim_exc:
            logger.warning("preliminary executive failed (%s)", _prelim_exc)
            executive = (
                f"**{hn} x {an}** — leitura preliminar (dados parciais).\n\n"
                + (executive or "")
            )
    elif is_partial or degraded:
        executive = (
            f"**Dados parciais** para {hn} x {an}. "
            f"A Aurora manteve a conversa com confiança muito baixa "
            f"(fixture não confirmada).\n\n"
            + (executive or "")
        )

    brain_meta = get_brain_meta()
    brain_meta = {
        **brain_meta,
        "inference": ictx.explainability(),
    }

    # Baseline market explanations (no live corner/card pace) ⇒ fallback flag
    used_baseline_markets = (not meth.is_live) or (not meth.has_stats) or (not meth.has_xg)

    from src.core.debug_audit import audit_from_analyze as _audit_from_analyze

    _audit_raw = _audit_from_analyze(
        fixture_located=fixture_located,
        fixture_id=fixture_id,
        is_partial=bool(is_partial),
        best_markets=best_markets,
        data_sources=data_sources,
        meth=meth,
        ictx=ictx,
        standings_home=(data.get("standings") or {}).get("home"),
        standings_away=(data.get("standings") or {}).get("away"),
        used_baseline_markets=used_baseline_markets,
    )

    # P2b Wave 1 — stamp DRS / degradation onto entities (no engine retune)
    _drs_ent = data.get("_drs") if isinstance(data, dict) else None
    _deg_ent = data.get("_degradation") if isinstance(data, dict) else None
    _nmb_ent = data.get("_nmb") if isinstance(data, dict) else None
    if not isinstance(_drs_ent, dict):
        try:
            from src.data.degradation import apply_degradation_plan as _deg_plan
            from src.data.drs import compute_drs as _compute_drs
            from src.data.nmb import build_nmb_from_analyze_payload as _build_nmb

            _nmb_obj = _build_nmb(
                data if isinstance(data, dict) else None,
                binding_quality=(
                    "PARTIAL" if (is_partial or not fixture_located) else "FULL"
                ),
                rate_limited=_rate_limited,
                user_wants_live=bool(prefer_live),
            )
            _drs_ent = _compute_drs(_nmb_obj)
            _deg_ent = _deg_plan(
                _drs_ent,
                rate_limited=_rate_limited,
                user_wants_live=bool(prefer_live),
            )
            _nmb_ent = _nmb_obj.to_dict()
        except Exception as _drs_exc:
            logger.warning("copilot: DRS stamp skipped (%s)", _drs_exc)
            _drs_ent = None
            _deg_ent = None

    result = {
        "intent":    "analyze_match",
        "entities": {
            "home": hn,
            "away": an,
            "league": league,
            "fixture_found": bool(fixture_located and not degraded),
            "fixture_quality": (
                "PARTIAL" if (is_partial or not fixture_located or degraded)
                else "VALID"
            ),
            "market_generation_enabled": True,
            "preliminary_analysis": bool(_allow_partial),
            "allow_partial_analysis": bool(_allow_partial),
            "rate_limited": bool(_rate_limited),
            "entity_invalid": False,
            **(
                {"data_richness": _drs_ent}
                if isinstance(_drs_ent, dict)
                else {}
            ),
            **(
                {"degradation": _deg_ent}
                if isinstance(_deg_ent, dict)
                else {}
            ),
            **(
                {"nmb_completion_rate": (_nmb_ent or {}).get("completion_rate")}
                if isinstance(_nmb_ent, dict)
                else {}
            ),
            **(
                {
                    # Protect preliminary executive from PIE / thinking-delay rewrite
                    "has_analysis": True,
                    "rewrite_locked": True,
                    "response_owner": "partial_analysis",
                    "final_response": True,
                }
                if _allow_partial
                else {}
            ),
        },
        "match":     report.match or f"{hn} x {an}",
        "status":    final_status,
        "is_live":   final_is_live,
        "minute":    final_minute,
        "fixture_id": int(fixture_id or 0),
        "_partial": bool(is_partial),
        "_audit": {
            **_audit_raw,
            "fixture_resolver": "analyze_pipeline",
            "market_generation_enabled": True,
            "fixture_quality": (
                "PARTIAL" if (is_partial or not fixture_located or degraded)
                else "VALID"
            ),
        },
        "fixture_status": (
            "PARTIAL" if (is_partial or not fixture_located or degraded)
            else "FOUND"
        ),
        "fixture_found": bool(fixture_located and not degraded),
        "fixture_quality": (
            "PARTIAL" if (is_partial or not fixture_located or degraded)
            else "VALID"
        ),

        "executive_summary": executive,
        "best_markets":      best_markets,

        "confidence": {
            "score":        conf_score,
            "label":        conf_label,
            "explanation":  conf_explanation,
            "data_sources": data_sources,
        },
        "risk": {
            "level":                  "High" if (is_partial or degraded) else report.risk_level,
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
        "knowledge_notes":        k_notes,
        "final_recommendation":   final_rec,

        "aurora_version": "Copilot v1.0",
        "brain":          brain_meta,
    }
    try:
        from src.communication import attach_match_card, build_match_card_from_analyze
        card = build_match_card_from_analyze(
            data,
            is_live=bool(final_is_live),
            minute=final_minute if isinstance(final_minute, int) else None,
            status_label=str(final_status) if final_status else None,
            confidence=result["confidence"],
        )
        result = attach_match_card(result, card)
    except Exception as _mc_exc:
        logger.warning("copilot: match_card skipped (%s)", _mc_exc)
    return result


async def _run_live() -> dict:
    """Live opportunities — powered by Live Intelligence Engine v1.0."""
    from src.brain import get_brain_meta
    from src.core.live_intelligence_engine import build_live_payload
    from src.routers.live import _build_live_response

    live     = await _build_live_response()
    fixtures = live.get("matches", [])   # processed format from live.py
    payload  = build_live_payload(fixtures, get_brain_meta())
    try:
        from src.communication import (
            attach_match_card,
            build_match_card_from_live_fixture,
        )
        ents = payload.get("entities") or {}
        hn = str(ents.get("live_home") or "").strip().lower()
        an = str(ents.get("live_away") or "").strip().lower()
        top_fx = None
        for fx in fixtures:
            fh = str(((fx.get("home") or {}).get("name") or "")).strip().lower()
            fa = str(((fx.get("away") or {}).get("name") or "")).strip().lower()
            if hn and an and fh == hn and fa == an:
                top_fx = fx
                break
        if top_fx is None and fixtures:
            top_fx = fixtures[0]
        if top_fx:
            card = build_match_card_from_live_fixture(
                top_fx,
                confidence=payload.get("confidence")
                if isinstance(payload.get("confidence"), dict)
                else None,
            )
            payload = attach_match_card(payload, card)
            if card:
                payload["match"] = f"{card['home']['name']} x {card['away']['name']}"
                payload["minute"] = card.get("minute")
                payload["status"] = card.get("status_label") or payload.get("status")
    except Exception as _mc_exc:
        logger.warning("copilot: live match_card skipped (%s)", _mc_exc)
    return payload


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
        f"A Aurora monitorou {total} previsões: {wins}V / {losses}D / {pending} pendentes. "
        f"Precisão: {acc_str}. ROI: {roi_str}. "
        f"Melhor mercado: {best_m}. Melhor liga: {best_l}."
    )
    final = (
        f"Desempenho {'acima' if (acc or 0) >= 55 else 'abaixo'} da meta de precisão. "
        f"{'Mantenha a disciplina.' if (acc or 0) >= 55 else 'Considere reduzir as stakes até que a precisão se recupere.'}"
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
            "explanation":  f"Baseado em {total} previsões monitoradas. Mais previsões aumentam a confiança estatística.",
            "data_sources": ["Base de dados de aprendizado"],
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
            "reasoning":             "Apenas revisão de banca — nenhuma aposta específica recomendada. Analise uma partida para obter uma recomendação de stake.",
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
        f"A Aurora resolveu {total} previsões: {wins}V / {losses}D. "
        f"Precisão atual: {f'{acc:.1f}%' if acc is not None else 'não calculada ainda'}. "
        f"A Aurora aprende continuamente — mudanças de peso requerem 20+ observações consistentes."
    )
    final = (
        "Motor de aprendizado ativo. "
        f"{'Mercados sólidos para continuar: ' + ', '.join(r.get('rule','').replace('_',' ').title() for r in working[:2]) + '.' if working else ''}"
        f"{'Mercados para atenção: ' + ', '.join(r.get('rule','').replace('_',' ').title() for r in struggling[:2]) + '.' if struggling else ''}"
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
            "explanation":  f"A confiança estatística cresce com mais previsões resolvidas. Atualmente {total} resolvidas.",
            "data_sources": ["Base de dados de aprendizado", "Motor de evolução"],
        },
        "risk": {
            "level":                  "Low" if (acc or 0) >= 55 else "High",
            "flags":                  neg[:3],
            "invalidation_conditions": [],
        },
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0, "method": "quarter-Kelly",
            "examples": {}, "no_bet": True,
            "reasoning": "Apenas revisão de aprendizado.",
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
        f"Encontrei {len(results)} item(ns) de conhecimento para \"{query}\"."
        if results else
        f"Nenhum item de conhecimento encontrado para \"{query}\"."
    )
    final = (
        f"A base de conhecimento tem {len(results)} regra(s) relevante(s) para \"{query}\". "
        "Estas são aplicadas antes de cada previsão da Aurora."
    )

    return {
        "intent":   "knowledge_search",
        "entities": {"query": query},
        "match":   None, "status": None, "is_live": False, "minute": None,

        "executive_summary": summary,
        "best_markets":      [],
        "confidence": {
            "score": 0.0, "label": "insufficient",
            "explanation": "Apenas busca de conhecimento — nenhuma análise de partida realizada.",
            "data_sources": ["Base de conhecimento"],
        },
        "risk": {
            "level": "Unknown", "flags": [],
            "invalidation_conditions": [],
        },
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0, "method": "quarter-Kelly",
            "examples": {}, "no_bet": True,
            "reasoning": "Nenhuma aposta recomendada apenas com base em busca de conhecimento.",
        },
        "positive_factors":      [],
        "negative_factors":      [],
        "historical_references": [],
        "knowledge_notes":       notes,
        "final_recommendation":  final,
        "aurora_version": "Copilot v1.0",
        "brain":          get_brain_meta(),
    }


def _run_greeting() -> dict:
    from src.brain import get_brain_meta
    from src.communication import (
        official_greeting_recommendation,
        official_greeting_summary,
    )
    return {
        "intent":   "greeting",
        "entities": {},
        "match":   None, "status": None, "is_live": False, "minute": None,
        "executive_summary": official_greeting_summary(),
        "best_markets":      [],
        "confidence": {"score": 0.0, "label": "insufficient", "explanation": "Sessão iniciada.", "data_sources": []},
        "risk": {"level": "Unknown", "flags": [], "invalidation_conditions": []},
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0, "method": "quarter-Kelly",
            "examples": {}, "no_bet": True,
            "reasoning": "",
        },
        "positive_factors":      [],
        "negative_factors":      [],
        "historical_references": [],
        "knowledge_notes": [],
        "final_recommendation": official_greeting_recommendation(),
        "aurora_version": "Copilot v1.0",
        "brain":          get_brain_meta(),
    }


def _run_help() -> dict:
    from src.brain import get_brain_meta
    return {
        "intent":   "help",
        "entities": {},
        "match":   None, "status": None, "is_live": False, "minute": None,
        "executive_summary": (
            "A Aurora suporta análise completa de partidas, oportunidades ao vivo, "
            "revisão de banca, resumo de aprendizado e busca na base de conhecimento. "
            "Linguagem natural funciona — não é preciso usar comandos exatos."
        ),
        "best_markets":      [],
        "confidence": {"score": 0.0, "label": "insufficient", "explanation": "Consulta de ajuda.", "data_sources": []},
        "risk": {"level": "Unknown", "flags": [], "invalidation_conditions": []},
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0, "method": "quarter-Kelly",
            "examples": {}, "no_bet": True,
            "reasoning": "Nenhuma aposta recomendada em consulta de ajuda.",
        },
        "positive_factors":      [],
        "negative_factors":      [],
        "historical_references": [],
        "knowledge_notes": [
            "Analisar partida → \"Analisar Palmeiras x Flamengo\"",
            "Oportunidades ao vivo → \"Melhores oportunidades ao vivo\"",
            "Revisão de banca → \"Revisar banca\"",
            "Resumo de aprendizado → \"O que a Aurora aprendeu hoje?\"",
            "Busca de conhecimento → \"O que você sabe sobre escanteios?\"",
            "Explicar análise → \"Explique a recomendação\"",
        ],
        "final_recommendation": (
            "Cada análise inclui: recomendação principal com probabilidade e valor esperado, "
            "stake pelo Critério de Kelly, fatores positivos e negativos, e condições de invalidação."
        ),
        "aurora_version": "Copilot v1.0",
        "brain":          get_brain_meta(),
    }


def _run_identity() -> dict:
    from src.brain import get_brain_meta
    from src.communication import AURORA_TAGLINE
    return {
        "intent":   "identity",
        "entities": {},
        "match":   None, "status": None, "is_live": False, "minute": None,
        "executive_summary": (
            "Eu sou a **Aurora** — analista esportiva focada em ler o jogo com calma e precisão.\n\n"
            "Observo o que realmente importa em uma partida: ritmo, pressão, oportunidades "
            "e os detalhes que costumam passar despercebidos.\n\n"
            "Se tiver um confronto em mente, analisamos juntos — sem pressa e sem ruído."
        ),
        "best_markets": [],
        "confidence": {"score": 0.0, "label": "insufficient", "explanation": "Apresentação da Aurora.", "data_sources": []},
        "risk": {"level": "Unknown", "flags": [], "invalidation_conditions": []},
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0, "method": "quarter-Kelly",
            "examples": {}, "no_bet": True,
            "reasoning": "",
        },
        "positive_factors":      [],
        "negative_factors":      [],
        "historical_references": [],
        "knowledge_notes": [],
        "final_recommendation": AURORA_TAGLINE,
        "aurora_version": "Copilot v1.0",
        "brain": get_brain_meta(),
    }


def _run_capabilities() -> dict:
    # Phase 8.4-A.9 — shared assistant_capabilities payload
    try:
        from src.conversation.assistant_capabilities import build_capabilities_payload

        return build_capabilities_payload("capacidades")
    except Exception:
        from src.brain import get_brain_meta

        return {
            "intent": "assistant_capabilities",
            "entities": {
                "assistant_capabilities": True,
                "assistant_kind": "capabilities",
            },
            "match": None,
            "status": None,
            "is_live": False,
            "minute": None,
            "executive_summary": (
                "Sou a **Aurora**, uma IA especializada em futebol. "
                "Posso analisar partidas, mercados, calendário e conversar com contexto."
            ),
            "best_markets": [],
            "confidence": {
                "score": 0.0,
                "label": "insufficient",
                "explanation": "Lista de capacidades.",
                "data_sources": [],
            },
            "risk": {"level": "Unknown", "flags": [], "invalidation_conditions": []},
            "bankroll_recommendation": {
                "recommended_stake_pct": 0.0,
                "method": "quarter-Kelly",
                "examples": {},
                "no_bet": True,
                "reasoning": "",
            },
            "positive_factors": [],
            "negative_factors": [],
            "historical_references": [],
            "knowledge_notes": [],
            "final_recommendation": "Pode pedir uma análise ou a agenda de um time.",
            "aurora_version": "Copilot v1.0",
            "brain": get_brain_meta(),
        }


def _suggest_follow_ups(intent: str, ctx: dict, payload: dict) -> list[str]:
    """
    Return 3–5 contextual follow-up suggestions in Brazilian Portuguese.

    For analyze_match: standard exploration prompts (corners, stake, risk, etc.)
    For follow_up:     complementary prompts not yet explored (inferred from
                       the executive_summary topic of the current response).
    For other intents: lightweight navigation suggestions.
    """
    last_match  = ctx.get("last_match", "")
    last_anal   = ctx.get("last_analysis") or {}

    # ── analyze_match ────────────────────────────────────────────────────────
    if intent == "analyze_match":
        return [
            "E os escanteios?",
            "Quanto apostar?",
            "Qual o risco?",
            "Existe opção mais segura?",
            "Quais fatores positivos?",
        ]

    # ── follow_up — suggest complementary topics ─────────────────────────────
    if intent == "follow_up":
        # Infer what was just covered from the executive_summary topic keyword.
        # Build a candidate pool and exclude the one that matches.
        exec_s = (payload.get("executive_summary") or "").lower()
        _pool: list[tuple[str, str]] = [
            ("escanteio",  "E os escanteios?"),
            ("gol",        "E os gols? Over/Under?"),
            ("cart",       "E os cartões?"),
            ("resultado",  "Qual o resultado mais provável?"),
            ("quanto",     "Quanto apostar?"),
            ("stake",      "Quanto apostar?"),
            ("risco",      "Qual o risco?"),
            ("segur",      "Existe opção mais segura?"),
            ("melhor",     "Quem está melhor?"),
            ("favorit",    "Quem está melhor?"),
            ("positiv",    "Quais fatores positivos?"),
            ("negativ",    "Quais fatores negativos?"),
            ("todos",      "Quais todos os mercados?"),
            ("mercado",    "Quais todos os mercados?"),
            ("ao vivo",    "Está ao vivo?"),
        ]
        seen_labels: set[str] = set()
        covered: set[str] = set()
        for kw, label in _pool:
            if kw in exec_s:
                covered.add(label)

        suggestions: list[str] = []
        # Standard pool to offer next — ordered by typical usage
        _standard = [
            "E os escanteios?",
            "E os gols? Over/Under?",
            "E os cartões?",
            "Quanto apostar?",
            "Qual o risco?",
            "Existe opção mais segura?",
            "Quais fatores positivos?",
            "Quais fatores negativos?",
            "Quem está melhor?",
            "Quais todos os mercados?",
        ]
        for s in _standard:
            if s not in covered and s not in seen_labels:
                suggestions.append(s)
                seen_labels.add(s)
            if len(suggestions) == 4:
                break
        return suggestions

    # ── live_opportunities ───────────────────────────────────────────────────
    if intent == "live_opportunities":
        live_matches = payload.get("live_matches") or []
        if live_matches:
            first = live_matches[0]
            hn = ((first.get("teams") or {}).get("home") or {}).get("name", "")
            an = ((first.get("teams") or {}).get("away") or {}).get("name", "")
            if hn and an:
                return [f"Analisar {hn} x {an}", "Revisar banca"]
        if last_match:
            return [f"Analisar {last_match}", "Revisar banca"]
        return ["Revisar banca", "O que a Aurora aprendeu?"]

    # ── bankroll_review ──────────────────────────────────────────────────────
    if intent == "bankroll_review":
        suggestions = ["O que a Aurora aprendeu?"]
        if last_match:
            suggestions.append(f"Analisar {last_match}")
        return suggestions

    # ── learning_recap ───────────────────────────────────────────────────────
    if intent == "learning_recap":
        suggestions = ["Revisar banca"]
        if last_match:
            suggestions.append(f"Analisar {last_match}")
        return suggestions

    # ── knowledge_search ─────────────────────────────────────────────────────
    if intent == "knowledge_search":
        if last_match:
            return [f"Analisar {last_match}", "Revisar banca"]
        return ["Analisar [Time A] x [Time B]", "Melhores oportunidades ao vivo"]

    # ── greeting / help / identity / capabilities / unknown / fallback ───────
    return [
        "Analisar [Time A] x [Time B]",
        "Melhores oportunidades ao vivo",
        "Revisar banca",
    ]


def _run_fallback(message: str, intent: str) -> dict:
    from src.brain import get_brain_meta
    # Try to give a useful clue based on the message content
    msg_lower = message.lower()
    if any(w in msg_lower for w in ("como", "what", "tell", "quero", "preciso")):
        tip = (
            "Parece que você quer analisar uma partida ou buscar informações. "
            "Aqui estão alguns exemplos do que posso fazer:\n\n"
        )
    else:
        tip = "Não entendi completamente. Aqui está o que posso fazer por você:\n\n"

    summary = (
        tip +
        "• **Analisar Flamengo x Palmeiras** — análise completa de uma partida\n"
        "• **Melhores oportunidades ao vivo** — partidas em andamento\n"
        "• **Revisar banca** — seu histórico e desempenho\n"
        "• **O que a Aurora aprendeu hoje?** — resumo de aprendizado\n"
        "• **O que você sabe sobre BTTS?** — busca na base de conhecimento\n\n"
        "Também entendo linguagem natural — basta perguntar normalmente."
    )
    return {
        "intent":   "unknown",
        "entities": {},
        "match":   None, "status": None, "is_live": False, "minute": None,
        "executive_summary": summary,
        "best_markets":      [],
        "confidence": {
            "score": 0.0, "label": "insufficient",
            "explanation": "Nenhuma análise executada.",
            "data_sources": [],
        },
        "risk": {
            "level": "Unknown", "flags": [],
            "invalidation_conditions": [],
        },
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0, "method": "quarter-Kelly",
            "examples": {}, "no_bet": True,
            "reasoning": "Nenhuma aposta recomendada.",
        },
        "positive_factors":      [],
        "negative_factors":      [],
        "historical_references": [],
        "knowledge_notes": [
            "Analisar partida → \"Analisar Palmeiras x Flamengo\"",
            "Ao vivo → \"Melhores oportunidades ao vivo\"",
            "Banca → \"Revisar banca\" ou \"Como está minha banca?\"",
            "Aprendizado → \"O que a Aurora aprendeu hoje?\"",
            "Conhecimento → \"O que você sabe sobre BTTS?\"",
        ],
        "final_recommendation": (
            "Digite o nome de dois times para começar: **\"Analisar [Time da Casa] x [Time Visitante]\"**"
        ),
        "aurora_version": "Copilot v1.0",
        "brain":          get_brain_meta(),
    }


# ---------------------------------------------------------------------------
# Context helper
# ---------------------------------------------------------------------------


def _save_analysis_context(ctx: dict, payload: dict, home: str, away: str) -> None:
    """
    Persist the analysis result into the conversation context dict *in-place*.

    The 'brain' and 'aurora_version' keys are excluded to keep the blob small.
    Phase 5B: also mirrors last_fixture / live snapshot fields.
    v3.7.1: shifts last → prev when the fixture changes (compare memory).
    """
    analysis = {k: v for k, v in payload.items() if k not in ("brain", "aurora_version")}
    match = payload.get("match") or f"{home} x {away}"
    try:
        from src.conversation.message_intelligence import shift_fixture_memory

        shift_fixture_memory(ctx, home, away, match if isinstance(match, str) else None)
    except Exception:
        pass
    ctx["last_home"]     = home
    ctx["last_away"]     = away
    ctx["last_match"]    = match
    ctx["last_fixture"]  = match
    ctx["last_intent"]   = "analyze_match"
    ctx["last_analysis"] = analysis
    ctx["last_market"]   = analysis.get("best_markets")
    # Keep a short recommendation fingerprint for prefer-alt intents
    fr = analysis.get("final_recommendation")
    if isinstance(fr, str) and fr.strip():
        ctx["last_recommendation"] = fr.strip()[:200]
    ctx["last_is_live"]  = bool(payload.get("is_live"))
    ctx["last_minute"]   = payload.get("minute")
    conf = analysis.get("confidence") if isinstance(analysis.get("confidence"), dict) else {}
    try:
        ctx["last_confidence"] = float(conf.get("score") or 0.0)
    except (TypeError, ValueError):
        ctx["last_confidence"] = 0.0
    ctx["last_entities"] = [{"home": home, "away": away}]
    if payload.get("is_live"):
        from datetime import datetime, timezone
        ctx["last_live_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    from datetime import datetime, timezone
    ctx["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # v3.7.5 — sync Conversation State (active fixture/market); fail-open
    try:
        from src.conversation.conversation_state import apply_after_analysis

        apply_after_analysis(
            ctx,
            home,
            away,
            match if isinstance(match, str) else None,
            analysis,
        )
    except Exception:
        pass


def _fixtures_equivalent(
    home: str,
    away: str,
    *,
    last_match: str = "",
    last_home: str = "",
    last_away: str = "",
) -> bool:
    """Compat wrapper → followup_guard.fixtures_equivalent."""
    from src.core.followup_guard import fixtures_equivalent

    return fixtures_equivalent(
        home,
        away,
        last_match=last_match,
        last_home=last_home,
        last_away=last_away,
    )


def _parse_match_card_model(raw: object) -> MatchCard | None:
    """Safely coerce payload match_card into the response model."""
    if not isinstance(raw, dict):
        return None
    try:
        from src.communication import normalize_match_card

        cleaned = normalize_match_card(raw)
        if not cleaned:
            return None
        return MatchCard(**cleaned)
    except Exception as exc:
        logger.warning("copilot: match_card response coerce skipped (%s)", exc)
        return None


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
    1. Detects intent automatically via the Natural Language Router
    2. Calls all required internal engines
    3. Merges outputs into one structured response

    **Supported intents (automatic detection):**
    | Example Input | Intent |
    |---|---|
    | *"Analisar Palmeiras x Flamengo"* | `analyze_match` |
    | *"PSG contra Bayern"* | `analyze_match` |
    | *"Man City x Arsenal"* | `analyze_match` |
    | *"Melhores oportunidades ao vivo"* | `live_opportunities` |
    | *"Como está minha banca?"* | `bankroll_review` |
    | *"O que a Aurora aprendeu?"* | `learning_recap` |
    | *"O que você sabe sobre BTTS?"* | `knowledge_search` |
    | *"Quem é você?"* | `identity` |
    | *"O que você faz?"* | `capabilities` |

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
    - `routing_confidence` — NL router confidence score (0.0–1.0)

    All numerical fields are machine-readable. All string fields are human-readable.
    Designed for direct integration with GPT-4, Claude, Gemini, and custom agents.
    """
    from src.brain import get_brain_meta
    from src.chat_db import (
        create_session      as _db_create,
        save_message        as _db_save_msg,
        update_session_context    as _db_upd_session,
    )
    from src.conversation import conversation_manager
    from src.core.conversation_engine import (
        detect                  as _conv_detect,
        extract_user_profile_info as _extract_profile,
        respond                 as _conv_respond,
    )
    from src.core.follow_up_engine import (
        is_followup  as _is_followup,
        resolve      as _fu_resolve,
    )
    from src.core.nl_router import route as _nl_route

    session_id = body.session_id or secrets.token_hex(8)
    _force_refresh = bool(getattr(body, "force_refresh", False))
    from src.ops import cost_protection as _ecpm

    _ecpm_tokens = _ecpm.begin_request(session_id, force_refresh=_force_refresh)
    try:
        return await _copilot_inner(body, session_id=session_id, force_refresh=_force_refresh)
    finally:
        _ecpm.end_request(_ecpm_tokens)


async def _copilot_inner(
    body: CopilotRequest,
    *,
    session_id: str,
    force_refresh: bool = False,
) -> CopilotResponse:
    """Copilot body (runs inside Emergency Cost Protection request scope)."""
    from src.brain import get_brain_meta
    from src.chat_db import (
        create_session      as _db_create,
        save_message        as _db_save_msg,
        update_session_context    as _db_upd_session,
    )
    from src.conversation import conversation_manager
    from src.core.conversation_engine import (
        detect                  as _conv_detect,
        extract_user_profile_info as _extract_profile,
        respond                 as _conv_respond,
    )
    from src.core.follow_up_engine import (
        is_followup  as _is_followup,
        resolve      as _fu_resolve,
    )
    from src.core.nl_router import route as _nl_route

    message = body.message.strip()
    _conv_prefs: dict = {}
    try:
        if isinstance(getattr(body, "conversation_preferences", None), dict):
            _conv_prefs = dict(body.conversation_preferences or {})
    except Exception:
        _conv_prefs = {}
    _about_you_in: dict = {}
    try:
        if isinstance(getattr(body, "about_you", None), dict):
            _about_you_in = dict(body.about_you or {})
    except Exception:
        _about_you_in = {}

    from src.core.debug_audit import debug_mode_enabled as _debug_mode_enabled

    debug_mode = _debug_mode_enabled(getattr(body, "debug", False), message=message)

    # ── Session management ────────────────────────────────────────────────
    # session_id comes from ECPM wrapper (stable daily-budget key)
    _db_create(session_id)
    # Phase 5B: memory cache first, SQLite fallback
    ctx   = conversation_manager.get(session_id) or {}
    try:
        ctx["_conversation_preferences"] = _conv_prefs
    except Exception:
        pass
    # v4.7 — merge About You into ctx (never touches betting user_profile)
    try:
        if _about_you_in:
            from src.conversation.user_profile_memory import save_profile as _v47_save_about

            _v47_save_about(ctx, _about_you_in)
    except Exception as _about_exc:
        logger.warning("copilot: about_you merge skipped (%s)", _about_exc)
    brain = get_brain_meta()

    request_id = secrets.token_hex(4)
    intent: str = "unknown"
    entities: dict = {}
    routing_confidence = 0.0
    payload: dict | None = None
    skipped_nl = False
    # Preserve raw user phrasing for Human Inference (recovery may rewrite)
    try:
        ctx["raw_user_message"] = message
    except Exception:
        pass

    # ── PATCH-002A: Sports Language Layer (BEFORE routing / memory / GA) ──
    try:
        from src.conversation.sports_language import apply_sports_language_layer

        _sll = apply_sports_language_layer(message, ctx)
        if _sll.applied and _sll.normalized_text:
            message = _sll.normalized_text
    except Exception as _sll_exc:
        logger.warning("copilot: SLL skipped (%s)", _sll_exc)

    # TOPIC-BOUNDARY-002 — Episode boundary V2 BEFORE CSL / sport-intent rewrite.
    # Uses raw (post-SLL) message so subject rotation beats fixture reuse.
    # Flag OFF by default. Does not redesign boundary rules — only order + cleanup.
    try:
        from src.conversation.topic_boundary_v2 import apply_topic_boundary_v2

        apply_topic_boundary_v2(message, ctx)
    except Exception as _tbv2_exc:
        logger.warning("copilot: topic boundary v2 skipped (%s)", _tbv2_exc)

    # ── CSL-001: Conversation State Layer façade (after SLL + boundary) ──
    # Stores slots + may contextualize bare follow-ups. Does not replace engines.
    try:
        from src.conversation.conversation_state_layer import apply_csl_resolve

        message = apply_csl_resolve(message, ctx)
    except Exception as _csl_exc:
        logger.warning("copilot: CSL skipped (%s)", _csl_exc)

    # ── INTENT-001: Semantic Sports Intent Layer (after CSL) ──
    # Classifies sport intents and routes follow-ups to specialized skills.
    try:
        from src.conversation.sport_intent_layer import apply_sport_intent_resolve

        message = apply_sport_intent_resolve(message, ctx)
    except Exception as _sil_exc:
        logger.warning("copilot: sport intent layer skipped (%s)", _sil_exc)

    # LANGGRAPH-STATE-POC-001 Phase 2 — SHADOW MODE only (log-only OLD vs NEW).
    # Gated by ENABLE_LANGGRAPH_STATE_SHADOW (default OFF). Independent of
    # ENABLE_LANGGRAPH_STATE (production write path stays OFF). Fail-open;
    # must not change message, payload, response, or live ctx subject writers.
    try:
        from src.conversation.langgraph_state_adapter import maybe_shadow_compare

        maybe_shadow_compare(message, ctx)
    except Exception as _lg_shadow_exc:
        logger.warning("copilot: langgraph shadow skipped (%s)", _lg_shadow_exc)

    # Per-turn flags (must not leak across turns in the same session).
    # Do NOT pop episode_boundary / subject_guard — set earlier this turn by V2.
    try:
        ctx.pop("ownership_stability_block_ga", None)
        ctx.pop("sport_continuity_block_ga", None)
        ctx.pop("sport_continuity_block_nc", None)
        ctx.pop("ambiguous_context_block_ga", None)
        ctx.pop("fiction_context_hard_reset", None)
    except Exception:
        pass

    # Phase 8.2-C — short memory pronoun resolve BEFORE MasterIntent
    # ("o que achou dele?" → last_team / last_fixture; avoids GA trap)
    try:
        from src.conversation.short_conversation_memory import (
            apply_short_memory_resolve as _sm_resolve,
        )

        message = _sm_resolve(message, ctx)
    except Exception as _sm_exc:
        logger.warning("copilot: short memory resolve skipped (%s)", _sm_exc)

    # Phase 8.4-A.22 — Fiction & Hard Context Jump Guard (reset only, no claim)
    try:
        from src.conversation.fiction_context_jump_guard import (
            process_turn_start as _fcj_start,
        )

        _fcj_start(message, ctx)
    except Exception as _fcj_exc:
        logger.warning("copilot: fiction/context-jump guard skipped (%s)", _fcj_exc)

    # P1-B — Fiction early claim only (before sport pipeline analyzes fictional pairs).
    # Do NOT early-claim CLARIFICATION/UNKNOWN — that steals sport continuity.
    try:
        if payload is None:
            from src.conversation.dialog_mode import (
                is_fiction_message as _dm_fic,
                try_dialog_mode_claim as _dm_early,
            )

            if _dm_fic(message):
                _dmp = _dm_early(message, ctx)
                if isinstance(_dmp, dict) and str(
                    (_dmp.get("entities") or {}).get("dialog_mode") or ""
                ).upper() == "FICTION":
                    payload = _dmp
                    intent = str(payload.get("intent") or "clarification")
                    entities = dict(payload.get("entities") or {})
                    routing_confidence = 0.97
                    skipped_nl = True
                    try:
                        ctx["sport_pipeline_blocked"] = True
                        ctx["ambiguous_context_block_ga"] = True
                    except Exception:
                        pass
                    logger.warning(
                        "[AUDIT] DialogMode: EARLY FICTION claim owner=%s",
                        entities.get("response_owner"),
                    )
    except Exception as _dm_early_exc:
        logger.warning("copilot: dialog_mode early claim skipped (%s)", _dm_early_exc)

    # P1-B — after fiction wipe, dialog_mode owns short FU / underspec recovery
    # (A.20 remains frozen; we only claim when post_fiction_release is active).
    try:
        if payload is None:
            from src.conversation.dialog_mode import (
                CTX_KEY as _dm_ctx_key,
                try_dialog_mode_claim as _dm_post,
            )

            _dm_blob = ctx.get(_dm_ctx_key) if isinstance(ctx, dict) else None
            if isinstance(_dm_blob, dict) and _dm_blob.get("post_fiction_release"):
                _dmp = _dm_post(message, ctx)
                if isinstance(_dmp, dict) and str(
                    (_dmp.get("entities") or {}).get("dialog_mode") or ""
                ).upper() in {
                    "CLARIFICATION",
                    "UNKNOWN",
                    "REPAIR",
                    "FICTION",
                    "IDENTITY",
                    "SMALL_TALK",
                }:
                    payload = _dmp
                    intent = str(payload.get("intent") or "clarification")
                    entities = dict(payload.get("entities") or {})
                    entities["post_fiction_clarify"] = True
                    entities["context_expected_waived"] = True
                    payload["entities"] = entities
                    routing_confidence = 0.97
                    skipped_nl = True
                    try:
                        ctx["sport_pipeline_blocked"] = True
                        ctx["ambiguous_context_block_ga"] = True
                    except Exception:
                        pass
                    logger.warning(
                        "[AUDIT] DialogMode: POST-FICTION claim mode=%s",
                        entities.get("dialog_mode"),
                    )
    except Exception as _dm_post_exc:
        logger.warning("copilot: dialog_mode post-fiction claim skipped (%s)", _dm_post_exc)

    # Phase 8.4-A.20 — Ambiguous Context Priming Guard
    # (detect jump → drop continuity; ambiguous opener → clarify; block bootstrap)
    try:
        if payload is None:
            from src.conversation.ambiguous_context_guard import (
                try_ambiguous_clarification_claim as _acg_try,
            )

            _acg = _acg_try(message, ctx)
            if isinstance(_acg, dict):
                payload = _acg
                intent = str(payload.get("intent") or "clarification")
                entities = dict(payload.get("entities") or {})
                # P1-B — if fiction release still sticky, align eval stamps (no A.20 edit)
                try:
                    from src.conversation.dialog_mode import CTX_KEY as _dm_k

                    _b = ctx.get(_dm_k) if isinstance(ctx, dict) else None
                    if isinstance(_b, dict) and _b.get("post_fiction_release"):
                        entities["post_fiction_clarify"] = True
                        entities["context_expected_waived"] = True
                        entities["p1_dialog_mode"] = True
                except Exception:
                    pass
                payload["entities"] = entities
                routing_confidence = 0.96
                skipped_nl = True
                try:
                    ctx["ambiguous_context_block_ga"] = True
                    ctx["sport_pipeline_blocked"] = True
                except Exception:
                    pass
                logger.warning(
                    "[AUDIT] AmbiguousContext: EARLY clarify before continuity/GA"
                )
    except Exception as _acg_exc:
        logger.warning("copilot: ambiguous context guard skipped (%s)", _acg_exc)

    # P2.5 — Entity Resolver v2 (SRF + ambiguity + pronoun). CLARIFY only;
    # ASSUME updates SRF and never steals the sport pipeline.
    # Must run BEFORE continuity / A.18 so side-pronoun clarify wins.
    try:
        from src.core.entity_resolver_v2 import (
            build_clarify_payload as _ev2_clarify_payload,
            resolve_referent as _ev2_resolve,
        )

        _ev2_bind = _ev2_resolve(message, ctx)
        if isinstance(ctx, dict):
            ctx["entity_v2_last_bind"] = _ev2_bind.to_entities()
        # Early-claim only for high-value clarifies (never steal short pronoun FUs)
        _ev2_claim_reasons = {
            "ambiguous_team",
            "ambiguous_club_on_switch",
            "side_pronoun_two_plausible",
            "opponent_deixis_team_only",
            "jogo_needs_fixture",
            "post_fiction_needs_new_anchor",
            "pronoun_no_frame",
            "plural_no_frame",
            # short_fu_no_frame / markets_need_fixture: stamp only — do not
            # early-claim (avoids stealing team research / A.18 happy paths)
        }
        if (
            payload is None
            and _ev2_bind.action == "CLARIFY"
            and (_ev2_bind.clarify_reason or "") in _ev2_claim_reasons
        ):
            payload = _ev2_clarify_payload(_ev2_bind, message)
            intent = str(payload.get("intent") or "clarification")
            entities = dict(payload.get("entities") or {})
            routing_confidence = 0.97
            skipped_nl = True
            try:
                ctx["sport_pipeline_blocked"] = True
                ctx["ambiguous_context_block_ga"] = True
            except Exception:
                pass
            logger.warning(
                "[AUDIT] EntityV2: CLARIFY reason=%s amb=%.2f",
                _ev2_bind.clarify_reason,
                float(_ev2_bind.ambiguity_score or 0.0),
            )
    except Exception as _ev2_exc:
        logger.warning("copilot: entity_resolver_v2 skipped (%s)", _ev2_exc)

    # Phase 8.3-B / 8.4-A.8 — continuity resolve (message rewrite) always.
    # RESPONSE-SELECTOR-001: when enabled, collect generators → select once
    # instead of first-wins race. OS / SCG remain as fallback generators.
    try:
        from src.conversation.conversation_continuity import (
            apply_continuity_resolve as _cont_resolve,
        )

        message = _cont_resolve(message, ctx)
    except Exception as _cont_exc:
        logger.warning("copilot: continuity resolve skipped (%s)", _cont_exc)

    _use_response_selector = False
    try:
        from src.conversation.response_selector import (
            response_selector_enabled as _rs_enabled,
            try_select_early_response as _rs_select,
        )

        _use_response_selector = bool(_rs_enabled())
        if payload is None and _use_response_selector:
            from src.brain import get_brain_meta as _gbm_rs

            _rs_payload = _rs_select(message, ctx, brain=_gbm_rs())
            if isinstance(_rs_payload, dict):
                payload = _rs_payload
                intent = str(payload.get("intent") or "follow_up")
                entities = dict(payload.get("entities") or {})
                routing_confidence = float(
                    entities.get("response_selector_confidence") or 0.92
                )
                skipped_nl = True
                try:
                    ctx["sport_pipeline_blocked"] = False
                    if entities.get("response_selector_fallback") or entities.get(
                        "sport_continuity_guard"
                    ):
                        ctx["sport_continuity_block_ga"] = True
                except Exception:
                    pass
                logger.warning(
                    "[AUDIT] ResponseSelector: EARLY select owner=%s priority=%s "
                    "fallback=%s",
                    entities.get("response_selector_owner")
                    or entities.get("response_owner"),
                    entities.get("response_selector_priority"),
                    entities.get("response_selector_fallback"),
                )
    except Exception as _rs_exc:
        logger.warning("copilot: response selector skipped (%s)", _rs_exc)
        _use_response_selector = False

    # Legacy first-wins race (flag off or selector miss with empty pool)
    if not _use_response_selector:
        try:
            from src.conversation.conversation_continuity import (
                is_active_sport_followup as _cont_active,
                try_contextual_short_followup as _cont_fu_early,
            )

            if payload is None and _cont_active(ctx, message):
                from src.brain import get_brain_meta as _gbm_cont_early

                _early_fu = _cont_fu_early(message, ctx, brain=_gbm_cont_early())
                if isinstance(_early_fu, dict):
                    payload = _early_fu
                    intent = str(payload.get("intent") or "follow_up")
                    entities = dict(payload.get("entities") or {})
                    routing_confidence = 0.94
                    skipped_nl = True
                    logger.warning(
                        "[AUDIT] ContinuityFollowUp: EARLY claim before MasterIntent "
                        "kind=%s team=%r",
                        entities.get("continuity_kind"),
                        entities.get("followup_resolved_team"),
                    )
        except Exception as _cont_exc:
            logger.warning("copilot: continuity claim skipped (%s)", _cont_exc)

        # Phase 8.4-A.10 — Pronoun Continuity BEFORE GA / fallback
        try:
            if payload is None:
                from src.brain import get_brain_meta as _gbm_pronoun
                from src.conversation.pronoun_continuity import (
                    try_pronoun_continuity as _pronoun_try,
                )

                _pronoun_payload = _pronoun_try(
                    message, ctx, brain=_gbm_pronoun()
                )
                if isinstance(_pronoun_payload, dict):
                    payload = _pronoun_payload
                    intent = str(payload.get("intent") or "follow_up")
                    entities = dict(payload.get("entities") or {})
                    routing_confidence = 0.93
                    skipped_nl = True
                    try:
                        ctx["sport_pipeline_blocked"] = False
                    except Exception:
                        pass
                    logger.warning(
                        "[AUDIT] PronounContinuity: EARLY claim before MasterIntent "
                        "value=%s entity=%r fixture=%r",
                        entities.get("pronoun_value"),
                        entities.get("pronoun_entity"),
                        entities.get("pronoun_fixture"),
                    )
        except Exception as _pronoun_exc:
            logger.warning("copilot: pronoun continuity skipped (%s)", _pronoun_exc)

        # Phase 8.4-A.11 — Advanced Football Continuity BEFORE GA / fallback
        try:
            if payload is None:
                from src.brain import get_brain_meta as _gbm_adv
                from src.conversation.advanced_football_continuity import (
                    try_advanced_football_continuity as _adv_try,
                )

                _adv_payload = _adv_try(message, ctx, brain=_gbm_adv())
                if isinstance(_adv_payload, dict):
                    payload = _adv_payload
                    intent = str(payload.get("intent") or "follow_up")
                    entities = dict(payload.get("entities") or {})
                    routing_confidence = 0.92
                    skipped_nl = True
                    try:
                        ctx["sport_pipeline_blocked"] = False
                    except Exception:
                        pass
                    logger.warning(
                        "[AUDIT] AdvancedFootball: EARLY claim before MasterIntent "
                        "term=%s fixture=%r reused=%s",
                        entities.get("advanced_term"),
                        entities.get("followup_resolved_fixture")
                        or entities.get("pronoun_fixture"),
                        entities.get("advanced_fixture_reused"),
                    )
        except Exception as _adv_exc:
            logger.warning(
                "copilot: advanced football continuity skipped (%s)", _adv_exc
            )

        # Phase 8.4-A.18 — Sport Continuity Guard
        try:
            if payload is None:
                from src.brain import get_brain_meta as _gbm_scg
                from src.conversation.sport_continuity_guard import (
                    try_sport_continuity_claim as _scg_try,
                )

                _scg = _scg_try(message, ctx, brain=_gbm_scg())
                if isinstance(_scg, dict):
                    payload = _scg
                    intent = str(payload.get("intent") or "follow_up")
                    entities = dict(payload.get("entities") or {})
                    routing_confidence = 0.935
                    skipped_nl = True
                    try:
                        ctx["sport_pipeline_blocked"] = False
                        ctx["sport_continuity_block_ga"] = True
                    except Exception:
                        pass
                    logger.warning(
                        "[AUDIT] SportContinuityGuard: EARLY claim owner=%s fixture=%r",
                        entities.get("response_owner"),
                        entities.get("followup_resolved_fixture")
                        or entities.get("sport_anchor_fixture"),
                    )
        except Exception as _scg_exc:
            logger.warning("copilot: sport continuity guard skipped (%s)", _scg_exc)

        # Phase 8.4-A.15 — Ownership Stability
        try:
            if payload is None:
                from src.brain import get_brain_meta as _gbm_own
                from src.conversation.ownership_stability import (
                    try_ownership_stability_claim as _own_stab,
                )

                _stab = _own_stab(message, ctx, brain=_gbm_own())
                if isinstance(_stab, dict):
                    payload = _stab
                    intent = str(payload.get("intent") or "follow_up")
                    entities = dict(payload.get("entities") or {})
                    routing_confidence = 0.91
                    skipped_nl = True
                    try:
                        ctx["sport_pipeline_blocked"] = False
                    except Exception:
                        pass
                    logger.warning(
                        "[AUDIT] OwnershipStability: EARLY claim guard=%s",
                        entities.get("ownership_stability_guard"),
                    )
        except Exception as _own_stab_exc:
            logger.warning("copilot: ownership stability skipped (%s)", _own_stab_exc)

    # Pipeline order (Human Understanding):
    #   MasterIntent → (non-sport short-circuit)
    #   → Recovery → DeepThinking → Focus → HumanInference
    #   → WEB(gather) → Emotional/Profile/HPL
    #   → Natural/Fallback → engines… → Review → ThinkingDelay → Final

    # ── 0. Master Intent Router — BEFORE any sport pipeline ───────────────
    _master = None
    _sport_ok = True
    try:
        from src.conversation.general_assistant import try_general_assistant as _ga_try
        from src.conversation.master_intent_router import (
            apply_master_intent as _mi_apply,
            sport_pipeline_allowed as _mi_sport_ok,
        )
        from src.conversation.natural_response_filter import (
            filter_or_regenerate as _nrf_filter,
        )

        def _continuity_or_owner_claimed(p: dict | None) -> bool:
            if not isinstance(p, dict):
                return False
            e = p.get("entities") or {}
            return bool(
                e.get("continuity_followup")
                or e.get("followup_before_fallback")
                or e.get("pronoun_resolved")
                or e.get("pronoun_continuity")
                or e.get("advanced_fixture_reused")
                or e.get("advanced_football_continuity")
                or e.get("ownership_stability")
                or e.get("owner_lock")
                or e.get("sport_continuity_guard")
                or e.get("ambiguous_context_guard")
                or e.get("clarification_mode")
                or e.get("response_selector")
                or e.get("sport_intent_authored")
            )

        # Continuity / pronoun / advanced / owner-lock claimed → skip GA steal
        if _continuity_or_owner_claimed(payload):
            _sport_ok = True
            try:
                ctx["sport_pipeline_blocked"] = False
            except Exception:
                pass
            logger.warning(
                "[AUDIT] ContinuityFollowUp: MasterIntent/GA short-circuit bypassed"
            )
            _master = None
        else:
            _master = _mi_apply(message, ctx)
            _sport_ok = _mi_sport_ok(ctx)
            # 8.4-A.18 / 8.4-A.15 — block GA steal on sport continuity / owner lock
            try:
                from src.conversation.ownership_stability import should_block_ga as _block_ga
                from src.conversation.sport_continuity_guard import (
                    should_block_ga_sport as _block_ga_sport,
                    try_sport_continuity_claim as _scg_force,
                )

                _ga_sport_block = _block_ga_sport(ctx, message)
                if _ga_sport_block or _block_ga(
                    ctx,
                    message,
                    master_confidence=float(
                        getattr(_master, "confidence", 0) or 0
                    )
                    if _master
                    else None,
                ):
                    # Prefer sport continuity claim (8.4-A.18); fall back to OS force.
                    try:
                        from src.brain import get_brain_meta as _gbm_hold
                        from src.conversation.ownership_stability import (
                            force_owner_claim_after_ga_block as _force_claim,
                            bump as _own_bump,
                        )

                        _forced = None
                        if _ga_sport_block:
                            _forced = _scg_force(
                                message, ctx, brain=_gbm_hold()
                            )
                        if not isinstance(_forced, dict):
                            _forced = _force_claim(
                                message,
                                ctx,
                                brain=_gbm_hold(),
                                existing_payload=payload
                                if isinstance(payload, dict)
                                else None,
                            )
                        if isinstance(_forced, dict):
                            payload = _forced
                            intent = str(payload.get("intent") or "follow_up")
                            entities = dict(payload.get("entities") or {})
                            routing_confidence = 0.9
                            skipped_nl = True
                            _sport_ok = True
                            _master = None
                            try:
                                ctx["sport_pipeline_blocked"] = False
                                if entities.get("sport_continuity_guard"):
                                    ctx["sport_continuity_block_ga"] = True
                                else:
                                    ctx["ownership_stability_block_ga"] = True
                            except Exception:
                                pass
                            logger.warning(
                                "[AUDIT] Sport/OS: GA blocked claim owner=%s "
                                "sport_guard=%s",
                                entities.get("response_owner"),
                                bool(entities.get("sport_continuity_guard")),
                            )
                        else:
                            _own_bump(ctx, "ga_block_without_claim")
                            try:
                                ctx.pop("ownership_stability_block_ga", None)
                            except Exception:
                                pass
                            logger.warning(
                                "[AUDIT] OwnershipStability: block skipped after "
                                "release (no sticky hold)"
                            )
                    except Exception as _force_exc:
                        logger.warning(
                            "copilot: forced owner claim failed (%s)", _force_exc
                        )
            except Exception as _block_exc:
                logger.warning("copilot: owner steal block skipped (%s)", _block_exc)
        try:
            from src.conversation.pipeline_trace import trace as _ptrace

            _ptrace(
                "INTENT",
                intent=(_master.intent if _master else None),
                sport_ok=_sport_ok,
                allow_sport=(_master.allow_sport_pipeline if _master else None),
                confidence=(_master.confidence if _master else None),
            )
        except Exception:
            pass
        _ga = None
        _cont_claimed = _continuity_or_owner_claimed(payload) or bool(
            ctx.get("ownership_stability_block_ga")
            or ctx.get("sport_continuity_block_ga")
            or ctx.get("ambiguous_context_block_ga")
        )
        # Phase 8.2-A — conversation repair BEFORE GeneralAssistant (no Entendi trap)
        # Phase 8.4-A.8 / 8.4-A.15 — never let repair/GA/HCE steal continuity / owner-lock
        if not _cont_claimed:
            try:
                from src.conversation.conversation_repair import (
                    try_conversation_repair as _repair_try,
                )

                _repair = _repair_try(message, ctx)
                if _repair:
                    _ga = _repair
                    _sport_ok = False
                    try:
                        ctx["sport_pipeline_blocked"] = True
                    except Exception:
                        pass
                    logger.warning("[AUDIT] ConversationRepair: early short-circuit")
            except Exception as _repair_exc:
                logger.warning("copilot: conversation repair skipped (%s)", _repair_exc)

            if _ga is None and _master and not _master.allow_sport_pipeline:
                _ga = _ga_try(message, _master.intent, ctx)
                if _ga:
                    _txt = str(_ga.get("executive_summary") or "")
                    _txt = _nrf_filter(
                        _txt,
                        master_intent=_master.intent,
                        ctx=ctx,
                        regenerate=_txt,
                    )
                    _ga["executive_summary"] = _txt
                    _ga["final_recommendation"] = _txt
                    try:
                        from src.conversation.pipeline_trace import trace as _ptrace

                        _ptrace(
                            "ENGINE",
                            engine="general_assistant",
                            kind=(_ga.get("entities") or {}).get("assistant_kind"),
                            fallback=False,
                        )
                    except Exception:
                        pass
            # Human Conversation Engine — continuity / short answers / meta / memory
            # May override weak GA; may also soft-handle sport ("quero analisar um jogo").
            try:
                from src.conversation.human_conversation_engine import (
                    try_human_conversation as _hce_try,
                )

                _hce = _hce_try(
                    message,
                    ctx,
                    master_intent=(_master.intent if _master else None),
                    existing_payload=_ga,
                    prefs=_conv_prefs,
                )
                if _hce:
                    payload = _hce
                    intent = str(payload.get("intent") or "conversation_assist")
                    entities = dict(payload.get("entities") or {})
                    routing_confidence = 0.94
                    skipped_nl = True
                    # Non-sport HCE must keep sport pipeline blocked
                    if entities.get("hce_kind") in {
                        "await_fixture",
                        "short_await_fixture",
                        "meta_question",
                        "memory_bankroll_saved",
                        "memory_bankroll_pending",
                        "memory_stake_guidance",
                        "short_loose",
                        "soft_followup",
                        "conversation_repair",
                    }:
                        _sport_ok = False
                        try:
                            ctx["sport_pipeline_blocked"] = True
                        except Exception:
                            pass
                    logger.warning(
                        "[AUDIT] HCE: kind=%s master=%s",
                        entities.get("hce_kind"),
                        (_master.intent if _master else None),
                    )
                    try:
                        from src.conversation.pipeline_trace import trace as _ptrace

                        _ptrace(
                            "ENGINE",
                            engine="human_conversation",
                            kind=entities.get("hce_kind"),
                            fallback=False,
                        )
                    except Exception:
                        pass
                elif _ga:
                    payload = _ga
                    intent = str(payload.get("intent") or "general_chat")
                    entities = dict(payload.get("entities") or {})
                    routing_confidence = float(_master.confidence or 0.95)
                    skipped_nl = True
                    if entities.get("conversation_repair"):
                        logger.warning(
                            "[AUDIT] ConversationRepair: master=%s kind=%s",
                            _master.intent if _master else None,
                            entities.get("assistant_kind"),
                        )
                    else:
                        logger.warning(
                            "[AUDIT] GeneralAssistant: master=%s kind=%s",
                            _master.intent,
                            entities.get("assistant_kind"),
                        )
            except Exception as _hce_exc:
                logger.warning("copilot: HCE skipped (%s)", _hce_exc)
                if _ga and payload is None:
                    payload = _ga
                    intent = str(payload.get("intent") or "general_chat")
                    entities = dict(payload.get("entities") or {})
                    routing_confidence = float(
                        (_master.confidence if _master else 0.9) or 0.9
                    )
                    skipped_nl = True
        else:
            logger.warning(
                "[AUDIT] ContinuityFollowUp: skipped repair/GA/HCE — already claimed"
            )

        # Natural Response Engine V2 — expression (ACK / farewell / warmth / variability)
        # Does not change understanding; only how social turns sound.
        try:
            from src.conversation.natural_response_engine import (
                apply_natural_response as _nre_apply,
                try_natural_social_payload as _nre_direct,
            )

            if payload is None:
                _nre = _nre_direct(message, ctx)
                if _nre:
                    payload = _nre
                    intent = "small_talk"
                    entities = dict(payload.get("entities") or {})
                    routing_confidence = 0.93
                    skipped_nl = True
                    _sport_ok = False
                    try:
                        ctx["sport_pipeline_blocked"] = True
                    except Exception:
                        pass
            elif payload is not None:
                payload = _nre_apply(message, payload, ctx) or payload
                intent = str(payload.get("intent") or intent)
                entities = dict(payload.get("entities") or {})
        except Exception as _nre_exc:
            logger.warning("copilot: NRE v2 skipped (%s)", _nre_exc)

        # Phase 7.4 — ONE TURN = ONE OWNER (lock resolved early replies)
        try:
            from src.conversation.turn_ownership import finalize_early_ownership as _own_fin

            if payload is not None:
                payload = _own_fin(payload) or payload
                entities = dict(payload.get("entities") or {})
                intent = str(payload.get("intent") or intent)
                try:
                    from src.conversation.pipeline_trace import (
                        snapshot_payload as _psnap,
                        trace as _ptrace,
                    )

                    _snap = _psnap(payload)
                    _ptrace(
                        "ENTITIES",
                        intent=_snap.get("intent"),
                        owner=_snap.get("owner"),
                        locked=_snap.get("locked"),
                        hce_kind=_snap.get("hce_kind"),
                    )
                    _ptrace(
                        "PLANNER",
                        sport_ok=_sport_ok,
                        skipped_nl=skipped_nl,
                        owner=_snap.get("owner"),
                        locked=_snap.get("locked"),
                    )
                except Exception:
                    pass
        except Exception as _own_exc:
            logger.warning("copilot: ownership finalize skipped (%s)", _own_exc)
    except Exception as _mi_exc:
        logger.warning("copilot: master intent skipped (%s)", _mi_exc)
        _sport_ok = True

    # ── 0a-1. Context Recovery (messy users → inferred intent) ────────────
    # Non-sport: NEVER enter recovery / focus / deep-thinking sport path.
    if _sport_ok and payload is None:
      try:
        from src.conversation.context_recovery import (
            apply_recovery_to_message as _v48_recover,
            recover_context as _v48_recover_full,
        )
        try:
            from src.conversation.pipeline_trace import trace as _ptrace

            _ptrace("RECOVERY", entered=True, sport_ok=_sport_ok)
        except Exception:
            pass

        _rec = _v48_recover_full(message, ctx)
        message = _v48_recover(message, ctx, min_confidence=0.7)
        try:
            from src.conversation.response_review import (
                run_deep_thinking_engine as _v48_think,
            )

            _v48_think(message, ctx, recovery=_rec.to_dict())
        except Exception:
            pass
        # ── Reference Resolver (Final Stabilization) ─────────────────────
        try:
            from src.conversation.conversation_focus import (
                apply_reference_resolution as _fc_resolve,
                confidence_clarification_payload as _fc_clarify,
            )

            _before = message
            message = _fc_resolve(message, ctx)
            # Re-think if rewritten
            if message != _before:
                try:
                    from src.conversation.response_review import (
                        run_deep_thinking_engine as _v48_think2,
                    )

                    _v48_think2(
                        message,
                        ctx,
                        recovery=(_rec.to_dict() if _rec else None),
                    )
                except Exception:
                    pass
            if ctx.get("pending_clarification") and payload is None:
                payload = _fc_clarify(
                    str(ctx.pop("pending_clarification")), _conv_prefs
                )
                intent = "conversation_assist"
                entities = dict(payload.get("entities") or {})
                routing_confidence = 0.9
                skipped_nl = True
                logger.warning(
                    "[AUDIT] ConfidenceResolver: clarification short-circuit"
                )
        except Exception as _fc_exc:
            logger.warning("copilot: reference resolver skipped (%s)", _fc_exc)
        # ── Topic Boundary BEFORE focus update (use prior focus) ──────────
        try:
            from src.conversation.brain_authority import (
                apply_topic_boundary as _ba_clear,
                should_clear_topic_boundary as _ba_should,
            )

            if payload is None:
                _clear, _why = _ba_should(
                    message, ctx, recovery=(_rec.to_dict() if _rec else None)
                )
                if _clear:
                    _ba_clear(ctx, reason=_why)
                    try:
                        conversation_manager.save(session_id, ctx)
                    except Exception:
                        pass
        except Exception as _tb_exc:
            logger.warning("copilot: topic boundary skipped (%s)", _tb_exc)
        # ── Persist conversation focus AFTER boundary ─────────────────────
        try:
            from src.conversation.conversation_focus import (
                update_conversation_focus as _fc_update,
            )

            if payload is None or not (payload.get("entities") or {}).get(
                "confidence_clarification"
            ):
                _fc_update(
                    ctx,
                    thinking=ctx.get("deep_thinking"),
                    recovery=(_rec.to_dict() if _rec else None),
                    message=message,
                    resolved=(ctx.get("reference_resolution") or None),
                )
        except Exception as _fc2_exc:
            logger.warning("copilot: focus update skipped (%s)", _fc2_exc)
      except Exception as _rec_exc:
        logger.warning("copilot: context recovery skipped (%s)", _rec_exc)

    # ── 0a-1a. Human Inference Engine — what did a human mean? ─────────────
    # BEFORE WEB / Natural / engines. Strong verbs dominate. Never "?".
    _hie = None
    if _sport_ok and payload is None:
      try:
        from src.conversation.human_inference import apply_human_inference as _hie_apply

        message, _hie = _hie_apply(message, ctx)
        if _hie and _hie.intent == "match_analysis" and _hie.home and _hie.away:
            # Lock analyze_match — Natural/NL must not reinterpret as agenda
            intent = "analyze_match"
            entities = {
                "home": _hie.home,
                "away": _hie.away,
                "human_inference": True,
            }
            routing_confidence = float(_hie.confidence or 0.95)
            skipped_nl = True
            logger.warning(
                "[AUDIT] HumanInference: forced analyze_match %s x %s",
                _hie.home,
                _hie.away,
            )
      except Exception as _hie_exc:
        logger.warning("copilot: human inference skipped (%s)", _hie_exc)

    # ── 0a-1b. WEB gather BEFORE draft (thinking control) ─────────────────
    # Skip WEB gather for match_analysis — engines + API own that path.
    try:
        _skip_web = bool(
            (not _sport_ok)
            or payload is not None
            or (_hie and getattr(_hie, "intent", None) == "match_analysis")
        )
        if not _skip_web:
            from src.conversation.web_intelligence import (
                gather_web_for_thinking as _v48_web_gather,
            )

            await _v48_web_gather(message, ctx)
    except Exception as _web_g_exc:
        logger.warning("copilot: web gather skipped (%s)", _web_g_exc)

    # ── 0a0. Conversational Understanding Engine (v4.3) ────────────────────
    _cue_dict: dict = {}
    try:
        if not _sport_ok or payload is not None:
            raise RuntimeError("skip_cue_non_sport")
        from src.conversation.conversational_understanding import understand as _cue_understand

        _cue = _cue_understand(message, ctx)
        _cue_dict = _cue.to_dict()
        # Rewrite natural "fale sobre A e B amanhã" → analyze A x B (Resolver untouched)
        if _cue.rewrite_for_pipeline and float(_cue.confidence or 0) >= 0.8:
            logger.warning(
                "[AUDIT] CUE: rewrite %r → %r goal=%s temporal=%s",
                message,
                _cue.rewrite_for_pipeline,
                _cue.explicit_goal,
                _cue.temporal_context,
            )
            message = _cue.rewrite_for_pipeline
        logger.warning(
            "[AUDIT] CUE: goal=%s social=%s temporal=%s conf=%.2f",
            _cue.explicit_goal,
            _cue.social_intents,
            _cue.temporal_context,
            _cue.confidence,
        )
    except Exception as _cue_exc:
        if "skip_cue_non_sport" not in str(_cue_exc):
            logger.warning("copilot: conversational understanding skipped (%s)", _cue_exc)

    # ── 0a0-pre. Continuity short follow-up (BEFORE presence / Natural / Intel)
    # Phase 8.4-A.8 — mercados? / placar? / estatísticas? / favorito? / escalações?
    # after match_opinion / partial_analysis / team_summary must reuse context
    # and must not be stolen by calendar_authority or intelligence_fallback.
    try:
        if payload is None:
            from src.brain import get_brain_meta as _gbm_cont
            from src.conversation.conversation_continuity import (
                try_contextual_short_followup as _cont_fu_try,
            )

            _cont_payload = _cont_fu_try(message, ctx, brain=_gbm_cont())
            if isinstance(_cont_payload, dict):
                payload = _cont_payload
                intent = str(payload.get("intent") or "follow_up")
                entities = dict(payload.get("entities") or {})
                routing_confidence = 0.93
                skipped_nl = True
                logger.warning(
                    "[AUDIT] ContinuityFollowUp: claimed before presence "
                    "kind=%s team=%r fixture=%r",
                    entities.get("continuity_kind"),
                    entities.get("followup_resolved_team"),
                    entities.get("followup_resolved_fixture"),
                )
    except Exception as _cont_fu_exc:
        logger.warning("copilot: continuity follow-up skipped (%s)", _cont_fu_exc)

    # ── 0a0. Emotional Presence FIRST (before HPL / LLM) ──────────────────
    # Absolute priority: pride / affection / thanks must never fall through
    # to "Posso ajudar com leituras...".
    # DeepThinking SoT: calendar/opinion/fixture topics never yield to emotional.
    # Phase 7.9-C: may claim deferred GA general (not hard-locked yet).
    try:
        from src.conversation.turn_ownership import can_presence_claim as _own_claim_emo

        if _own_claim_emo(payload if isinstance(payload, dict) else None):
            from src.conversation.brain_authority import (
                should_block_analysis_engines as _ba_block_emo,
            )
            from src.conversation.emotional_presence import (
                try_emotional_presence as _v47_emo,
            )

            from src.conversation.human_inference import is_match_analysis as _hie_match

            if not _ba_block_emo(ctx) and not _hie_match(ctx):
                _emo = _v47_emo(message, ctx, _conv_prefs)
                if _emo:
                    payload = _emo
                    intent = "emotional"
                    entities = dict(payload.get("entities") or {})
                    routing_confidence = 0.98
                    skipped_nl = True
                    logger.warning(
                        "[AUDIT] EmotionalPresence: kind=%s reply=%r",
                        entities.get("emotional_kind"),
                        str(payload.get("executive_summary") or "")[:120],
                    )
            else:
                logger.warning(
                    "[AUDIT] EmotionalPresence: SKIPPED — DeepThinking SoT topic=%s",
                    ((ctx.get("deep_thinking") or {}).get("topic_kind")),
                )
    except Exception as _emo_exc:
        logger.warning("copilot: emotional presence skipped (%s)", _emo_exc)

    # ── 0a0b. About You profile teach / forget / query (SoT) ───────────────
    try:
        from src.conversation.turn_ownership import can_presence_claim as _own_claim_prof

        if _own_claim_prof(payload if isinstance(payload, dict) else None):
            from src.conversation.user_profile_memory import (
                try_profile_commands as _v47_profile,
            )

            _prof = _v47_profile(message, ctx, _conv_prefs)
            if _prof:
                payload = _prof
                intent = str(payload.get("intent") or "small_talk")
                entities = dict(payload.get("entities") or {})
                routing_confidence = 0.95
                skipped_nl = True
                conversation_manager.save(session_id, ctx)
                logger.warning(
                    "[AUDIT] ProfileMemory: handled query=%s",
                    entities.get("profile_query") or "teach_or_forget",
                )
    except Exception as _prof_exc:
        logger.warning("copilot: profile memory skipped (%s)", _prof_exc)

    # ── 0a. Human Presence social (then legacy small talk) ─────────────────
    # Phase 7.4: NRE/HCE/META already own social — do not compete.
    # Phase 7.9-C: may claim deferred GA general.
    try:
        from src.conversation.human_presence import (
            build_presence_payload as _hpl_payload,
            build_social_presence_reply as _hpl_social,
            is_social_presence_turn as _hpl_is_social,
        )
        from src.conversation.turn_ownership import (
            can_presence_claim as _own_claim_hpl,
            should_skip_competing_social as _own_skip,
        )

        if payload is not None and _own_skip(payload):
            logger.warning("[AUDIT] Ownership: HPL skipped — turn already owned")
            try:
                from src.conversation.turn_ownership import note_overwrite_blocked as _owb

                _owb(payload, layer="HPL")
            except Exception:
                pass
        elif _own_claim_hpl(payload if isinstance(payload, dict) else None) and _hpl_is_social(
            _cue_dict
        ):
            from src.conversation.brain_authority import (
                should_block_analysis_engines as _ba_block_hpl,
            )

            if _ba_block_hpl(ctx):
                logger.warning(
                    "[AUDIT] HumanPresence: SKIPPED — DeepThinking SoT topic=%s",
                    ((ctx.get("deep_thinking") or {}).get("topic_kind")),
                )
            else:
                _hpl_text = _hpl_social(message, _cue_dict, ctx)
                if _hpl_text:
                    try:
                        from src.conversation.presence_humanization import (
                            apply_presence_humanization as _v452_hum,
                        )

                        _hpl_text = _v452_hum(_hpl_text, _conv_prefs)
                    except Exception:
                        pass
                    payload = _hpl_payload(_hpl_text, brain)
                    intent = "small_talk"
                    entities = dict(payload.get("entities") or {})
                    routing_confidence = 0.96
                    skipped_nl = True
                    try:
                        from src.conversation.conversation_state import note_small_talk

                        note_small_talk(ctx)
                        conversation_manager.save(session_id, ctx)
                    except Exception:
                        pass
                    logger.warning(
                        "[AUDIT] HumanPresence: SOCIAL HIT message=%r reply=%r",
                        message,
                        _hpl_text[:120],
                    )
    except Exception as _hpl_exc:
        logger.warning("copilot: human presence social skipped (%s)", _hpl_exc)

    # Soft name prefix — ONCE per session, GREETING only (not boa noite / como está)
    try:
        if payload is not None and intent == "small_talk":
            from src.conversation.user_profile_memory import (
                consume_greeting_prefix as _v47_greet_once,
            )

            _prefix = _v47_greet_once(
                ctx,
                social_intents=list((_cue_dict or {}).get("social_intents") or []),
            )
            if _prefix and (entities or {}).get("human_presence"):
                _sum = str(payload.get("executive_summary") or "")
                if _sum and "bom te ver novamente" not in _sum.lower():
                    _joined = f"{_prefix}\n\n{_sum}"
                    payload["executive_summary"] = _joined
                    payload["final_recommendation"] = _joined
                    conversation_manager.save(session_id, ctx)
                    logger.warning("[AUDIT] AboutYouGreeting: sent once session=%s", session_id)
    except Exception:
        pass

    # ── 0a1. Natural Conversation (calendar / team opinion / capabilities) ─
    try:
        from src.conversation.turn_ownership import (
            can_presence_claim as _own_claim_nat,
            should_skip_competing_social as _own_skip_nat,
        )

        if payload is not None and _own_skip_nat(payload):
            logger.warning("[AUDIT] Ownership: Natural skipped — turn already owned")
            try:
                from src.conversation.turn_ownership import note_overwrite_blocked as _owb

                _owb(payload, layer="NaturalConversation")
            except Exception:
                pass
        elif _own_claim_nat(payload if isinstance(payload, dict) else None):
            # 8.4-A.18 — NC must not steal short sport FUs with active anchor
            try:
                from src.conversation.sport_continuity_guard import (
                    should_block_nc as _scg_block_nc,
                )

                if _scg_block_nc(ctx, message):
                    logger.warning(
                        "[AUDIT] SportContinuityGuard: NaturalConversation blocked"
                    )
                    _nat = None
                else:
                    from src.conversation.natural_conversation import (
                        try_natural_conversation as _v452_natural,
                    )

                    _nat = await _v452_natural(message, ctx, _conv_prefs)
            except Exception:
                from src.conversation.natural_conversation import (
                    try_natural_conversation as _v452_natural,
                )

                _nat = await _v452_natural(message, ctx, _conv_prefs)
            if _nat:
                payload = _nat
                # Phase 8.4-A.5 — lock finalized Natural opinion before IntelFallback
                try:
                    from src.conversation.turn_ownership import (
                        is_finalized_opinion_payload as _opin_final,
                        mark_owner as _own_mark,
                    )

                    if _opin_final(payload):
                        payload = _own_mark(
                            payload, "SPORT", rewrite_locked=True
                        ) or payload
                        _ents_lock = dict(payload.get("entities") or {})
                        if (
                            _ents_lock.get("match_opinion_renderer")
                            or _ents_lock.get("response_type") == "match_opinion"
                        ):
                            _ents_lock["response_owner"] = "match_opinion_renderer"
                        else:
                            _ents_lock.setdefault(
                                "response_owner", "natural_conversation"
                            )
                        _ents_lock["final_response"] = True
                        payload["entities"] = _ents_lock
                        logger.warning(
                            "[AUDIT] Ownership: Natural opinion LOCKED — "
                            "IntelFallback must not overwrite owner=%s",
                            _ents_lock.get("response_owner"),
                        )
                except Exception as _lock_exc:
                    logger.warning(
                        "copilot: natural opinion lock skipped (%s)", _lock_exc
                    )
                intent = str(payload.get("intent") or "conversation_assist")
                entities = dict(payload.get("entities") or {})
                routing_confidence = 0.91
                skipped_nl = True
                logger.warning(
                    "[AUDIT] NaturalConversation: kind=%s intent=%s",
                    entities.get("natural_kind"),
                    intent,
                )
                # Phase 8.4-A.4 forensics
                logger.warning(
                    "[AUDIT] Forensics84a4 NATURAL: path=%s import_ok=%s stage=%s "
                    "rtype=%s mop=%s",
                    entities.get("team_opinion_path"),
                    entities.get("match_opinion_import_ok"),
                    entities.get("renderer_stage"),
                    entities.get("response_type"),
                    entities.get("match_opinion_renderer"),
                )
    except Exception as _nat_exc:
        logger.warning("copilot: natural conversation skipped (%s)", _nat_exc)

    # ── 0a1b. Intelligence Fallback (Copa / never empty topics) ────────────
    try:
        from src.conversation.turn_ownership import (
            can_presence_claim as _own_claim_intel,
            should_skip_competing_social as _own_skip_intel,
        )

        if payload is not None and _own_skip_intel(payload):
            logger.warning("[AUDIT] Ownership: IntelFallback skipped — owned")
            try:
                from src.conversation.turn_ownership import note_overwrite_blocked as _owb

                _owb(payload, layer="IntelFallback")
            except Exception:
                pass
        elif _own_claim_intel(payload if isinstance(payload, dict) else None):
            from src.conversation.intelligence_fallback import (
                try_intelligence_fallback as _v48_intel,
            )

            _prev_forensics = (
                dict(ctx.get("_forensics_84a4") or {})
                if isinstance(ctx, dict)
                else {}
            )
            _prev_rtype = None
            if isinstance(payload, dict):
                _prev_rtype = (payload.get("entities") or {}).get("response_type")
            _intel = _v48_intel(message, ctx, _conv_prefs)
            if _intel:
                payload = _intel
                intent = str(payload.get("intent") or "conversation_assist")
                entities = dict(payload.get("entities") or {})
                # Phase 8.4-A.4 — keep forensic trail across overwrite (no UX change)
                if _prev_forensics:
                    for _fk, _fv in _prev_forensics.items():
                        entities.setdefault(_fk, _fv)
                    entities["overwrite_by"] = "intelligence_fallback"
                    entities["response_type_before_overwrite"] = _prev_rtype or (
                        _prev_forensics.get("response_type")
                    )
                    entities["response_type_after_overwrite"] = entities.get(
                        "response_type"
                    )
                    if isinstance(payload, dict):
                        payload["entities"] = entities
                routing_confidence = 0.9
                skipped_nl = True
                logger.warning(
                    "[AUDIT] IntelligenceFallback: kind=%s",
                    entities.get("fallback_kind"),
                )
                logger.warning(
                    "[AUDIT] Forensics84a4 OVERWRITE: by=intelligence_fallback "
                    "before=%s after=%s stage=%s",
                    entities.get("response_type_before_overwrite"),
                    entities.get("response_type_after_overwrite"),
                    entities.get("renderer_stage"),
                )
                try:
                    from src.conversation.pipeline_trace import trace as _ptrace

                    _ptrace(
                        "FALLBACK",
                        source="intelligence_fallback",
                        kind=entities.get("fallback_kind"),
                        fallback=True,
                    )
                except Exception:
                    pass
    except Exception as _intel_exc:
        logger.warning("copilot: intelligence fallback skipped (%s)", _intel_exc)

    # Legacy Small Talk fallback (only if HPL did not handle)
    # Phase 7.4 candidate freeze: never steal owned NRE/HCE turns.
    try:
        from src.conversation.turn_ownership import (
            can_presence_claim as _own_claim_st,
            should_skip_competing_social as _own_skip_st,
        )

        if payload is not None and _own_skip_st(payload):
            logger.warning("[AUDIT] Ownership: legacy SmallTalk skipped — owned")
            try:
                from src.conversation.turn_ownership import note_overwrite_blocked as _owb

                _owb(payload, layer="LegacySmallTalk")
            except Exception:
                pass
        elif _own_claim_st(payload if isinstance(payload, dict) else None):
            from src.communication import try_small_talk as _try_small_talk

            _social = _try_small_talk(message, brain)
            if _social:
                try:
                    from src.conversation.presence_humanization import (
                        apply_presence_humanization as _v452_hum2,
                    )

                    _sum = str(_social.get("executive_summary") or "")
                    _hum = _v452_hum2(_sum, _conv_prefs)
                    if _hum:
                        _social["executive_summary"] = _hum
                        _social["final_recommendation"] = _hum
                except Exception:
                    pass
                payload = _social
                intent = "small_talk"
                entities = {"social": True}
                routing_confidence = 0.95
                skipped_nl = True
                try:
                    from src.conversation.conversation_state import note_small_talk

                    note_small_talk(ctx)
                    conversation_manager.save(session_id, ctx)
                except Exception:
                    pass
                logger.warning("[AUDIT] SmallTalkGate: HIT (legacy fallback) message=%r", message)
    except Exception as _st_exc:
        logger.warning("copilot: small talk gate skipped (%s)", _st_exc)

    # Phase 7.9-C — second ownership pass after presence layers (before late filters)
    try:
        from src.conversation.turn_ownership import (
            finalize_presence_ownership as _own_presence,
        )

        if isinstance(payload, dict):
            payload = _own_presence(payload) or payload
            entities = dict(payload.get("entities") or {})
            intent = str(payload.get("intent") or intent)
    except Exception as _own_p_exc:
        logger.warning("copilot: presence ownership finalize skipped (%s)", _own_p_exc)

    # ── 0a2. Conversation State TTL + cancel/reset + topic switch ──────────
    try:
        from src.conversation.conversation_state import (
            expire_conversation_state_if_needed as _cs_expire,
        )
        from src.conversation.message_intelligence import (
            clear_fixture_context as _ci_clear_ctx,
            expire_ci_pending_if_needed as _ci_expire_pending,
            is_cancel_reset as _ci_is_cancel,
            is_topic_switch as _ci_is_topic_switch,
        )

        if _cs_expire(ctx):
            logger.warning("[AUDIT] ConversationState: EXPIRED — conversational cleared")
            conversation_manager.save(session_id, ctx)

        if _ci_expire_pending(ctx):
            logger.warning("[AUDIT] ConversationIntel: pending EXPIRED — cleared")
            conversation_manager.save(session_id, ctx)

        if payload is None and _ci_is_cancel(message):
            _ci_clear_ctx(ctx)
            conversation_manager.save(session_id, ctx)
            from src.conversation.message_intelligence import (
                build_conversational_payload as _ci_talk_payload,
            )

            payload = _ci_talk_payload(
                "Contexto limpo. Pode começar de novo — diga um confronto "
                "ou só converse comigo.",
                brain,
            )
            intent = "conversation_assist"
            entities = {"context_reset": True, "conversation_intelligence": True}
            routing_confidence = 0.95
            skipped_nl = True
            logger.warning("[AUDIT] ConversationIntel: CONTEXT RESET message=%r", message)
        elif payload is None and _ci_is_topic_switch(message, ctx):
            # New A x B — drop pending clarify; active fixture replaced on analyze save
            if ctx.get("ci_pending"):
                ctx.pop("ci_pending", None)
                conversation_manager.save(session_id, ctx)
                logger.warning(
                    "[AUDIT] ConversationIntel: TOPIC SWITCH — pending cleared message=%r",
                    message,
                )
    except Exception as _ctx_gate_exc:
        logger.warning("copilot: context gate skipped (%s)", _ctx_gate_exc)

    # ── 0a2a. Context Reinforcement (v4.5) — soft priority / anti-forget ───
    try:
        from src.conversation.context_reinforcement import (
            reinforce_context as _v45_reinforce,
        )

        _creinf = _v45_reinforce(ctx, message)
        logger.warning(
            "[AUDIT] ContextReinforcement: fx=%.2f mkt=%.2f rec=%.2f imp=%.2f fixture=%r",
            float(_creinf.get("fixture_score") or 0),
            float(_creinf.get("market_score") or 0),
            float(_creinf.get("recency_score") or 0),
            float(_creinf.get("importance_score") or 0),
            _creinf.get("active_fixture"),
        )
    except Exception as _creinf_exc:
        logger.warning("copilot: context reinforcement skipped (%s)", _creinf_exc)

    # ── 0a2b. Conversation Reasoner (v4.0) — thinks, does NOT reply ────────
    # Phase 7.4: freeze on owned social/continuity turns (no user-visible value).
    # Fail-open: errors never block Small Talk / CI / FollowUp / engines.
    try:
        from src.conversation.turn_ownership import should_skip_competing_social as _own_skip_cr

        _skip_social_reasoners = bool(payload is not None and _own_skip_cr(payload))
    except Exception:
        _skip_social_reasoners = False

    try:
        if _skip_social_reasoners:
            logger.warning("[AUDIT] Ownership: Reasoner skipped — turn owned")
        else:
            from src.conversation.conversation_reasoner import (
                attach_reasoning as _cr_attach,
                reason as _cr_reason,
            )

            _thought = _cr_reason(message, ctx)
            _cr_attach(ctx, _thought)
            logger.warning(
                "[AUDIT] ConversationReasoner: type=%s goal=%r conf=%.2f next=%s thought=%r",
                _thought.reasoning_type,
                _thought.user_goal,
                _thought.confidence,
                _thought.next_action,
                (_thought.thought or "")[:180],
            )
    except Exception as _cr_exc:
        logger.warning("copilot: conversation reasoner skipped (%s)", _cr_exc)

    # ── 0a2b2. Conversation Intelligence Layer (v4.2) — real intent ────────
    # Hypotheses + context priority + humanizer plan. Rewrites last_reasoning
    # for CRL. Does NOT edit Reasoner/CRL/State modules. Fail-open.
    try:
        if _skip_social_reasoners:
            logger.warning("[AUDIT] Ownership: CIL skipped — turn owned")
        else:
            from src.conversation.conversation_intelligence_layer import (
                run_intelligence as _cil_run,
            )

            _cil_thought = _cil_run(message, ctx)
            logger.warning(
                "[AUDIT] ConversationIntelligenceLayer: goal=%s conf=%.2f strategy=%s selected=%r",
                _cil_thought.user_intent,
                _cil_thought.confidence,
                _cil_thought.response_strategy,
                _cil_thought.selected_interpretation,
            )
    except Exception as _cil_exc:
        logger.warning("copilot: conversation intelligence layer skipped (%s)", _cil_exc)

    # ── 0a2c. Conversation Response Layer (v4.1) — HOW to reply ────────────
    # Consumes last_reasoning (possibly refined by CIL). Fail-open.
    try:
        from src.conversation.human_inference import is_match_analysis as _hie_match_crl

        if payload is None and _hie_match_crl(ctx):
            logger.warning(
                "[AUDIT] CRL: SKIPPED short-circuit — HumanInference match_analysis"
            )
        elif payload is None:
            from src.conversation.conversation_intelligence_layer import (
                refine_crl_reply as _cil_refine,
            )
            from src.conversation.conversation_response_layer import (
                apply_crl_payload as _crl_apply,
                attach_response_plan as _crl_attach,
                plan_response as _crl_plan,
            )

            _plan = _crl_plan(message, ctx)
            # Humanize / override copy without editing CRL module
            _refined = _cil_refine(_plan.reply_text, ctx)
            if _refined:
                _plan.reply_text = _refined
            # v4.5 Deep Reasoning (wraps v4.4 reflection) — deeper short-circuit copy
            try:
                from src.conversation.deep_reasoning import (
                    run_deep_reasoning as _v45_deep,
                )

                _refl = _v45_deep(message, ctx, _plan.reply_text)
                if _refl.chosen_answer and _plan.should_short_circuit:
                    _plan.reply_text = _refl.chosen_answer
                    logger.warning(
                        "[AUDIT] DeepReasoning: intent=%s position=%s conf=%.2f",
                        _refl.user_real_intent,
                        _refl.position,
                        _refl.confidence,
                    )
            except Exception as _refl_exc:
                logger.warning("copilot: deep reasoning skipped (%s)", _refl_exc)
            _crl_attach(ctx, _plan)
            if _plan.should_short_circuit:
                _crl_payload = _crl_apply(_plan, brain)
                if _crl_payload:
                    payload = _crl_payload
                    intent = "conversation_assist"
                    entities = dict(_crl_payload.get("entities") or {})
                    entities["cil"] = True
                    if isinstance(ctx.get("conversation_goal"), dict):
                        entities["cil_goal"] = ctx["conversation_goal"].get("goal_type")
                    payload["entities"] = entities
                    routing_confidence = 0.9
                    skipped_nl = True
                    logger.warning(
                        "[AUDIT] ConversationResponseLayer: mode=%s short_circuit=1 show_header=%s msg=%r",
                        _plan.mode,
                        _plan.show_header,
                        message,
                    )
            else:
                logger.warning(
                    "[AUDIT] ConversationResponseLayer: mode=%s pass_through msg=%r",
                    _plan.mode,
                    message,
                )
    except Exception as _crl_exc:
        logger.warning("copilot: conversation response layer skipped (%s)", _crl_exc)

    # ── 0a3. Conversation Intelligence (after CRL) ────────────────────────
    # Normalization → Context → Intent → Confidence. Never invents fixtures.
    try:
        if payload is None:
            from src.conversation.message_intelligence import (
                build_clarification_payload as _ci_clarify_payload,
                build_conversational_payload as _ci_talk_payload,
                process_inbound_message as _ci_process,
                set_ci_pending as _ci_set_pending,
            )

            _ci = _ci_process(message, ctx)
            if _ci.conversational_reply:
                payload = _ci_talk_payload(_ci.conversational_reply, brain)
                intent = "conversation_assist"
                entities = {"conversation_assist": True, "conversation_intelligence": True}
                routing_confidence = float(_ci.confidence or 0.85)
                skipped_nl = True
                logger.warning(
                    "[AUDIT] ConversationIntel: TALK band=%s msg=%r",
                    _ci.confidence_band,
                    message,
                )
            elif _ci.needs_clarification and _ci.clarification_prompt:
                payload = _ci_clarify_payload(_ci.clarification_prompt, brain)
                intent = "clarification"
                entities = {"clarification": True, "conversation_intelligence": True}
                routing_confidence = float(_ci.confidence or 0.4)
                skipped_nl = True
                _pending_team = (_ci.metadata or {}).get("pending_team")
                if _pending_team:
                    _ci_set_pending(ctx, kind="single_team_clarify", team=str(_pending_team))
                    conversation_manager.save(session_id, ctx)
                logger.warning(
                    "[AUDIT] ConversationIntel: CLARIFY band=%s conf=%.2f msg=%r",
                    _ci.confidence_band,
                    _ci.confidence,
                    message,
                )
            elif _ci.confidence_band == "high" and _ci.message_for_pipeline:
                if _ci.message_for_pipeline != message:
                    logger.warning(
                        "[AUDIT] ConversationIntel: REWRITE band=high %r → %r",
                        message,
                        _ci.message_for_pipeline,
                    )
                message = _ci.message_for_pipeline
                # Successful rewrite / follow-up path clears pending clarify
                if ctx.get("ci_pending"):
                    ctx.pop("ci_pending", None)
    except Exception as _ci_exc:
        logger.warning("copilot: conversation intelligence skipped (%s)", _ci_exc)

    # Silently extract + update user profile from this message
    old_profile = ctx.get("user_profile", {})
    new_profile = _extract_profile(message, old_profile)
    if new_profile != old_profile:
        ctx["user_profile"] = new_profile

    # ── 0b. Follow-up / fixture context guard (v3.3.1-beta) ───────────────
    # Compare entities BEFORE reusing last_analysis. Different teams → discard
    # follow-up, start a new fixture context, force analyze_match.
    from src.core.followup_guard import (
        decide_followup_reuse as _decide_fu_reuse,
        start_new_fixture_context as _start_new_fx,
    )

    # Hard stop: non-sport must never hit follow-up / NL sport routing
    if not _sport_ok and payload is None:
        try:
            from src.conversation.general_assistant import (
                try_general_assistant as _ga_retry,
            )
            from src.conversation.human_conversation_engine import (
                try_human_conversation as _hce_force,
            )
            from src.conversation.conversation_repair import (
                try_conversation_repair as _repair_force,
            )
            from src.conversation.dialog_mode import (
                progress_act_text as _dm_progress,
                try_dialog_mode_claim as _dm_claim,
            )

            _mi_n = (
                (_master.intent if _master else None)
                or str((ctx.get("master_intent") or {}).get("intent") or "GENERAL_CHAT")
            )
            # Phase 8.2-A — repair before forced path; P1-B never uses sticky Entendi
            payload = _repair_force(message, ctx)
            if payload is None:
                payload = _hce_force(
                    message,
                    ctx,
                    master_intent=_mi_n,
                    existing_payload=None,
                    prefs=_conv_prefs,
                )
            if payload is None:
                payload = _ga_retry(message, _mi_n, ctx)
            if payload is None:
                payload = _dm_claim(message, ctx, master_intent=_mi_n)
            if payload is None:
                _prog = _dm_progress(message)
                payload = {
                    "intent": "clarification",
                    "entities": {
                        "dialog_mode": "UNKNOWN",
                        "response_owner": "unknown_policy",
                        "has_analysis": False,
                        "show_header": False,
                        "skip_llm": True,
                        "fallback": True,
                        "fallback_source": "forced_dialog_progress",
                        "p1_dialog_mode": True,
                        "rewrite_locked": True,
                    },
                    "executive_summary": _prog,
                    "final_recommendation": _prog,
                    "best_markets": [],
                    "match": None,
                    "is_live": False,
                    "brain": brain,
                }
            intent = str(payload.get("intent") or "general_chat")
            entities = dict(payload.get("entities") or {})
            routing_confidence = 0.9
            skipped_nl = True
            logger.warning(
                "[AUDIT] MasterIntent: forced human/general (block NL/follow-up) intent=%s",
                _mi_n,
            )
            # Phase 7.9-D P1-1 — forced path ownership finalize (lock before late filters)
            try:
                from src.conversation.turn_ownership import (
                    finalize_forced_ownership as _own_forced,
                )

                if isinstance(payload, dict):
                    payload = _own_forced(payload) or payload
                    entities = dict(payload.get("entities") or {})
                    intent = str(payload.get("intent") or intent)
            except Exception as _own_f_exc:
                logger.warning("copilot: forced ownership finalize skipped (%s)", _own_f_exc)
            try:
                from src.conversation.pipeline_trace import (
                    snapshot_payload as _psnap,
                    trace as _ptrace,
                )

                _snap_f = _psnap(payload if isinstance(payload, dict) else None)
                _ptrace(
                    "FALLBACK",
                    source="forced_nonsport",
                    master=_mi_n,
                    has_confidence=_snap_f.get("has_confidence"),
                    summary_prefix=_snap_f.get("summary_prefix"),
                    owner=_snap_f.get("owner"),
                    locked=_snap_f.get("locked"),
                    fallback=True,
                )
            except Exception:
                pass
        except Exception as _ga_force_exc:
            logger.warning("copilot: forced general failed (%s)", _ga_force_exc)
            skipped_nl = True

    _ctx_last_match = ctx.get("last_match") or ctx.get("last_fixture")
    _fu_decision = _decide_fu_reuse(message, ctx)

    if payload is None and _sport_ok and _fu_decision.new_fixture and not _fu_decision.reuse:
        # Explicit new A x B — never reuse prior England/etc. context
        intent = "analyze_match"
        entities = {
            "home": _fu_decision.home,
            "away": _fu_decision.away,
            **({"is_live": True} if _fu_decision.is_live else {}),
        }
        routing_confidence = max(routing_confidence, 0.92)
        skipped_nl = True
        _start_new_fx(
            ctx,
            str(_fu_decision.home or ""),
            str(_fu_decision.away or ""),
            is_live=bool(_fu_decision.is_live),
        )
        logger.warning(
            "[AUDIT] FixtureGuard: NEW fixture overrides context → analyze_match "
            "prev=%r new=%r",
            _fu_decision.previous_fixture,
            _fu_decision.new_fixture,
        )
    elif (
        payload is None
        and _sport_ok
        and _ctx_last_match
        and _is_followup(message)
        and _fu_decision.reuse
    ):
        logger.warning(
            "[AUDIT] QuickFollowUpGate: ENTER (before NL) last_match=%r message=%r",
            _ctx_last_match, message,
        )
        fu_payload = _fu_resolve(message, ctx, brain)
        if fu_payload:
            payload = fu_payload
            intent = "follow_up"
            entities = dict(fu_payload.get("entities") or {})
            routing_confidence = 0.90
            skipped_nl = True
            logger.warning("[AUDIT] QuickFollowUpGate: HIT → skip nl_router ✅")
        else:
            logger.warning("[AUDIT] QuickFollowUpGate: engine returned None — fall through")
    elif (
        payload is None
        and _sport_ok
        and _ctx_last_match
        and _is_followup(message)
        and not _fu_decision.reuse
    ):
        # Follow-up phrasing but different teams named — already handled above;
        # belt-and-suspenders fallthrough to analyze if entities present.
        if _fu_decision.home and _fu_decision.away:
            intent = "analyze_match"
            entities = {
                "home": _fu_decision.home,
                "away": _fu_decision.away,
                **({"is_live": True} if _fu_decision.is_live else {}),
            }
            routing_confidence = 0.92
            skipped_nl = True
            _start_new_fx(
                ctx,
                str(_fu_decision.home),
                str(_fu_decision.away),
                is_live=bool(_fu_decision.is_live),
            )

    # ── NL Routing (skipped on quick follow-up hit / non-sport) ───────────
    if not skipped_nl and _sport_ok:
        _route = _nl_route(message)
        intent, entities, routing_confidence = _route.intent, _route.entities, _route.confidence
    elif not skipped_nl and not _sport_ok:
        skipped_nl = True
        intent = intent if intent and intent != "unknown" else "general_chat"
        logger.warning("[AUDIT] MasterIntent: NL routing blocked (non-sport)")

    # P2.5-S — sport understanding recall after NL: never leave real sport as unknown
    try:
        from src.conversation.sport_understanding import (
            enrich_sport_entities as _su_enrich,
            is_fixture_pair_ask as _su_fx,
            should_force_sport_mode as _su_force,
            stamp_sport_understanding as _su_stamp,
        )

        _mi_s = (
            (_master.intent if _master else None)
            or str((ctx.get("master_intent") or {}).get("intent") or "")
        )
        if _sport_ok and _su_force(message, ctx, master_intent=_mi_s):
            _su_stamp(ctx, message, master_intent=_mi_s, forced=True)
            entities = _su_enrich(entities if isinstance(entities, dict) else {}, message)
            if _su_fx(message) and intent in {None, "", "unknown", "general_chat", "clarification"}:
                intent = "analyze_match"
                routing_confidence = max(float(routing_confidence or 0), 0.86)
                logger.warning("[AUDIT] P25SportUnderstanding: forced analyze_match")
            elif intent in {None, "", "unknown"}:
                # Team-form / sport chat — keep sport-ok path; stamp mode for harness
                intent = intent if intent and intent != "unknown" else "conversation_assist"
                routing_confidence = max(float(routing_confidence or 0), 0.84)
                logger.warning(
                    "[AUDIT] P25SportUnderstanding: stamped SPORT on intent=%s",
                    intent,
                )
    except Exception as _su_exc:
        logger.warning("copilot: P25 sport understanding skipped (%s)", _su_exc)

    logger.info(
        "copilot request_id=%s session=%s intent=%s conf=%.3f entities=%s "
        "message=%r skipped_nl=%s",
        request_id, session_id, intent, routing_confidence, entities, message, skipped_nl,
    )

    # Persist user turn
    _db_save_msg(session_id=session_id, role="user", content=message,
                 intent=intent, entities=entities)

    try:
        # ── 1. Emotional / conversational (only if not already answered) ──
        if payload is None:
            from src.conversation.brain_authority import (
                should_block_analysis_engines as _ba_block_em2,
            )

            _has_fixture_ents = bool(entities.get("home")) and bool(entities.get("away"))
            if not _ba_block_em2(ctx) and not (
                intent == "analyze_match" and _has_fixture_ents
            ):
                em = _conv_detect(message)
                if em and em[1] >= 0.80:
                    emotional_intent, em_conf = em
                    payload = _conv_respond(emotional_intent, ctx, brain)
                    intent = emotional_intent
                    routing_confidence = em_conf
            elif _ba_block_em2(ctx):
                logger.warning(
                    "[AUDIT] EmotionalDetect: SKIPPED — DeepThinking SoT kind=%s",
                    ((ctx.get("deep_thinking") or {}).get("topic_kind")),
                )

        # ── 2. Legacy follow-up after NL (compat if QuickGate missed) ─────
        _ctx_last_match  = ctx.get("last_match") or ctx.get("last_fixture")
        _ctx_last_intent = ctx.get("last_intent")
        _followup_check  = _is_followup(message)
        _fu_decision2 = _decide_fu_reuse(
            message,
            ctx,
        )
        logger.warning(
            "[AUDIT] follow-up gate: nl_intent=%r | ctx.last_match=%r | ctx.last_intent=%r"
            " | follow_up_detected=%s | already_payload=%s | FOLLOWUP_REUSED=%s",
            intent, _ctx_last_match, _ctx_last_intent, _followup_check,
            payload is not None,
            "true" if _fu_decision2.reuse else "false",
        )
        if (
            payload is None
            and _fu_decision2.new_fixture
            and not _fu_decision2.reuse
            and _fu_decision2.home
            and _fu_decision2.away
        ):
            # Named a different fixture — discard follow-up, force analyze
            intent = "analyze_match"
            entities = {
                "home": _fu_decision2.home,
                "away": _fu_decision2.away,
                **({"is_live": True} if _fu_decision2.is_live else {}),
            }
            _start_new_fx(
                ctx,
                str(_fu_decision2.home),
                str(_fu_decision2.away),
                is_live=bool(_fu_decision2.is_live),
            )
            logger.warning(
                "[AUDIT] follow-up gate: DISCARD reuse — new fixture %r (was %r)",
                _fu_decision2.new_fixture,
                _fu_decision2.previous_fixture,
            )
        elif payload is None and _ctx_last_match and _followup_check and _fu_decision2.reuse:
            logger.warning(
                "[AUDIT] follow-up gate: ENTERING follow-up engine "
                "(has_last_match=True, follow_up_detected=True, FOLLOWUP_REUSED=true)"
            )
            fu_payload = _fu_resolve(message, ctx, brain)
            if fu_payload:
                payload = fu_payload
                intent = "follow_up"
                routing_confidence = 0.88
                logger.warning("[AUDIT] follow-up gate: engine returned payload → intent=follow_up ✅")
            else:
                logger.warning("[AUDIT] follow-up gate: engine returned None — falling through to normal routing")
        elif payload is None and not _ctx_last_match:
            logger.warning("[AUDIT] follow-up gate: SKIPPED — ctx.last_match is empty (no prior analysis in session)")
        elif payload is None and not _followup_check:
            logger.warning("[AUDIT] follow-up gate: SKIPPED — message not recognised as follow-up pattern")

        # ── 3. Normal routing ─────────────────────────────────────────────
        if payload is None:
            # DeepThinking SoT — never let analyze engines steal calendar/opinion.
            try:
                from src.conversation.brain_authority import (
                    ensure_fallback_for_thinking as _ba_ensure_txt,
                    should_block_analysis_engines as _ba_block_eng,
                )

                if _ba_block_eng(ctx) and intent == "analyze_match":
                    _txt = _ba_ensure_txt(message, ctx)
                    try:
                        from src.conversation.message_intelligence import (
                            build_conversational_payload as _ba_conv,
                        )

                        _fb = _ba_conv(_txt, {})
                    except Exception:
                        _fb = {
                            "intent": "conversation_assist",
                            "executive_summary": _txt,
                            "final_recommendation": _txt,
                            "entities": {
                                "dt_sot_block_engines": True,
                                "has_analysis": False,
                                "show_header": False,
                                "skip_llm": True,
                            },
                        }
                    if _fb:
                        ents = dict(_fb.get("entities") or {})
                        ents["dt_sot_block_engines"] = True
                        _fb["entities"] = ents
                        payload = _fb
                        intent = str(payload.get("intent") or "conversation_assist")
                        entities = dict(payload.get("entities") or {})
                        routing_confidence = 0.88
                        skipped_nl = True
                        logger.warning(
                            "[AUDIT] AnalysisEngines: BLOCKED by DeepThinking SoT kind=%s",
                            ((ctx.get("deep_thinking") or {}).get("topic_kind")),
                        )
            except Exception as _ba_eng_exc:
                logger.warning("copilot: DT engine gate skipped (%s)", _ba_eng_exc)

        if payload is None:
            if intent == "analyze_match":
                home = entities.get("home", "")
                away = entities.get("away", "")
                logger.warning(
                    "[AUDIT] copilot dispatch: intent=%r home=%r away=%r is_live=%r",
                    intent, home, away, entities.get("is_live"),
                )
                if not home or not away:
                    logger.warning(
                        "[AUDIT] copilot dispatch: missing home/away — "
                        "Inference V2 degraded path (no hard fallback abort)"
                    )
                    from src.brain import get_brain_meta as _gbm_ent
                    from src.core.inference_context import InferenceContext

                    _ictx = InferenceContext(soft_mode=True)
                    _ictx.register_failure(
                        "entity_extract",
                        "Times home/away não extraídos do NLP",
                        signal="teams",
                    )
                    _ictx.mark_missing("fixture", "Sem entidades de partida")
                    _ictx.finalize()
                    hint = ""
                    if home:
                        hint = f" Identifiquei apenas **{home}** — falta o adversário."
                    elif away:
                        hint = f" Identifiquei apenas **{away}** — falta o time da casa."
                    payload = _run_fallback(message, intent)
                    payload["intent"] = "analyze_match"
                    payload["entities"] = {"home": home or None, "away": away or None}
                    payload["executive_summary"] = (
                        "Não consegui extrair os dois times da mensagem."
                        + hint
                        + "\n\nInforme no formato: **\"Analisar [Casa] x [Visitante]\"**.\n\n"
                        + "A Aurora registrou a falha (Inference V2) e manteve a conversa "
                        "com confiança reduzida em vez de abortar."
                    )
                    payload["confidence"] = {
                        "score": _ictx.apply_to_score(1.5),
                        "label": "insufficient",
                        "explanation": (
                            f"Inference V2: entidades incompletas — "
                            f"penalidade −{_ictx.total_penalty():.1f}"
                        ),
                        "data_sources": ["Inference Layer V2", "NL Router"],
                    }
                    payload["knowledge_notes"] = (
                        list(payload.get("knowledge_notes") or [])
                        + _ictx.knowledge_notes_pt()
                    )
                    payload["brain"] = {
                        **_gbm_ent(),
                        "inference": _ictx.explainability(),
                    }
                    payload["final_recommendation"] = (
                        "Digite os dois times: **\"Analisar [Time A] x [Time B]\"**."
                    )
                else:
                    from src.core.fixture_integrity import (
                        apply_integrity_to_payload as _apply_integrity,
                        assess_analyze_result as _assess_fx,
                        assess_named_fixture as _assess_named,
                        blocked_integrity_payload as _blocked_fx,
                    )

                    _integrity = _assess_named(home, away)
                    logger.warning(
                        "[AUDIT] FixtureIntegrity: precheck status=%s home=%r away=%r reasons=%s",
                        _integrity.status, home, away, _integrity.reasons,
                    )
                    # When precheck would INVALID, still try soft analyze (live/API
                    # may locate a real fixture). Fiction stays INVALID inside _run_analyze.
                    try:
                        logger.warning(
                            "[AUDIT] ctx_before: last_match=%r last_intent=%r",
                            ctx.get("last_match"), ctx.get("last_intent"),
                        )
                        prefer_live = bool(entities.get("is_live")) or _integrity.is_blocked
                        payload = await _run_analyze(
                            home, away, prefer_live=prefer_live, force_refresh=force_refresh
                        )
                        _still_invalid = (
                            payload.get("fixture_quality") == "INVALID"
                            or (payload.get("entities") or {}).get("entity_invalid") is True
                            or payload.get("fixture_status") in ("NOT_FOUND", "FICTIONAL")
                        )
                        if _integrity.is_blocked and _still_invalid:
                            payload = _blocked_fx(_integrity, brain=brain)
                        else:
                            _post = _assess_fx(
                                home,
                                away,
                                fixture_id=payload.get("fixture_id"),
                                is_partial=bool(payload.get("_partial")),
                                data_completeness=float(
                                    ((payload.get("brain") or {}).get("inference") or {}).get(
                                        "data_completeness", 1.0
                                    )
                                ),
                            )
                            # If soft analyze found a real fixture, prefer post-assess over
                            # a precheck INVALID caused only by missing aliases.
                            if (
                                _integrity.is_blocked
                                and not _post.is_blocked
                                and int(payload.get("fixture_id") or 0) > 0
                            ):
                                logger.warning(
                                    "[AUDIT] FixtureIntegrity: live/API rescue home=%r away=%r fid=%s",
                                    home,
                                    away,
                                    payload.get("fixture_id"),
                                )
                            payload = _apply_integrity(payload, _post)
                            logger.warning(
                                "[AUDIT] FixtureIntegrity: postcheck status=%s markets=%d",
                                _post.status,
                                len(payload.get("best_markets") or []),
                            )
                            if not _post.is_blocked and not (
                                payload.get("fixture_quality") == "INVALID"
                            ):
                                _save_analysis_context(ctx, payload, home, away)
                                _db_upd_session(session_id, home=home, away=away, intent=intent)
                            else:
                                # Do not poison follow-up context with fictional/generic markets
                                ctx["last_analysis"] = None
                                ctx["last_market"] = None
                        logger.warning(
                            "[AUDIT] copilot dispatch: _run_analyze done, match=%r status=%r",
                            payload.get("match"),
                            payload.get("fixture_status"),
                        )
                        logger.warning(
                            "[AUDIT] ctx_after: last_match=%r last_intent=%r",
                            ctx.get("last_match"), ctx.get("last_intent"),
                        )
                    except Exception as _analyze_exc:
                        # Soft analyze already avoids 404; this catches engine crashes.
                        logger.warning(
                            "[AUDIT] copilot dispatch: _run_analyze raised %s: %s — "
                            "Fixture Integrity Guard returns NOT_FOUND",
                            type(_analyze_exc).__name__, _analyze_exc,
                        )
                        from src.core.fixture_integrity import FixtureIntegrityResult

                        payload = _blocked_fx(
                            FixtureIntegrityResult(
                                status="NOT_FOUND",
                                home=home,
                                away=away,
                                markets_blocked=True,
                                header_blocked=True,
                                confidence_label="insufficient",
                                confidence_score=1.0,
                                message=(
                                    "Não consegui localizar um confronto esportivo válido."
                                ),
                                reasons=(f"analyze_error:{type(_analyze_exc).__name__}",),
                            ),
                            brain=brain,
                        )

            elif intent == "live_team_analysis":
                # FIX 1 — "analise jogo do [team]" → search live for that team
                # then call full _run_analyze pipeline with the found match.
                from src.routers.live import _build_live_response as _lbr_single
                _lt_team = entities.get("team", "")
                logger.warning(
                    "[AUDIT] live_team_analysis: team=%r | ctx_before=last_match=%r last_intent=%r",
                    _lt_team, ctx.get("last_match"), ctx.get("last_intent"),
                )
                _lt_live  = await _lbr_single()
                _lt_list  = _lt_live.get("matches", [])
                logger.warning("[AUDIT] live_team_analysis: %d live matches to search", len(_lt_list))
                # Phase 5A — live matching via EntityResolver (fold + name_match)
                from src.core.entity_resolver import match_team_in_fixture_names
                _lt_home, _lt_away = "", ""
                for _lt_fx in _lt_list:
                    _lt_h = ((_lt_fx.get("home") or {}).get("name") or "")
                    _lt_a = ((_lt_fx.get("away") or {}).get("name") or "")
                    if match_team_in_fixture_names(_lt_team, _lt_h, _lt_a):
                        _lt_home, _lt_away = _lt_h, _lt_a
                        logger.warning("[AUDIT] live_team_analysis: matched %r vs %r", _lt_h, _lt_a)
                        break
                if _lt_home and _lt_away:
                    from src.core.fixture_integrity import (
                        apply_integrity_to_payload as _apply_lt,
                        assess_analyze_result as _assess_lt,
                        assess_named_fixture as _assess_named_lt,
                        blocked_integrity_payload as _blocked_lt,
                    )

                    _lt_pre = _assess_named_lt(_lt_home, _lt_away)
                    if _lt_pre.is_blocked:
                        payload = _blocked_lt(_lt_pre, brain=brain)
                    else:
                        payload = await _run_analyze(
                            _lt_home, _lt_away, prefer_live=True, force_refresh=force_refresh
                        )
                        _lt_post = _assess_lt(
                            _lt_home,
                            _lt_away,
                            fixture_id=payload.get("fixture_id"),
                            is_partial=bool(payload.get("_partial")),
                            data_completeness=float(
                                ((payload.get("brain") or {}).get("inference") or {}).get(
                                    "data_completeness", 1.0
                                )
                            ),
                        )
                        payload = _apply_lt(payload, _lt_post)
                        if not _lt_post.is_blocked:
                            _save_analysis_context(ctx, payload, _lt_home, _lt_away)
                    logger.warning(
                        "[AUDIT] live_team_analysis: done match=%r status=%r found=%r",
                        payload.get("match"),
                        payload.get("fixture_status"),
                        payload.get("fixture_found"),
                    )
                else:
                    logger.warning(
                        "[AUDIT] live_team_analysis: %r not found in %d live matches",
                        _lt_team, len(_lt_list),
                    )
                    from src.brain import get_brain_meta as _gbm_lt
                    from src.core.inference_context import InferenceContext

                    _lt_ctx = InferenceContext(soft_mode=True)
                    _lt_ctx.register_failure(
                        "live_team_lookup",
                        f"{_lt_team} não está no feed ao vivo",
                        signal="fixture",
                    )
                    _lt_ctx.finalize()
                    payload = {
                        "intent": "live_team_analysis",
                        "match": None, "is_live": False, "status": "NotFound", "minute": None,
                        "executive_summary": (
                            f"**{_lt_team}** não está jogando ao vivo agora.\n\n"
                            f"A Aurora registrou a falha (Inference V2) e manteve a conversa "
                            f"com confiança reduzida.\n\n"
                            f"Se souber o adversário, diga:\n"
                            f"\"Analisar {_lt_team} x [adversário]\""
                        ),
                        "best_markets": [],
                        "confidence": {
                            "score": _lt_ctx.apply_to_score(2.0),
                            "label": "insufficient",
                            "explanation": (
                                f"Inference V2: time ausente ao vivo — "
                                f"penalidade −{_lt_ctx.total_penalty():.1f}"
                            ),
                            "data_sources": ["Feed ao vivo API-Football", "Inference Layer V2"],
                        },
                        "risk": {
                            "level": "Unknown",
                            "flags": list(_lt_ctx.missing_signals),
                            "invalidation_conditions": [],
                        },
                        "bankroll_recommendation": {
                            "recommended_stake_pct": 0.0, "method": "quarter-Kelly",
                            "examples": {}, "no_bet": True,
                            "reasoning": "Sem partida ao vivo identificada.",
                        },
                        "positive_factors": [], "negative_factors": [],
                        "historical_references": [],
                        "knowledge_notes": _lt_ctx.knowledge_notes_pt(),
                        "final_recommendation": (
                            f"Não encontrei {_lt_team} ao vivo. "
                            f"Tente: \"Analisar {_lt_team} x [adversário]\""
                        ),
                        "aurora_version": "Copilot v1.0",
                        "brain": {**_gbm_lt(), "inference": _lt_ctx.explainability()},
                    }
                logger.warning(
                    "[AUDIT] ctx_after: last_match=%r last_intent=%r",
                    ctx.get("last_match"), ctx.get("last_intent"),
                )

            elif intent == "live_opportunities":
                # FIX 2 — preserve existing ctx when user already has an active match.
                # Only seed ctx from the live list when no prior analysis is in session.
                _preserve_context = bool(ctx.get("last_match"))
                logger.warning(
                    "[AUDIT] live_opportunities: ctx_before=last_match=%r last_intent=%r"
                    " preserve_context=%s",
                    ctx.get("last_match"), ctx.get("last_intent"), _preserve_context,
                )
                payload = await _run_live()
                if not _preserve_context:
                    _live_ents = payload.get("entities", {})
                    _hn = _live_ents.get("live_home", "")
                    _an = _live_ents.get("live_away", "")
                    if _hn and _an:
                        _live_match_str = f"{_hn} x {_an}"
                        ctx["last_match"]  = _live_match_str
                        ctx["last_home"]   = _hn
                        ctx["last_away"]   = _an
                        ctx["last_intent"] = "live_opportunities"
                        logger.warning(
                            "[AUDIT] live_opportunities: seeded ctx.last_match=%r from top opportunity",
                            _live_match_str,
                        )
                    else:
                        logger.warning("[AUDIT] live_opportunities: no live matches — ctx.last_match NOT seeded")
                else:
                    logger.warning(
                        "[AUDIT] live_opportunities: ctx PRESERVED (last_match=%r last_intent=%r)",
                        ctx.get("last_match"), ctx.get("last_intent"),
                    )
                logger.warning(
                    "[AUDIT] ctx_after: last_match=%r last_intent=%r",
                    ctx.get("last_match"), ctx.get("last_intent"),
                )

            elif intent == "bankroll_review":
                payload = _run_bankroll()

            elif intent == "learning_recap":
                payload = _run_learning()

            elif intent == "knowledge_search":
                payload = _run_knowledge(entities.get("query", message))

            elif intent == "greeting":
                payload = _run_greeting()

            elif intent == "identity":
                payload = _run_identity()

            elif intent in {"capabilities", "assistant_capabilities"}:
                payload = _run_capabilities()

            elif intent == "help":
                payload = _run_help()

            else:
                payload = _run_fallback(message, intent)
                try:
                    from src.conversation.pipeline_trace import trace as _ptrace

                    _ptrace(
                        "FALLBACK",
                        source="run_fallback",
                        intent=intent,
                        fallback=True,
                    )
                except Exception:
                    pass

    except Exception as exc:
        logger.error("Copilot unified error [%s]: %s", intent, exc, exc_info=True)
        try:
            from src.conversation.pipeline_trace import trace as _ptrace

            _ptrace(
                "FALLBACK",
                source="outer_exception",
                intent=intent,
                error=type(exc).__name__,
                detail=exc,
                fallback=True,
            )
        except Exception:
            pass
        from fastapi import HTTPException as _HTTPExc
        from src.core.inference_context import InferenceContext

        is_404 = isinstance(exc, _HTTPExc) and exc.status_code == 404
        home_q = entities.get("home", "")
        away_q = entities.get("away", "")

        # Inference V2: convert outer abort into explained low-confidence response
        _octx = InferenceContext(soft_mode=True)
        _octx.register_failure(
            "copilot_outer",
            str(exc.detail if is_404 else exc),
            signal="fixture" if is_404 else "teams",
        )
        _octx.finalize()

        if is_404 and home_q and away_q:
            # Soft analyze — integrity guard still applies (no generic markets)
            try:
                from src.core.fixture_integrity import (
                    apply_integrity_to_payload as _apply_404,
                    assess_analyze_result as _assess_404,
                    assess_named_fixture as _assess_named_404,
                    blocked_integrity_payload as _blocked_404,
                )

                _pre404 = _assess_named_404(home_q, away_q)
                if _pre404.is_blocked:
                    payload = _blocked_404(_pre404, brain=brain)
                else:
                    payload = await _run_analyze(
                        home_q, away_q, prefer_live=False, force_refresh=force_refresh
                    )
                    _post404 = _assess_404(
                        home_q,
                        away_q,
                        fixture_id=payload.get("fixture_id"),
                        is_partial=bool(payload.get("_partial")),
                        data_completeness=float(
                            ((payload.get("brain") or {}).get("inference") or {}).get(
                                "data_completeness", 1.0
                            )
                        ),
                    )
                    payload = _apply_404(payload, _post404)
            except Exception:
                # Phase 8.4-A.7 — valid confrontation → preliminary, not hard refuse
                try:
                    from src.core.partial_analysis import (
                        allow_partial_analysis as _allow_pa_404,
                        build_preliminary_executive as _prelim_404,
                        detect_rate_limited as _rl_404,
                        resolve_preliminary_confidence as _pconf_404,
                    )

                    _rl = _rl_404(_octx) or _rl_404(
                        notes=[str(exc.detail if is_404 else exc)]
                    )
                    if _allow_pa_404(
                        entity_invalid=False,
                        fixture_quality="PARTIAL",
                        data_completeness=max(
                            0.22, float(_octx.data_completeness or 0.0)
                        ),
                        available_signals=["teams"]
                        + (["fixture"] if not is_404 else []),
                        rate_limited=_rl,
                    ):
                        _ps, _pl = _pconf_404(
                            _octx.apply_to_score(3.5),
                            data_completeness=0.25,
                            rate_limited=_rl,
                        )
                        summary = _prelim_404(
                            home_q,
                            away_q,
                            base_summary=None,
                            missing_signals=list(_octx.missing_signals or []),
                            available_signals=["teams"],
                            rate_limited=_rl,
                            confidence_label=_pl,
                        )
                        payload = {
                            "intent": intent,
                            "entities": {
                                **dict(entities or {}),
                                "home": home_q,
                                "away": away_q,
                                "fixture_quality": "PARTIAL",
                                "entity_invalid": False,
                                "preliminary_analysis": True,
                                "allow_partial_analysis": True,
                                "rate_limited": _rl,
                                "market_generation_enabled": True,
                            },
                            "match": f"{home_q} x {away_q}",
                            "status": "PARTIAL",
                            "is_live": False,
                            "minute": None,
                            "fixture_quality": "PARTIAL",
                            "fixture_status": "PARTIAL",
                            "executive_summary": summary,
                            "best_markets": [],
                            "confidence": {
                                "score": _ps,
                                "label": _pl,
                                "explanation": (
                                    "Análise preliminar — dados parciais"
                                    + ("; rate limit" if _rl else "")
                                ),
                                "data_sources": ["Inference Layer V2", "Partial Analysis"],
                            },
                            "risk": {
                                "level": "High",
                                "flags": list(_octx.missing_signals),
                                "invalidation_conditions": [
                                    "Completar estatísticas oficiais quando a API responder",
                                ],
                            },
                            "bankroll_recommendation": {
                                "recommended_stake_pct": 0.0,
                                "method": "quarter-Kelly",
                                "examples": {},
                                "no_bet": True,
                                "reasoning": "Dados parciais — sem stake.",
                            },
                            "final_recommendation": (
                                f"Leitura preliminar {home_q} x {away_q} "
                                f"(confiança {_pl})."
                            ),
                            "knowledge_notes": _octx.knowledge_notes_pt(),
                            "brain": {
                                **brain,
                                "inference": _octx.explainability(),
                            },
                        }
                    else:
                        raise RuntimeError("partial_not_allowed")
                except Exception:
                    summary = (
                        f"Não consegui localizar a partida **{home_q} x {away_q}** "
                        f"com dados completos.\n\n"
                        f"A Aurora registrou a falha (Inference V2) e manteve a conversa "
                        f"com confiança reduzida.\n\n"
                        f"**Sugestão:** use o nome oficial completo dos times."
                    )
                    payload = {
                        "intent":   intent,
                        "entities": entities,
                        "match":   f"{home_q} x {away_q}",
                        "status": "Partial", "is_live": False, "minute": None,
                        "executive_summary": summary,
                        "best_markets":      [],
                        "confidence": {
                            "score": _octx.apply_to_score(2.0),
                            "label": "insufficient",
                            "explanation": (
                                f"Inference V2: fixture ausente — "
                                f"penalidade −{_octx.total_penalty():.1f}"
                            ),
                            "data_sources": ["Inference Layer V2"],
                        },
                        "risk": {
                            "level": "High",
                            "flags": list(_octx.missing_signals),
                            "invalidation_conditions": [
                                "Confirmar nomes oficiais na API-Football",
                            ],
                        },
                        "bankroll_recommendation": {
                            "recommended_stake_pct": 0.0,
                            "method": "quarter-Kelly",
                            "examples": {},
                            "reasoning": "Sem dados completos para stake.",
                            "no_bet": True,
                        },
                        "positive_factors": [],
                        "negative_factors": [
                            "Fixture não resolvida — análise degradada.",
                        ],
                        "historical_references": [],
                        "knowledge_notes": _octx.knowledge_notes_pt(),
                        "final_recommendation": (
                            "Tente novamente com o nome oficial do time, "
                            "sem abreviações."
                        ),
                        "aurora_version": "Copilot v1.0",
                        "brain": {**brain, "inference": _octx.explainability()},
                    }
        else:
            summary = (
                "A Aurora encontrou um problema ao processar sua solicitação, "
                "registrou a falha e manteve a resposta ativa (Inference V2).\n\n"
                "Por favor, reformule ou tente novamente."
            )
            payload = {
                "intent":   intent,
                "entities": entities,
                "match":   None, "status": None, "is_live": False, "minute": None,
                "executive_summary": summary,
                "best_markets":      [],
                "confidence": {
                    "score": _octx.apply_to_score(1.0),
                    "label": "insufficient",
                    "explanation": (
                        f"Inference V2: erro de processamento — "
                        f"penalidade −{_octx.total_penalty():.1f}"
                    ),
                    "data_sources": ["Inference Layer V2"],
                },
                "risk": {
                    "level": "Unknown",
                    "flags": list(_octx.missing_signals),
                    "invalidation_conditions": [],
                },
                "bankroll_recommendation": {
                    "recommended_stake_pct": 0.0, "method": "quarter-Kelly",
                    "examples": {}, "reasoning": "Nenhuma aposta disponível.", "no_bet": True,
                },
                "positive_factors": [], "negative_factors": [],
                "historical_references": [],
                "knowledge_notes": _octx.knowledge_notes_pt(),
                "final_recommendation": (
                    "Tente novamente. Se o problema persistir, verifique o nome da partida."
                ),
                "aurora_version": "Copilot v1.0",
                "brain": {**brain, "inference": _octx.explainability()},
            }

    # ── LLM Conversational Layer (Phases 1–9) ────────────────────────────
    # Called ONLY when the LLM router decides it adds value.
    # Aurora's calculations are never replaced — only the narrative is enhanced.
    try:
        from src.core.conversation_llm import chat as _llm_chat
        from src.core.conversation_llm import enhance as _llm_enhance
        from src.core.conversation_llm import needs_llm as _needs_llm

        _ents_llm = dict((payload or {}).get("entities") or {})
        _meta_llm = dict((payload or {}).get("response_metadata") or {})
        _skip_llm_presence = bool(
            _ents_llm.get("skip_llm")
            or _ents_llm.get("emotional")
            or _ents_llm.get("human_presence")
            or _ents_llm.get("natural_conversation")
            or _ents_llm.get("profile_memory")
            or _meta_llm.get("skip_llm")
            or intent in {"emotional", "capabilities"}
        )
        if _skip_llm_presence:
            logger.warning(
                "[AUDIT] LLM skipped — presence/emotional/natural guard intent=%s",
                intent,
            )
        elif _needs_llm(intent, message, ctx):
            _blocked = bool(
                _ents_llm.get("markets_blocked")
                or payload.get("fixture_status") in ("NOT_FOUND", "FICTIONAL")
            )
            if _blocked:
                logger.warning(
                    "copilot: LLM skipped — Fixture Integrity Guard blocked markets"
                )
            else:
                has_structure = bool(payload.get("best_markets") or payload.get("positive_factors"))
                if has_structure:
                    # Enhance the narrative of a structured Aurora payload
                    payload = _llm_enhance(payload, message, ctx, intent)
                else:
                    # Pure conversational — replace entirely with LLM response
                    llm_payload = _llm_chat(message, ctx, intent, brain)
                    if llm_payload.get("executive_summary"):
                        # Merge: keep any structured fields from the rule engine
                        for k in ("executive_summary", "final_recommendation", "aurora_version"):
                            payload[k] = llm_payload[k]
    except Exception as _llm_exc:
        logger.warning("copilot: LLM layer skipped (%s) — using Aurora rule engine response", _llm_exc)

    # ── i18n: translate presentation layer to Brazilian Portuguese ───────
    # Pure presentation pass — translates labels/prose only. Numbers, odds,
    # probabilities, EV, Kelly sizing and all engine math are untouched.
    try:
        from src.core.i18n_pt import translate_report as _translate_pt

        payload = _translate_pt(payload)
    except Exception as _i18n_exc:
        logger.warning("copilot: i18n translation skipped (%s)", _i18n_exc)

    # ── Phase 6: Personality & Communication Layer (presentation only) ──
    # Cleanup internals, humanize, size control, tone, hooks.
    # Does NOT alter engines, EntityResolver, follow-up detection, or memory.
    # Phase 8.4-A.7 — skip polish on preliminary_analysis (sanitizer would
    # replace with generic "leitura cautelosa" and erase the prelim body).
    try:
        _ents_polish = (payload.get("entities") or {}) if isinstance(payload, dict) else {}
        if (
            _ents_polish.get("preliminary_analysis")
            or _ents_polish.get("continuity_followup")
            or _ents_polish.get("assistant_capabilities")
            or _ents_polish.get("assistant_kind") == "capabilities"
            or _ents_polish.get("sport_intent_authored")
            or _ents_polish.get("response_selector_skip_honesty")
        ):
            logger.warning(
                "[AUDIT] Personality: SKIPPED — preliminary/continuity/capabilities lock"
            )
        else:
            from src.communication import polish_payload as _polish

            payload = _polish(payload, message=message, intent=intent, ctx=ctx)
    except Exception as _pers_exc:
        logger.warning("copilot: personality layer skipped (%s)", _pers_exc)

    # Persist Aurora response turn
    try:
        _db_save_msg(
            session_id=session_id,
            role="aurora",
            content=(payload.get("executive_summary") or "")[:2000],
            intent=payload.get("intent", intent),
            entities={},
        )
    except Exception as _save_exc:
        logger.warning("copilot: failed to save aurora msg: %s", _save_exc)

    # Persist updated conversation context (memory + SQLite)
    try:
        meta = (payload or {}).get("response_metadata") or {}
        if meta:
            ctx["last_response_metadata"] = meta
        conversation_manager.save(session_id, ctx)
    except Exception as _ctx_exc:
        logger.warning("copilot: failed to save context: %s", _ctx_exc)

    # Contextual follow-up suggestions (pure function, never raises)
    try:
        suggested_follow_ups = _suggest_follow_ups(intent, ctx, payload)
    except Exception:
        suggested_follow_ups = []

    # Integrity: strip MatchHeader / markets only for INVALID (fiction / unknown).
    # PARTIAL keeps logos, estimated markets and fallback analysis.
    _fx_status = payload.get("fixture_status") or (payload.get("entities") or {}).get(
        "fixture_status"
    )
    _fx_quality = payload.get("fixture_quality") or (payload.get("entities") or {}).get(
        "fixture_quality"
    )
    _invalid = (
        _fx_quality == "INVALID"
        or _fx_status in ("NOT_FOUND", "FICTIONAL")
        or (payload.get("entities") or {}).get("entity_invalid") is True
    )
    _header_blocked = bool(
        (payload.get("response_metadata") or {}).get("header_blocked")
        or _invalid
    )
    if _header_blocked or _invalid:
        payload["match_card"] = None
    if _invalid:
        payload["best_markets"] = []
        payload["fixture_found"] = False

    # ── 0z. Deep Reasoning + Credibility (v4.5/v4.4) — final stamp ────────
    # After integrity. Additive. Fail-open. Does not touch engines/CRL/CIL modules.
    # Phase 8.4-A.8 — never let credibility overwrite continuity short follow-ups
    # (chosen_answer often collapses to "?" / crumbs).
    try:
        _ents_cred = (payload.get("entities") or {}) if isinstance(payload, dict) else {}
        if (
            _ents_cred.get("continuity_followup")
            or (
                _ents_cred.get("followup_before_fallback")
                and _ents_cred.get("rewrite_locked")
            )
            or _ents_cred.get("assistant_capabilities")
            or _ents_cred.get("assistant_kind") == "capabilities"
            or _ents_cred.get("sport_intent_authored")
            or _ents_cred.get("response_selector_skip_honesty")
        ):
            logger.warning(
                "[AUDIT] CredibilityLayer: SKIPPED text upgrade — "
                "continuity/capabilities lock"
            )
        else:
            from src.conversation.deep_reasoning import run_deep_reasoning as _v45_deep_final
            from src.conversation.reflection_credibility import (
                apply_credibility_to_payload as _v44_cred,
                ReflectionResult,
            )

            _draft = str(payload.get("executive_summary") or "")
            _refl_final = ctx.get("conversation_reflection")
            if isinstance(_refl_final, dict) and _refl_final.get("user_real_intent"):
                try:
                    _rr = ReflectionResult(
                        user_real_intent=str(_refl_final.get("user_real_intent") or ""),
                        possible_answers=list(_refl_final.get("possible_answers") or []),
                        chosen_answer=_refl_final.get("chosen_answer"),
                        why_this_answer=str(_refl_final.get("why_this_answer") or ""),
                        confidence=float(_refl_final.get("confidence") or 0),
                        position=_refl_final.get("position") or "none",
                        risks=list(_refl_final.get("risks") or []),
                        display_mode=_refl_final.get("display_mode") or "FOLLOW_UP",
                        thinking_label=_refl_final.get("thinking_label"),
                        humanized_reply=_refl_final.get("humanized_reply"),
                        signals=list(_refl_final.get("signals") or []),
                    )
                except Exception:
                    _rr = _v45_deep_final(message, ctx, _draft)
            else:
                _rr = _v45_deep_final(message, ctx, _draft)
            payload = _v44_cred(payload, _rr, ctx)
            # Attach deep reflection structure into metadata (presentation-safe)
            try:
                _deep = ctx.get("deep_reflection") or (
                    (_refl_final or {}).get("deep")
                    if isinstance(_refl_final, dict)
                    else None
                )
                if _deep:
                    _meta = dict(payload.get("response_metadata") or {})
                    _meta["deep_reflection"] = _deep
                    payload["response_metadata"] = _meta
            except Exception:
                pass
            logger.warning(
                "[AUDIT] CredibilityLayer: mode=%s show_confidence=%s thinking=%r",
                (payload.get("response_metadata") or {})
                .get("credibility", {})
                .get("display_mode"),
                (payload.get("response_metadata") or {})
                .get("credibility", {})
                .get("show_confidence"),
                (payload.get("response_metadata") or {})
                .get("credibility", {})
                .get("thinking_label"),
            )
    except Exception as _cred_exc:
        logger.warning("copilot: credibility layer skipped (%s)", _cred_exc)

    # ── 0z1a. Web Intelligence (v4.7) — optional enrich, fail-open ─────────
    try:
        from src.conversation.web_intelligence import (
            maybe_enrich_with_web as _v47_web,
        )

        payload = await _v47_web(
            message,
            payload,
            intent=intent,
            ctx=ctx,
        )
    except Exception as _web_exc:
        logger.warning("copilot: web intelligence skipped (%s)", _web_exc)

    # ── 0z1b. Response Formatter (v4.7) — last-mile humanization ──────────
    try:
        from src.conversation.response_formatter import (
            apply_formatter_to_payload as _v47_fmt,
        )

        payload = _v47_fmt(payload, prefs=_conv_prefs, ctx=ctx)
    except Exception as _fmt_exc:
        logger.warning("copilot: response formatter skipped (%s)", _fmt_exc)

    # ── 0z1b2. Personality prefs (emoji/enthusiasm/structure/detail) ───────
    try:
        from src.conversation.presence_humanization import (
            apply_personality_to_payload as _v48_pers,
        )

        payload = _v48_pers(payload, _conv_prefs)
    except Exception as _pers2_exc:
        logger.warning("copilot: personality apply skipped (%s)", _pers2_exc)

    # ── 0z1b3. Response Review (template → enrich) ────────────────────────
    try:
        from src.conversation.turn_ownership import is_rewrite_locked as _own_locked_rev

        if isinstance(payload, dict) and _own_locked_rev(payload):
            logger.warning("[AUDIT] Ownership: ResponseReview skipped — locked")
        else:
            from src.conversation.response_review import (
                review_and_enrich_payload as _v48_review,
            )

            payload = _v48_review(
                payload, message=message, ctx=ctx, prefs=_conv_prefs
            )
    except Exception as _rev_exc:
        logger.warning("copilot: response review skipped (%s)", _rev_exc)

    # ── 0z1b4. Never-empty guard ──────────────────────────────────────────
    try:
        from src.conversation.turn_ownership import is_rewrite_locked as _own_locked_ne

        if isinstance(payload, dict) and _own_locked_ne(payload):
            # Owned replies already have text — do not inject Copa/team filler
            pass
        else:
            from src.conversation.intelligence_fallback import (
                ensure_non_empty_payload as _v48_nonempty,
            )

            payload = _v48_nonempty(
                payload, message=message, ctx=ctx, prefs=_conv_prefs
            )
    except Exception as _ne_exc:
        logger.warning("copilot: non-empty guard skipped (%s)", _ne_exc)

    # ── 0z1b5. Thinking Delay + Response Reflection ───────────────────────
    try:
        from src.conversation.human_inference import (
            repair_unintelligent_reply as _hie_repair,
            thinking_delay_ok as _hie_delay_ok,
        )
        from src.conversation.response_reflection import (
            reflect_response as _ri_reflect,
        )

        if isinstance(payload, dict):
            _ents_td = dict(payload.get("entities") or {})
            # Phase 7.4: never rewrite locked owners (NRE/HCE/META/…)
            if (
                _ents_td.get("rewrite_locked")
                or _ents_td.get("preliminary_analysis")
                or _ents_td.get("turn_owner") in {
                    "NRE",
                    "HCE",
                    "META",
                    "GA",
                    "PROFILE",
                    "EMOTIONAL",
                }
                or _ents_td.get("general_assistant")
                or _ents_td.get("human_conversation")
                or not _sport_ok
            ):
                logger.warning(
                    "[AUDIT] ThinkingDelay: SKIPPED — ownership/non-sport"
                    "/preliminary"
                )
            else:
                _sum = str(payload.get("executive_summary") or "")
                _ref = _ri_reflect(_sum, question=message)
                if (
                    not _hie_delay_ok(_sum, ctx)
                    or _ref.blocked
                    or (not _ref.ok and _ents_td.get("opinion_time"))
                ):
                    _fixed = None
                    try:
                        from src.conversation.response_planner import (
                            plan_response as _ri_plan,
                        )
                        from src.conversation.response_templates import (
                            render_forced_useful as _ri_forced,
                        )

                        _plan = _ri_plan(message, ctx)
                        if not _plan.team:
                            _plan.team = (
                                ((ctx.get("human_inference") or {}).get("team"))
                                or ((ctx.get("deep_thinking") or {}).get("topic_team"))
                            )
                        _fixed = _ri_forced(_plan)
                    except Exception:
                        _fixed = _hie_repair(_sum, ctx)
                    try:
                        from src.conversation.confidence_rewriter import (
                            rewrite_confidence_tone as _ri_conf,
                        )

                        _fixed = _ri_conf(_fixed)
                    except Exception:
                        pass
                    payload["executive_summary"] = _fixed
                    payload["final_recommendation"] = _fixed
                    _ents_td["response_intelligence_repair"] = True
                    payload["entities"] = _ents_td
                    logger.warning(
                        "[AUDIT] ThinkingDelay: repaired unintelligent reply reasons=%s",
                        _ref.reasons,
                    )
    except Exception as _td_exc:
        logger.warning("copilot: thinking delay skipped (%s)", _td_exc)

    # ── 0z1c. Emotional hard-guard ABSOLUTE (after LLM / polish / formatter)
    try:
        from src.conversation.emotional_presence import (
            enforce_emotional_hard_guard as _v47_emo_guard,
        )

        payload = _v47_emo_guard(payload, message=message, ctx=ctx)
    except Exception as _emo_g_exc:
        logger.warning("copilot: emotional hard-guard skipped (%s)", _emo_g_exc)

    # ── 0z1c2. Natural Response Filter + perceived intelligence (non-sport) ─
    try:
        _ents_nrf = (payload.get("entities") or {}) if isinstance(payload, dict) else {}
        try:
            from src.conversation.pipeline_trace import (
                trace_owner as _town,
                trace_payload as _tpay,
            )

            _tpay("PAYLOAD_BEFORE", "late_nrf", payload if isinstance(payload, dict) else None)
            _town("before_late_nrf", payload if isinstance(payload, dict) else None)
        except Exception:
            pass
        # Phase 7.4: owned/locked replies — no meaning rewrite
        if isinstance(payload, dict) and (
            _ents_nrf.get("rewrite_locked")
            or _ents_nrf.get("human_conversation")
            or _ents_nrf.get("turn_owner") in {"NRE", "HCE", "META"}
        ):
            try:
                from src.conversation.pipeline_trace import trace as _ptrace

                _ptrace(
                    "NRF_OUTPUT",
                    action="skipped_owned",
                    owner=_ents_nrf.get("turn_owner"),
                    locked=_ents_nrf.get("rewrite_locked"),
                )
            except Exception:
                pass
        elif isinstance(payload, dict) and (
            not _sport_ok or _ents_nrf.get("general_assistant")
        ):
            from src.conversation.natural_response_filter import (
                filter_or_regenerate as _nrf_final,
            )

            _mi_name = (
                ((_master.intent if _master else None) or "")
                or str((ctx.get("master_intent") or {}).get("intent") or "GENERAL_CHAT")
            )
            _sum_f = str(payload.get("executive_summary") or "")
            _regen = None
            try:
                from src.conversation.dialog_mode import progress_act_text as _dm_prog
                from src.conversation.general_assistant import (
                    reply_math as _ga_math,
                    reply_small_talk as _ga_st,
                    reply_system as _ga_sys,
                )

                if _mi_name == "MATH_QUERY":
                    _regen = _ga_math(message)
                elif _mi_name == "SMALL_TALK":
                    _regen = _ga_st(message)
                elif _mi_name == "SYSTEM_QUERY":
                    _regen = _ga_sys(message)
                else:
                    # P1-B — never regenerate with sticky Entendi
                    _regen = _dm_prog(message)
            except Exception:
                _regen = (
                    "Ainda não peguei o objetivo. "
                    "Quer analisar um jogo, tirar uma dúvida, ou só conversar?"
                )
            _clean = _nrf_final(
                _sum_f,
                master_intent=_mi_name,
                ctx=ctx,
                regenerate=_regen,
            )
            payload["executive_summary"] = _clean
            payload["final_recommendation"] = _clean
        try:
            from src.conversation.pipeline_trace import (
                trace_owner as _town,
                trace_payload as _tpay,
            )

            _tpay("PAYLOAD_AFTER", "late_nrf", payload if isinstance(payload, dict) else None)
            _town("after_late_nrf", payload if isinstance(payload, dict) else None)
        except Exception:
            pass
    except Exception as _nrf_exc:
        logger.warning("copilot: natural response filter skipped (%s)", _nrf_exc)

    # ── 0z1c3. Perceived Intelligence Engine — fact→interpretation→conclusion
    # Expression of reasoning only; never invents evidence. Skips social/NRE.
    # Phase 7.4: mark SPORT owner when analysis-shaped and not already locked.
    try:
        from src.conversation.perceived_intelligence_engine import (
            apply_perceived_intelligence as _pie_apply,
        )
        from src.conversation.turn_ownership import (
            is_rewrite_locked as _own_locked_pie,
            mark_sport_owner as _own_sport,
        )

        _ents_pie = (payload.get("entities") or {}) if isinstance(payload, dict) else {}
        # Phase 8.4-A.7 — never let PIE replace a preliminary_analysis executive
        if isinstance(payload, dict) and _ents_pie.get("preliminary_analysis"):
            logger.warning("[AUDIT] PIE: skipped — preliminary_analysis lock")
        elif isinstance(payload, dict) and not _own_locked_pie(payload):
            if (
                payload.get("best_markets")
                or _ents_pie.get("has_analysis")
                or payload.get("positive_factors")
                or payload.get("is_live")
            ):
                payload = _own_sport(payload) or payload
            payload = _pie_apply(message, payload, ctx) or payload
    except Exception as _pie_exc:
        logger.warning("copilot: PIE skipped (%s)", _pie_exc)

    # ── 0z1c4. HCE — persist conversational thread after reply ────────────
    try:
        from src.conversation.human_conversation_engine import (
            note_hce_after_response as _hce_note,
        )

        _hce_note(ctx, message, payload if isinstance(payload, dict) else None)
        try:
            from src.conversation.conversation_repair import (
                note_repair_memory as _repair_note,
            )

            _repair_note(ctx, message, payload if isinstance(payload, dict) else None)
        except Exception as _repair_note_exc:
            logger.warning("copilot: repair memory note skipped (%s)", _repair_note_exc)
        # 8.4-A.22 — after hard fiction/jump reset, do not re-bootstrap sport notes
        _skip_sport_bootstrap = False
        try:
            from src.conversation.fiction_context_jump_guard import (
                should_skip_sport_bootstrap as _fcj_skip,
            )

            _skip_sport_bootstrap = bool(_fcj_skip(ctx))
        except Exception:
            _skip_sport_bootstrap = bool(ctx.get("fiction_context_hard_reset"))
        try:
            from src.conversation.short_conversation_memory import (
                note_short_memory as _sm_note,
            )

            if not _skip_sport_bootstrap:
                _sm_note(ctx, message, payload if isinstance(payload, dict) else None)
        except Exception as _sm_note_exc:
            logger.warning("copilot: short memory note skipped (%s)", _sm_note_exc)
        try:
            from src.conversation.conversation_continuity import (
                note_continuity as _cont_note,
            )

            if not _skip_sport_bootstrap:
                _cont_note(ctx, message, payload if isinstance(payload, dict) else None)
            else:
                logger.warning(
                    "[AUDIT] Continuity: SKIP note — fiction/hard-jump reset"
                )
        except Exception as _cont_note_exc:
            logger.warning("copilot: continuity note skipped (%s)", _cont_note_exc)
        try:
            from src.conversation.pronoun_continuity import (
                note_pronoun_memory as _pronoun_note,
            )

            if not _skip_sport_bootstrap:
                _pronoun_note(ctx, message, payload if isinstance(payload, dict) else None)
        except Exception as _pronoun_note_exc:
            logger.warning("copilot: pronoun memory note skipped (%s)", _pronoun_note_exc)
        try:
            from src.conversation.ownership_stability import (
                note_owner_after_response as _own_note,
                stamp_payload_observability as _own_stamp,
            )

            if not _skip_sport_bootstrap:
                _own_note(ctx, payload if isinstance(payload, dict) else None)
            payload = _own_stamp(
                payload if isinstance(payload, dict) else None, ctx
            )
        except Exception as _own_note_exc:
            logger.warning("copilot: ownership stability note skipped (%s)", _own_note_exc)
        try:
            from src.conversation.sport_continuity_guard import (
                note_sport_anchor_after_response as _scg_note,
            )

            if not _skip_sport_bootstrap:
                payload = _scg_note(
                    ctx,
                    message,
                    payload if isinstance(payload, dict) else None,
                )
            else:
                logger.warning(
                    "[AUDIT] SportAnchor: SKIP note — fiction/hard-jump reset"
                )
        except Exception as _scg_note_exc:
            logger.warning("copilot: sport continuity note skipped (%s)", _scg_note_exc)
        try:
            from src.conversation.ambiguous_context_guard import (
                note_after_clarification as _acg_note,
                stamp_payload_observability as _acg_stamp,
            )

            _acg_note(ctx, message, payload if isinstance(payload, dict) else None)
            payload = _acg_stamp(
                payload if isinstance(payload, dict) else None, ctx
            )
        except Exception as _acg_note_exc:
            logger.warning("copilot: ambiguous context note skipped (%s)", _acg_note_exc)
        try:
            from src.conversation.fiction_context_jump_guard import (
                note_after_response as _fcj_note,
            )

            payload = _fcj_note(
                ctx,
                message,
                payload if isinstance(payload, dict) else None,
            )
        except Exception as _fcj_note_exc:
            logger.warning("copilot: fiction/jump note skipped (%s)", _fcj_note_exc)
        # CSL-001 — façade slot update (after sport notes; never touches FROZEN modules)
        try:
            from src.conversation.conversation_state_layer import (
                note_csl_after_response as _csl_note,
            )

            if not _skip_sport_bootstrap:
                payload = _csl_note(
                    ctx,
                    message,
                    payload if isinstance(payload, dict) else None,
                )
        except Exception as _csl_note_exc:
            logger.warning("copilot: CSL note skipped (%s)", _csl_note_exc)
        # INTENT-001 — stamp sport intent / skill on entities
        try:
            from src.conversation.sport_intent_layer import (
                note_sport_intent_on_payload as _sil_note,
            )

            payload = _sil_note(ctx, payload if isinstance(payload, dict) else None)
        except Exception as _sil_note_exc:
            logger.warning("copilot: sport intent note skipped (%s)", _sil_note_exc)
        try:
            from src.conversation.frustration_observability import (
                note_frustration_observability as _frust_note,
            )

            payload = _frust_note(
                ctx, message, payload if isinstance(payload, dict) else None
            )
        except Exception as _frust_note_exc:
            logger.warning(
                "copilot: frustration observability skipped (%s)", _frust_note_exc
            )
        try:
            from src.conversation.llm_judge_observability import (
                note_llm_judge_observability as _judge_note,
            )

            payload = _judge_note(
                ctx, message, payload if isinstance(payload, dict) else None
            )
        except Exception as _judge_note_exc:
            logger.warning(
                "copilot: llm judge observability skipped (%s)", _judge_note_exc
            )
        try:
            conversation_manager.save(session_id, ctx)
        except Exception:
            pass
    except Exception as _hce_note_exc:
        logger.warning("copilot: HCE note skipped (%s)", _hce_note_exc)

    # ── 0z2. Prediction / Experience Memory (v4.5) — PASSIVE store only ────
    try:
        from src.conversation.prediction_memory import (
            maybe_store_from_turn as _v45_mem_store,
        )

        _pid = _v45_mem_store(
            message=message,
            payload=payload,
            ctx=ctx,
            session_id=session_id,
            reflection=ctx.get("conversation_reflection")
            if isinstance(ctx.get("conversation_reflection"), dict)
            else None,
        )
        if _pid:
            _meta = dict(payload.get("response_metadata") or {})
            _meta["prediction_id"] = _pid
            payload["response_metadata"] = _meta
            logger.warning("[AUDIT] PredictionMemory: saved id=%s", _pid)
    except Exception as _mem_exc:
        logger.warning("copilot: prediction memory skipped (%s)", _mem_exc)

    # ── DEBUG audit block (optional) ─────────────────────────────────────
    try:
        from src.core.debug_audit import attach_debug_to_payload as _attach_debug

        payload = _attach_debug(payload, enabled=debug_mode)
    except Exception as _dbg_exc:
        logger.warning("copilot: debug audit skipped (%s)", _dbg_exc)
        payload.pop("_audit", None)
        if not debug_mode:
            payload.pop("debug", None)

    _out_quality = payload.get("fixture_quality") or _fx_quality
    _out_found = payload.get("fixture_found")
    if _out_found is None:
        _out_found = False if _invalid else None

    # Temporary audit identity — presentation only, no integrity/market changes
    try:
        from src.core.deploy_identity import deploy_identity_dict as _deploy_id

        _identity = _deploy_id()
    except Exception:
        _identity = {"backend_commit": "unknown", "frontend_commit": "unknown"}

    # Phase 8.4-A.4 — stamp finalize forensics onto entities (temp audit only)
    try:
        if isinstance(payload, dict):
            _fe = dict(payload.get("entities") or {})
            _snap = (
                dict(ctx.get("_forensics_84a4") or {})
                if isinstance(ctx, dict)
                else {}
            )
            for _fk, _fv in _snap.items():
                _fe.setdefault(_fk, _fv)
            if "response_type_before_finalize" not in _fe and _snap.get(
                "response_type_before_finalize"
            ):
                _fe["response_type_before_finalize"] = _snap.get(
                    "response_type_before_finalize"
                )
            _fe["response_type_after_finalize"] = _fe.get("response_type")
            _fe["final_summary_prefix"] = str(
                payload.get("executive_summary") or ""
            )[:120]
            payload["entities"] = _fe
            entities = _fe
            logger.warning(
                "[AUDIT] Forensics84a4 FINAL: path=%s import_ok=%s stage=%s "
                "before=%s after=%s overwrite=%s commit=%s",
                _fe.get("team_opinion_path"),
                _fe.get("match_opinion_import_ok"),
                _fe.get("renderer_stage"),
                _fe.get("response_type_before_finalize"),
                _fe.get("response_type_after_finalize"),
                _fe.get("overwrite_by"),
                _identity.get("backend_commit"),
            )
    except Exception as _fe_exc:
        logger.warning("copilot: forensics84a4 finalize skipped (%s)", _fe_exc)

    # P2.5 — stamp SRF / honesty / confidence explainability (presentation only)
    try:
        if isinstance(payload, dict):
            from src.core.entity_resolver_v2 import stamp_bind_on_payload as _ev2_stamp
            from src.conversation.partial_inference_honesty import (
                apply_honesty_to_payload as _p25_honesty,
            )
            from src.conversation.confidence_explainability import (
                apply_confidence_explanation as _p25_explain,
            )

            payload = _ev2_stamp(payload, ctx, message) or payload
            payload = _p25_honesty(payload, ctx, user_message=message) or payload
            payload = _p25_explain(payload, ctx) or payload
            entities = dict(payload.get("entities") or entities or {})
    except Exception as _p25_exc:
        logger.warning("copilot: P2.5 enrich skipped (%s)", _p25_exc)

    # Phase 7.9-A P0-1 — defensive soft sections (anti-KeyError only)
    try:
        from src.conversation.ensure_soft_sections import (
            ensure_soft_sections as _ensure_soft,
        )

        if isinstance(payload, dict):
            payload = _ensure_soft(payload) or payload
    except Exception as _soft_exc:
        logger.warning("copilot: ensure_soft_sections skipped (%s)", _soft_exc)

    try:
        from src.conversation.pipeline_trace import (
            snapshot_payload as _psnap,
            trace as _ptrace,
        )

        _final = _psnap(payload if isinstance(payload, dict) else None)
        _ptrace(
            "FINAL_RESPONSE",
            intent=_final.get("intent") or intent,
            engine=_final.get("owner") or _final.get("assistant_kind") or _final.get("hce_kind"),
            fallback=bool(_final.get("fallback")),
            final_source=(
                "fallback"
                if _final.get("fallback")
                else (_final.get("owner") or "payload")
            ),
            has_confidence=_final.get("has_confidence"),
            locked=_final.get("locked"),
            summary_prefix=_final.get("summary_prefix"),
            routing_confidence=routing_confidence,
        )
        try:
            from src.conversation.turn_ownership import log_final_source as _own_final_src

            _own_final_src(
                payload if isinstance(payload, dict) else None,
                lock_moment="pre_response",
            )
        except Exception:
            pass
    except Exception:
        pass

    # Phase 8.4-A.8 — restore continuity draft if late layers wiped it to "?"
    try:
        from src.conversation.conversation_continuity import (
            restore_continuity_draft as _cont_restore,
        )

        payload = _cont_restore(payload) or payload
    except Exception:
        pass

    # P2.5-S — ensure sport-owned payloads expose dialog_mode=SPORT (not null/UNKNOWN)
    try:
        if isinstance(payload, dict):
            from src.conversation.sport_understanding import (
                enrich_sport_entities as _su_final,
                should_force_sport_mode as _su_force_final,
            )

            _ents_f = dict(payload.get("entities") or {})
            _owner_f = str(_ents_f.get("turn_owner") or "").upper()
            _intent_f = str(payload.get("intent") or intent or "")
            _mi_f = (
                (_master.intent if _master else None)
                or str((ctx.get("master_intent") or {}).get("intent") or "")
            )
            _sport_owned = (
                _owner_f == "SPORT"
                or _intent_f in {"analyze_match", "follow_up", "live_team_analysis"}
                or _ents_f.get("p25_sport_understanding")
                or _ents_f.get("team_opinion_path")
                or _su_force_final(message, ctx, master_intent=_mi_f)
            )
            if _sport_owned and str(_ents_f.get("dialog_mode") or "").upper() not in {
                "FICTION",
                "REPAIR",
                "IDENTITY",
            }:
                _ents_f = _su_final(_ents_f, message)
                payload["entities"] = _ents_f
                entities = _ents_f
    except Exception as _su_final_exc:
        logger.warning("copilot: P25 final sport stamp skipped (%s)", _su_final_exc)

    return CopilotResponse(
        intent             = payload["intent"],
        entities           = payload.get("entities", entities),
        request_id         = request_id,
        generated_at       = _now_iso(),
        session_id         = session_id,
        routing_confidence = routing_confidence,
        match              = payload.get("match"),
        status             = payload.get("status"),
        is_live            = payload.get("is_live", False),
        minute             = payload.get("minute"),
        match_card         = _parse_match_card_model(payload.get("match_card")),
        fixture_status     = (
            str(_fx_status)
            if _fx_status in ("FOUND", "PARTIAL", "NOT_FOUND", "FICTIONAL")
            else None
        ),
        fixture_found      = (
            bool(_out_found) if isinstance(_out_found, bool) else None
        ),
        fixture_quality    = (
            str(_out_quality)
            if _out_quality in ("VALID", "PARTIAL", "INVALID")
            else None
        ),
        backend_commit     = _identity.get("backend_commit"),
        frontend_commit    = _identity.get("frontend_commit"),

        executive_summary       = payload["executive_summary"],
        best_markets            = [MarketEntry(**m) for m in payload.get("best_markets", [])],
        confidence              = ConfidenceSection(**payload["confidence"]),
        risk                    = RiskSection(**payload["risk"]),
        bankroll_recommendation = BankrollSection(**payload["bankroll_recommendation"]),
        positive_factors        = payload.get("positive_factors", []),
        negative_factors        = payload.get("negative_factors", []),
        historical_references   = payload.get("historical_references", []),
        knowledge_notes         = payload.get("knowledge_notes", []),
        final_recommendation    = payload["final_recommendation"],
        aurora_version          = payload.get("aurora_version", "Copilot v1.0"),
        brain                   = payload.get("brain", {}),
        suggested_follow_ups    = suggested_follow_ups,
        response_metadata       = payload.get("response_metadata") or {},
        debug                   = payload.get("debug") if debug_mode else None,
    )
