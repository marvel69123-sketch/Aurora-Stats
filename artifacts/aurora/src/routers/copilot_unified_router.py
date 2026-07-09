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
            "market":         f"{hn} x {an}",
            "probability":    0.0,
            "expected_value": 0.0,
            "confidence":     0.0,
            "risk":           "Unknown",
            "rationale":      (
                f"{hn} {score_h}–{score_a} {an} · Minuto {minute}"
                + (f" · {league}" if league else "")
                + ". Peça à Aurora para \"Analisar [Casa] x [Fora]\" para uma avaliação completa."
            ),
        })

    summary = (
        f"{count} partida{'s' if count != 1 else ''} ao vivo agora."
        if count else "Nenhuma partida ao vivo no momento."
    )
    final = (
        f"Execute \"Analisar [Casa] x [Fora]\" em qualquer partida ao vivo para um relatório completo de inteligência."
        if count else "Nenhuma oportunidade ao vivo no momento. Volte mais tarde."
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
            "explanation":  "Apenas lista de partidas ao vivo. Análise completa requer uma partida específica.",
            "data_sources": ["Feed ao vivo API-Football"],
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
            "reasoning":             "Nenhuma stake recomendada sem análise completa da partida.",
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
    return {
        "intent":   "greeting",
        "entities": {},
        "match":   None, "status": None, "is_live": False, "minute": None,
        "executive_summary": (
            "Olá! Sou a **Aurora**, sua assistente profissional de inteligência esportiva. "
            "Combino dados ao vivo, gols esperados (xG), padrões históricos e 39 regras metodológicas "
            "de apostas para entregar análises de nível profissional."
        ),
        "best_markets":      [],
        "confidence": {"score": 0.0, "label": "insufficient", "explanation": "Sessão iniciada.", "data_sources": []},
        "risk": {"level": "Unknown", "flags": [], "invalidation_conditions": []},
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0, "method": "quarter-Kelly",
            "examples": {}, "no_bet": True,
            "reasoning": "Comece analisando uma partida para receber uma recomendação de stake.",
        },
        "positive_factors":      [],
        "negative_factors":      [],
        "historical_references": [],
        "knowledge_notes": [
            "Analisar partida: \"Analisar Palmeiras x Flamengo\"",
            "Oportunidades ao vivo: \"Melhores oportunidades ao vivo\"",
            "Revisão de banca: \"Revisar banca\"",
            "Aprendizado: \"O que a Aurora aprendeu hoje?\"",
            "Conhecimento: \"O que você sabe sobre BTTS?\"",
        ],
        "final_recommendation": (
            "Por onde começar? Tente: **\"Analisar [Time da Casa] x [Time Visitante]\"** "
            "para um relatório completo de inteligência."
        ),
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
    return {
        "intent":   "identity",
        "entities": {},
        "match":   None, "status": None, "is_live": False, "minute": None,
        "executive_summary": (
            "Sou a **Aurora** — uma assistente de inteligência esportiva de nível profissional.\n\n"
            "Fui construída para analistas e apostadores sérios que precisam de dados concretos, "
            "não de palpites. Combino múltiplas fontes em tempo real:\n\n"
            "• **Dados ao vivo** — fixtures, escalações, eventos e estatísticas de partidas\n"
            "• **Gols esperados (xG)** — qualidade de chutes além do placar\n"
            "• **Histórico de confrontos** — padrões de h2h e forma recente\n"
            "• **Base de conhecimento** — 40 regras metodológicas de apostas\n"
            "• **Gestão de banca** — dimensionamento de stake pelo Critério de Kelly\n"
            "• **Motor de aprendizado** — aprendo com cada previsão e ajusto os pesos\n\n"
            "Entendo português natural. Não precisa de comandos exatos."
        ),
        "best_markets": [],
        "confidence": {"score": 0.0, "label": "insufficient", "explanation": "Apresentação da Aurora.", "data_sources": []},
        "risk": {"level": "Unknown", "flags": [], "invalidation_conditions": []},
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0, "method": "quarter-Kelly",
            "examples": {}, "no_bet": True,
            "reasoning": "Analise uma partida para receber uma recomendação de stake.",
        },
        "positive_factors":      [],
        "negative_factors":      [],
        "historical_references": [],
        "knowledge_notes": [
            "Aurora = Inteligência Esportiva Profissional",
            "Dados: API-Football + xG + H2H + 40 regras metodológicas",
            "Banca: dimensionamento pelo Critério de Kelly",
            "Aprendizado: precisão rastreada por mercado, risco ajustado automaticamente",
        ],
        "final_recommendation": (
            "Pronto para ajudar! Tente: **\"Analisar [Time da Casa] x [Time Visitante]\"** "
            "para uma análise completa de inteligência."
        ),
        "aurora_version": "Copilot v1.0",
        "brain":          get_brain_meta(),
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
    from src.core.nl_router import route as _nl_route

    message = body.message.strip()
    _route  = _nl_route(message)
    intent, entities, routing_confidence = _route.intent, _route.entities, _route.confidence
    request_id = secrets.token_hex(4)

    logger.info(
        "copilot request_id=%s intent=%s conf=%.3f entities=%s message=%r",
        request_id, intent, routing_confidence, entities, message,
    )

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
        from src.brain import get_brain_meta

        # Friendly handling for 404 (team/fixture not found)
        is_404 = isinstance(exc, _HTTPExc) and exc.status_code == 404
        home_q = entities.get("home", "")
        away_q = entities.get("away", "")

        if is_404:
            if home_q and away_q:
                summary = (
                    f"Não consegui localizar a partida **{home_q} x {away_q}**.\n\n"
                    f"Isso pode acontecer porque:\n"
                    f"• o jogo ainda não foi cadastrado na API\n"
                    f"• o nome do time está diferente do nome oficial\n"
                    f"• a competição não está disponível na temporada atual\n\n"
                    f"**Sugestões:** tente o nome oficial completo — por exemplo, "
                    f"*\"Atletico Mineiro\"* em vez de *\"Atlético-MG\"*, ou "
                    f"*\"Paris Saint-Germain\"* em vez de *\"PSG\"*."
                )
                final = "Tente novamente com o nome oficial do time. Digite o nome completo sem abreviações."
            else:
                summary = (
                    "Não consegui localizar esse time ou partida na API.\n\n"
                    "Verifique o nome oficial e tente novamente.\n"
                    "Exemplo: *\"Analisar Real Madrid x Barcelona\"*"
                )
                final = "Use o nome oficial completo do time para uma busca bem-sucedida."
        else:
            summary = (
                "A Aurora encontrou um problema ao processar sua solicitação. "
                "Por favor, tente novamente ou reformule a pergunta."
            )
            final = "Tente novamente. Se o problema persistir, verifique o nome da partida."

        payload = {
            "intent":   intent,
            "entities": entities,
            "match":   None, "status": None, "is_live": False, "minute": None,
            "executive_summary": summary,
            "best_markets":      [],
            "confidence": {"score": 0.0, "label": "insufficient", "explanation": "Erro de processamento.", "data_sources": []},
            "risk": {"level": "Unknown", "flags": [], "invalidation_conditions": []},
            "bankroll_recommendation": {"recommended_stake_pct": 0.0, "method": "quarter-Kelly", "examples": {}, "reasoning": "Nenhuma aposta disponível.", "no_bet": True},
            "positive_factors": [], "negative_factors": [],
            "historical_references": [], "knowledge_notes": [],
            "final_recommendation": final,
            "aurora_version": "Copilot v1.0",
            "brain": get_brain_meta(),
        }

    return CopilotResponse(
        intent              = payload["intent"],
        entities            = payload.get("entities", entities),
        request_id          = request_id,
        generated_at        = _now_iso(),
        routing_confidence  = routing_confidence,
        match               = payload.get("match"),
        status              = payload.get("status"),
        is_live             = payload.get("is_live", False),
        minute              = payload.get("minute"),

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
