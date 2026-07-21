"""
AURORA-INTENT-001 — Semantic Sports Intent Layer (SSIL).

Inspired by Rasa dialogue policies (intent → action) and Athena response
generators (topic-specialized handlers). Additive façade only.

Classifies explicit sports intents and routes follow-ups to specialized
*skills* via message shaping + metadata — does NOT modify engines,
MasterIntent, ownership/continuity guards, SLL, CSL, or entity_safety.

Feature flag: ENABLE_SPORT_INTENTS (default ON; 0/false/off = rollback).
"""

from __future__ import annotations

import logging
import os
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

_FLAG_ENV = "ENABLE_SPORT_INTENTS"
CTX_KEY = "sport_intents"
MIN_CONFIDENCE = 0.70

# Explicit intents (contract)
COMPARE_STRENGTH = "compare_strength"
BET_VIABILITY = "bet_viability"
CALENDAR_QUERY = "calendar_query"
HOME_AWAY_ANALYSIS = "home_away_analysis"
RECENT_FORM = "recent_form"
MARKET_QUESTION = "market_question"

SPORT_INTENTS = (
    COMPARE_STRENGTH,
    BET_VIABILITY,
    CALENDAR_QUERY,
    HOME_AWAY_ANALYSIS,
    RECENT_FORM,
    MARKET_QUESTION,
)

# Intent → skill id (Rasa-like policy target)
INTENT_TO_SKILL: dict[str, str] = {
    COMPARE_STRENGTH: "skill_compare_strength",
    BET_VIABILITY: "skill_bet_viability",
    CALENDAR_QUERY: "skill_calendar_query",
    HOME_AWAY_ANALYSIS: "skill_home_away",
    RECENT_FORM: "skill_recent_form",
    MARKET_QUESTION: "skill_market_question",
}


def sport_intents_enabled() -> bool:
    raw = (os.environ.get(_FLAG_ENV) or "1").strip().lower()
    return raw not in {"0", "false", "off", "no"}


def fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


@dataclass
class SportIntentResult:
    intent: str | None = None
    skill: str | None = None
    confidence: float = 0.0
    raw_text: str = ""
    routed_text: str | None = None
    applied: bool = False
    rewritten: bool = False
    signals: list[str] = field(default_factory=list)
    skipped_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Intent detectors (scored; highest confidence wins) ──

_INTENT_PATTERNS: list[tuple[str, re.Pattern[str], float]] = [
    (
        MARKET_QUESTION,
        re.compile(
            r"(?:"
            r"\b(?:over|under)\s*\d|"
            r"\bbtts\b|ambos\s+marcam|ambas\s+marcam|"
            r"\bescanteios?\b|\bcantos?\b|\bcorners?\b|"
            r"\bcart[oõ]es?\b|\bamarelos?\b|\bcards?\b|"
            r"\bmercados?\b|\bmarket\b|"
            r"e\s+(?:os\s+)?(?:gols?|escanteios?|cart[oõ]es?|mercados?)"
            r")",
            re.I,
        ),
        0.90,
    ),
    (
        BET_VIABILITY,
        re.compile(
            r"(?:"
            r"vale\s+a\s+pena|"
            r"\baposta(?:r)?\b|"
            r"\bstake\b|\bkelly\b|"
            r"\bedge\b|\bvalue\b|"
            r"odd\s+justa|valor\s+esperado|"
            r"viabilidade|"
            r"confian[cç]a\s+(?:na|da)\s+aposta|"
            r"entrar\s+n(?:essa|esta)\s+aposta"
            r")",
            re.I,
        ),
        0.88,
    ),
    (
        CALENDAR_QUERY,
        re.compile(
            r"(?:"
            r"quando\s+joga|"
            r"\bagenda\b|\bcalend[aá]rio\b|"
            r"pr[oó]xim[oa]\s+(?:jogo|partida|rodada)|"
            r"jogos?\s+(?:de\s+)?(?:hoje|amanh[aã])|"
            r"\bhor[aá]rio\b|que\s+horas|"
            r"\bhoje\b.*\bjogo|\bjogo\b.*\bhoje|"
            r"\bamanh[aã]\b"
            r")",
            re.I,
        ),
        0.86,
    ),
    (
        HOME_AWAY_ANALYSIS,
        re.compile(
            r"(?:"
            r"mando\s+de\s+campo|"
            r"em\s+casa|fora\s+de\s+casa|"
            r"home\s+advantage|away\s+form|"
            r"como\s+(?:manda|joga)\s+em\s+casa|"
            r"fator\s+casa"
            r")",
            re.I,
        ),
        0.87,
    ),
    (
        RECENT_FORM,
        re.compile(
            r"(?:"
            r"melhor\s+fase|em\s+melhor\s+fase|"
            r"melhor\s+forma|em\s+melhor\s+forma|"
            r"\bfase\b|\bforma\b|\bmomento\b|"
            r"[uú]ltimos?\s+jogos?|"
            r"sequ[eê]ncia|streak|"
            r"est[aá]\s+(?:bem|mal)|"
            r"quem\s+est[aá]\s+melhor"
            r")",
            re.I,
        ),
        0.85,
    ),
    (
        COMPARE_STRENGTH,
        re.compile(
            r"(?:"
            r"quem\s+(?:e|é)\s+mais\s+forte|"
            r"quem\s+ganha|quem\s+vence|quem\s+leva|"
            r"mais\s+chance|mais\s+forte|"
            r"\bcompar(?:ar|e|ando)\b|"
            r"qual\s+dos\s+dois|"
            r"\sou\b|\bvs\.?\b|\bx\b"
            r")",
            re.I,
        ),
        0.82,
    ),
]


def classify_sport_intent(message: str) -> tuple[str | None, float, list[str]]:
    """Return (intent, confidence, matched signal names)."""
    text = message or ""
    if not text.strip():
        return None, 0.0, []
    hits: list[tuple[str, float]] = []
    for name, pat, base in _INTENT_PATTERNS:
        if pat.search(text):
            hits.append((name, base))
    if not hits:
        return None, 0.0, []
    hits.sort(key=lambda h: -h[1])
    best_name, best_conf = hits[0]
    if len(hits) > 1 and hits[1][1] >= 0.84:
        best_conf = min(0.95, best_conf + 0.03)
    return best_name, best_conf, [h[0] for h in hits]


def _csl_teams(ctx: dict[str, Any] | None) -> list[str]:
    if not isinstance(ctx, dict):
        return []
    csl = ctx.get("csl")
    if isinstance(csl, dict):
        teams = csl.get("teams") or []
        if isinstance(teams, list):
            return [str(t).strip() for t in teams if isinstance(t, str) and t.strip()][:4]
    return []


def _fixture_label(ctx: dict[str, Any] | None, teams: list[str]) -> str | None:
    if isinstance(ctx, dict):
        csl = ctx.get("csl") if isinstance(ctx.get("csl"), dict) else {}
        fx = csl.get("fixture") if isinstance(csl, dict) else None
        if isinstance(fx, str) and fx.strip():
            return fx.strip()
        for key in ("last_match", "last_fixture"):
            v = ctx.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
    if len(teams) >= 2:
        return f"{teams[0]} x {teams[1]}"
    return teams[0] if teams else None


def _skill_compare_strength(message: str, ctx: dict[str, Any]) -> str | None:
    teams = _csl_teams(ctx)
    msg = (message or "").strip()
    if len(teams) >= 2 and not re.search(rf"\b{re.escape(teams[0])}\b", msg, re.I):
        return (
            f"Entre {teams[0]} e {teams[1]}, "
            f"quem é mais forte / tem mais chance?"
        )
    if len(teams) >= 2 and re.search(r"\bou\b|\bx\b|\bvs\b", msg, re.I):
        return f"analisar {teams[0]} x {teams[1]} (comparativo de forca)"
    return None


def _skill_bet_viability(message: str, ctx: dict[str, Any]) -> str | None:
    fx = _fixture_label(ctx, _csl_teams(ctx))
    if not fx:
        return None
    if re.search(r"vale\s+a\s+pena|viabilidade|apostar", message or "", re.I):
        return f"vale a pena apostar no confronto {fx}?"
    return f"viabilidade de aposta em {fx}"


def _skill_calendar_query(message: str, ctx: dict[str, Any]) -> str | None:
    teams = _csl_teams(ctx)
    msg = fold(message)
    team = teams[0] if teams else None
    if not team:
        return None
    team_f = fold(team)
    if team_f in msg:
        return None
    if re.search(r"quando|agenda|proximo|calendario|joga", message or "", re.I):
        if "agenda" in msg or "calendario" in msg:
            return f"agenda de {team}"
        return f"quando joga {team}?"
    return None


def _skill_home_away(message: str, ctx: dict[str, Any]) -> str | None:
    fx = _fixture_label(ctx, _csl_teams(ctx))
    teams = _csl_teams(ctx)
    if fx and re.search(
        r"mando|em\s+casa|fora\s+de\s+casa|fator\s+casa", message or "", re.I
    ):
        return f"análise de mando de campo em {fx}"
    if len(teams) >= 1 and re.search(r"em\s+casa|fora\s+de\s+casa", message or "", re.I):
        return f"como {teams[0]} joga em casa e fora"
    return None


def _skill_recent_form(message: str, ctx: dict[str, Any]) -> str | None:
    teams = _csl_teams(ctx)
    msg = (message or "").strip()
    if len(teams) >= 2:
        if not re.search(rf"\b{re.escape(teams[0])}\b", msg, re.I):
            return (
                f"Entre {teams[0]} e {teams[1]}, "
                f"quem está em melhor fase recente?"
            )
        return f"forma recente de {teams[0]} e {teams[1]}"
    if len(teams) == 1 and not re.search(rf"\b{re.escape(teams[0])}\b", msg, re.I):
        return f"como está a fase recente do {teams[0]}?"
    return None


def _skill_market_question(message: str, ctx: dict[str, Any]) -> str | None:
    fx = _fixture_label(ctx, _csl_teams(ctx))
    msg = (message or "").strip()
    # Preserve short FU tokens for follow_up_engine
    if re.match(
        r"^(?:e\s+)?(?:os\s+)?(?:gols?|escanteios?|cantos?|corners?|"
        r"cart[oõ]es?|mercados?|btts|over|under)(?:\s+\d+(?:[.,]\d+)?)?\s*\??$",
        msg,
        re.I,
    ):
        return None
    if fx and re.search(r"mercado|over|under|btts|escanteio|cart", msg, re.I):
        side0 = fx.split(" x ")[0].strip() if " x " in fx else fx.split(" vs ")[0].strip()
        if side0 and fold(side0) not in fold(msg):
            return f"{msg.rstrip('?')} no confronto {fx}?"
    return None


_SKILL_HANDLERS: dict[str, Callable[[str, dict[str, Any]], str | None]] = {
    COMPARE_STRENGTH: _skill_compare_strength,
    BET_VIABILITY: _skill_bet_viability,
    CALENDAR_QUERY: _skill_calendar_query,
    HOME_AWAY_ANALYSIS: _skill_home_away,
    RECENT_FORM: _skill_recent_form,
    MARKET_QUESTION: _skill_market_question,
}


def route_to_skill(
    intent: str,
    message: str,
    ctx: dict[str, Any] | None,
) -> str | None:
    """Apply specialized skill rewrite; None = leave message unchanged."""
    handler = _SKILL_HANDLERS.get(intent)
    if not handler or not isinstance(ctx, dict):
        return None
    try:
        return handler(message, ctx)
    except Exception:
        return None


def apply_sport_intent_layer(
    message: str,
    ctx: dict[str, Any] | None = None,
) -> SportIntentResult:
    """
    Turn-start SSIL entry. Classifies intent, routes to skill rewrite when useful.
    Fail-open. Never raises.
    """
    raw = message or ""
    result = SportIntentResult(raw_text=raw, routed_text=raw)

    if not sport_intents_enabled():
        result.skipped_reason = "flag_disabled"
        _stamp(ctx, result)
        _log(result)
        return result

    try:
        if isinstance(ctx, dict) and (
            ctx.get("fiction_context_hard_reset") or ctx.get("sport_pipeline_blocked")
        ):
            result.skipped_reason = "pipeline_blocked"
            _stamp(ctx, result)
            _log(result)
            return result

        intent, conf, signals = classify_sport_intent(raw)
        result.signals = signals
        result.confidence = conf

        if not intent or conf < MIN_CONFIDENCE:
            result.skipped_reason = "low_confidence" if intent else "no_intent"
            _stamp(ctx, result)
            _log(result)
            return result

        result.intent = intent
        result.skill = INTENT_TO_SKILL.get(intent)
        rewritten = route_to_skill(intent, raw, ctx if isinstance(ctx, dict) else {})
        out = raw
        if rewritten and fold(rewritten) != fold(raw):
            out = rewritten
            result.rewritten = True
        result.routed_text = out
        result.applied = True
        result.skipped_reason = None
        _stamp(ctx, result)
        _log(result)
        return result
    except Exception as exc:
        logger.warning("[SPORT_INTENT] fail-open: %s", exc)
        result.skipped_reason = f"error:{exc}"
        _stamp(ctx, result)
        return result


def apply_sport_intent_resolve(
    message: str, ctx: dict[str, Any] | None = None
) -> str:
    """Router helper — returns possibly skill-routed message."""
    r = apply_sport_intent_layer(message, ctx)
    if r.applied and r.routed_text:
        return r.routed_text
    return message or ""


def note_sport_intent_on_payload(
    ctx: dict[str, Any] | None,
    payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Additive stamp of sport intent/skill onto payload entities."""
    if not sport_intents_enabled() or not isinstance(payload, dict):
        return payload
    try:
        blob = None
        if isinstance(ctx, dict):
            blob = ctx.get(CTX_KEY)
        if not isinstance(blob, dict) or not blob.get("intent"):
            return payload
        ents = dict(payload.get("entities") or {})
        ents["sport_intent"] = blob.get("intent")
        ents["sport_skill"] = blob.get("skill")
        ents["sport_intent_confidence"] = blob.get("confidence")
        payload["entities"] = ents
        return payload
    except Exception as exc:
        logger.warning("[SPORT_INTENT] note fail-open: %s", exc)
        return payload


def _stamp(ctx: dict[str, Any] | None, result: SportIntentResult) -> None:
    if not isinstance(ctx, dict):
        return
    try:
        ctx[CTX_KEY] = result.to_dict()
    except Exception:
        pass


def _log(result: SportIntentResult) -> None:
    try:
        logger.warning(
            "[SPORT_INTENT] intent=%s skill=%s conf=%.2f applied=%s "
            "rewritten=%s signals=%s skip=%s raw=%r routed=%r",
            result.intent,
            result.skill,
            result.confidence,
            result.applied,
            result.rewritten,
            result.signals,
            result.skipped_reason,
            (result.raw_text or "")[:80],
            (result.routed_text or "")[:80],
        )
    except Exception:
        pass
