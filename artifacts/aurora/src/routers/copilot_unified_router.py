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


async def _run_analyze(home: str, away: str, prefer_live: bool = False) -> dict:
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
    data   = await analyze_fixture(
        home=home, away=away, prefer_live=prefer_live, soft=True,
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
        conf_score=adj_score,
        conf_label=_conf_label(adj_score),
        stake_pct=stake_pct,
        risk_level=report.risk_level if not is_partial else "High",
        best_ev=best_ev,
    )
    if is_partial:
        final_rec = (
            f"Análise parcial para **{hn} x {an}**: a partida não foi confirmada "
            f"na API. Confiança ajustada para {adj_score:.1f}/10. "
            f"Tente o nome oficial dos times para dados completos. " + final_rec
        )

    conf_explanation = report.confidence_explanation or ""
    if ictx.total_penalty() > 0:
        conf_explanation = (
            f"{conf_explanation} "
            f"[Inference V2: completude {ictx.data_completeness * 100:.0f}%, "
            f"penalidade −{ictx.total_penalty():.1f}, "
            f"score {raw_score:.1f}→{adj_score:.1f}]"
        ).strip()

    executive = report.executive_summary
    if is_partial:
        executive = (
            f"**Dados parciais** para {hn} x {an}. "
            f"A Aurora continuou a análise com confiança reduzida em vez de abortar.\n\n"
            + (executive or "")
        )

    brain_meta = get_brain_meta()
    brain_meta = {
        **brain_meta,
        "inference": ictx.explainability(),
    }

    return {
        "intent":    "analyze_match",
        "entities":  {"home": hn, "away": an, "league": league},
        "match":     report.match or f"{hn} x {an}",
        "status":    final_status,
        "is_live":   final_is_live,
        "minute":    final_minute,

        "executive_summary": executive,
        "best_markets":      best_markets,

        "confidence": {
            "score":        adj_score,
            "label":        _conf_label(adj_score),
            "explanation":  conf_explanation,
            "data_sources": data_sources,
        },
        "risk": {
            "level":                  "High" if is_partial else report.risk_level,
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


async def _run_live() -> dict:
    """Live opportunities — powered by Live Intelligence Engine v1.0."""
    from src.brain import get_brain_meta
    from src.core.live_intelligence_engine import build_live_payload
    from src.routers.live import _build_live_response

    live     = await _build_live_response()
    fixtures = live.get("matches", [])   # processed format from live.py
    return build_live_payload(fixtures, get_brain_meta())


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
    from src.brain import get_brain_meta
    return {
        "intent":   "capabilities",
        "entities": {},
        "match":   None, "status": None, "is_live": False, "minute": None,
        "executive_summary": (
            "Aqui está o que posso fazer por você:\n\n"
            "**Análise de partidas**\n"
            "→ *\"Analisar Arsenal x Chelsea\"* ou *\"PSG contra Bayern\"*\n"
            "Entrego: recomendação principal, probabilidades dos mercados, valor esperado (EV), "
            "risco, fatores positivos/negativos, stake pelo Kelly e condições de invalidação.\n\n"
            "**Oportunidades ao vivo**\n"
            "→ *\"Melhores oportunidades ao vivo\"* ou *\"Jogos ao vivo\"*\n"
            "Vejo todas as partidas em andamento e destaco as melhores apostas em tempo real.\n\n"
            "**Revisão de banca**\n"
            "→ *\"Como está minha banca?\"* ou *\"ROI atual\"*\n"
            "Mostro desempenho histórico, acertos, ROI e ajustes de risco por mercado.\n\n"
            "**Aprendizado**\n"
            "→ *\"O que a Aurora aprendeu hoje?\"* ou *\"Mostrar histórico\"*\n"
            "Resumo de precisão e lições dos resultados recentes.\n\n"
            "**Base de conhecimento**\n"
            "→ *\"O que você sabe sobre BTTS?\"* ou *\"Explique escanteios\"*\n"
            "Consulta às 40 regras metodológicas de apostas da Aurora.\n\n"
            "**Linguagem natural** — fala comigo normalmente, sem comandos exatos."
        ),
        "best_markets": [],
        "confidence": {"score": 0.0, "label": "insufficient", "explanation": "Lista de capacidades.", "data_sources": []},
        "risk": {"level": "Unknown", "flags": [], "invalidation_conditions": []},
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0, "method": "quarter-Kelly",
            "examples": {}, "no_bet": True,
            "reasoning": "Nenhuma aposta recomendada em consulta de capacidades.",
        },
        "positive_factors":      [],
        "negative_factors":      [],
        "historical_references": [],
        "knowledge_notes": [
            "Análise → \"Analisar [Casa] x [Fora]\"",
            "Ao vivo → \"Melhores oportunidades ao vivo\"",
            "Banca → \"Como está minha banca?\" / \"ROI atual\"",
            "Aprendizado → \"O que a Aurora aprendeu hoje?\"",
            "Conhecimento → \"O que você sabe sobre [mercado]?\"",
            "Identidade → \"Quem é você?\" / \"O que é a Aurora?\"",
        ],
        "final_recommendation": (
            "Escolha qualquer um dos recursos acima. Para começar: "
            "**\"Analisar [Time da Casa] x [Time Visitante]\"**"
        ),
        "aurora_version": "Copilot v1.0",
        "brain":          get_brain_meta(),
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
        "• **Analisar Arsenal x Chelsea** — análise completa de uma partida\n"
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
    """
    analysis = {k: v for k, v in payload.items() if k not in ("brain", "aurora_version")}
    match = payload.get("match") or f"{home} x {away}"
    ctx["last_home"]     = home
    ctx["last_away"]     = away
    ctx["last_match"]    = match
    ctx["last_fixture"]  = match
    ctx["last_intent"]   = "analyze_match"
    ctx["last_analysis"] = analysis
    ctx["last_market"]   = analysis.get("best_markets")
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

    message = body.message.strip()

    # ── Session management ────────────────────────────────────────────────
    session_id = body.session_id or secrets.token_hex(8)
    _db_create(session_id)
    # Phase 5B: memory cache first, SQLite fallback
    ctx   = conversation_manager.get(session_id) or {}
    brain = get_brain_meta()

    # Silently extract + update user profile from this message
    old_profile = ctx.get("user_profile", {})
    new_profile = _extract_profile(message, old_profile)
    if new_profile != old_profile:
        ctx["user_profile"] = new_profile

    request_id = secrets.token_hex(4)
    intent: str = "unknown"
    entities: dict = {}
    routing_confidence = 0.0
    payload: dict | None = None
    skipped_nl = False

    # ── 0. QuickFollowUpGate (BEFORE nl_router) — Phase 5B economy ────────
    # If we already have a fixture in context and the message is a follow-up,
    # resolve from last_analysis without NL / EntityResolver / full analyze.
    #
    # LIMITATION: Autoscale has no sticky sessions; SQLite is per-instance.
    # Context here is best-effort (memory → local SQLite). Cross-node miss
    # falls through to normal NL — never invent fixture context.
    _ctx_last_match = ctx.get("last_match") or ctx.get("last_fixture")
    if _ctx_last_match and _is_followup(message):
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

    # ── NL Routing (skipped on quick follow-up hit) ───────────────────────
    if not skipped_nl:
        _route = _nl_route(message)
        intent, entities, routing_confidence = _route.intent, _route.entities, _route.confidence

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
            em = _conv_detect(message)
            if em and em[1] >= 0.80:
                emotional_intent, em_conf = em
                payload = _conv_respond(emotional_intent, ctx, brain)
                intent = emotional_intent
                routing_confidence = em_conf

        # ── 2. Legacy follow-up after NL (compat if QuickGate missed) ─────
        _ctx_last_match  = ctx.get("last_match") or ctx.get("last_fixture")
        _ctx_last_intent = ctx.get("last_intent")
        _followup_check  = _is_followup(message)
        logger.warning(
            "[AUDIT] follow-up gate: nl_intent=%r | ctx.last_match=%r | ctx.last_intent=%r"
            " | follow_up_detected=%s | already_payload=%s",
            intent, _ctx_last_match, _ctx_last_intent, _followup_check, payload is not None,
        )
        if payload is None and _ctx_last_match and _followup_check:
            logger.warning(
                "[AUDIT] follow-up gate: ENTERING follow-up engine "
                "(has_last_match=True, follow_up_detected=True)"
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
                    try:
                        logger.warning(
                            "[AUDIT] ctx_before: last_match=%r last_intent=%r",
                            ctx.get("last_match"), ctx.get("last_intent"),
                        )
                        prefer_live = bool(entities.get("is_live"))
                        payload = await _run_analyze(home, away, prefer_live=prefer_live)
                        _save_analysis_context(ctx, payload, home, away)
                        _db_upd_session(session_id, home=home, away=away, intent=intent)
                        logger.warning(
                            "[AUDIT] copilot dispatch: _run_analyze succeeded, match=%r",
                            payload.get("match"),
                        )
                        logger.warning(
                            "[AUDIT] ctx_after: last_match=%r last_intent=%r",
                            ctx.get("last_match"), ctx.get("last_intent"),
                        )
                    except Exception as _analyze_exc:
                        # Soft analyze already avoids 404; this catches engine crashes.
                        logger.warning(
                            "[AUDIT] copilot dispatch: _run_analyze raised %s: %s — "
                            "Inference V2 continues with degraded payload",
                            type(_analyze_exc).__name__, _analyze_exc,
                        )
                        from src.brain import get_brain_meta as _gbm_inf
                        from src.core.inference_context import InferenceContext

                        _eictx = InferenceContext(soft_mode=True)
                        _eictx.register_failure(
                            "analyze_pipeline",
                            str(_analyze_exc),
                            signal="fixture",
                        )
                        _eictx.finalize()
                        payload = {
                            "intent": "analyze_match",
                            "entities": {"home": home, "away": away},
                            "match": f"{home} x {away}",
                            "status": "Partial",
                            "is_live": False,
                            "minute": None,
                            "executive_summary": (
                                f"Não foi possível completar a análise de **{home} x {away}**, "
                                f"mas a Aurora registrou a falha e manteve a conversa ativa.\n\n"
                                f"Detalhe técnico: {_analyze_exc}"
                            ),
                            "best_markets": [],
                            "confidence": {
                                "score": _eictx.apply_to_score(2.0),
                                "label": "insufficient",
                                "explanation": (
                                    f"Inference V2: falha no pipeline — "
                                    f"penalidade −{_eictx.total_penalty():.1f}"
                                ),
                                "data_sources": ["Inference Layer V2"],
                            },
                            "risk": {
                                "level": "High",
                                "flags": list(_eictx.missing_signals),
                                "invalidation_conditions": [
                                    "Confirmar nomes oficiais dos times",
                                ],
                            },
                            "bankroll_recommendation": {
                                "recommended_stake_pct": 0.0,
                                "method": "quarter-Kelly",
                                "examples": {},
                                "reasoning": "Dados insuficientes para stake.",
                                "no_bet": True,
                            },
                            "positive_factors": [],
                            "negative_factors": [
                                "Falha registrada — confiança reduzida (sem abort duro).",
                            ],
                            "historical_references": [],
                            "knowledge_notes": _eictx.knowledge_notes_pt(),
                            "final_recommendation": (
                                f"Tente novamente com nomes oficiais: "
                                f"\"Analisar {home} x {away}\"."
                            ),
                            "aurora_version": "Copilot v1.0",
                            "brain": {
                                **_gbm_inf(),
                                "inference": _eictx.explainability(),
                            },
                        }

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
                    payload = await _run_analyze(_lt_home, _lt_away, prefer_live=True)
                    _save_analysis_context(ctx, payload, _lt_home, _lt_away)
                    logger.warning(
                        "[AUDIT] live_team_analysis: _run_analyze succeeded match=%r", payload.get("match")
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

            elif intent == "capabilities":
                payload = _run_capabilities()

            elif intent == "help":
                payload = _run_help()

            else:
                payload = _run_fallback(message, intent)

    except Exception as exc:
        logger.error("Copilot unified error [%s]: %s", intent, exc, exc_info=True)
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
            # Prefer soft analyze (continues engines) over static error page
            try:
                payload = await _run_analyze(home_q, away_q, prefer_live=False)
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
                        "recommended_stake_pct": 0.0, "method": "quarter-Kelly",
                        "examples": {}, "reasoning": "Sem dados completos para stake.",
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

        if _needs_llm(intent, message, ctx):
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
    try:
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
    )
