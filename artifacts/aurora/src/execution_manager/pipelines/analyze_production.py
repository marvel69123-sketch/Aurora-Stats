"""
Analyze production assembly — Phase 4 Stage 3 (E3).

Parity body for EM `run_analyze` after A1 soft fetch. Consume-only Frozen engines.
No attach_match_card. No CM writes. No begin_request.
Generated from SoT `_run_analyze` (helpers + post-fetch body); match-card stripped.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


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


def build_analyze_payload_from_data(
    data: dict[str, Any],
    home: str,
    away: str,
    *,
    prefer_live: bool = False,
) -> dict[str, Any]:
    """
    SoT-equivalent of `_run_analyze` after soft fetch, without match-card attach.

    Includes defense-in-depth early integrity HARD-ABORT (same as SoT). EM A2
    normally gates first; this keeps parity if called with raw fetch data.
    """
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
    return result
