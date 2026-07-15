"""
Aurora v3.3.2-beta — Fixture Integrity Guard.

Classifies confrontation quality before markets / confidence / MatchHeader
are exposed. Does NOT change methodology / market / confidence engines.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal

logger = logging.getLogger(__name__)

FixtureStatus = Literal["FOUND", "PARTIAL", "NOT_FOUND", "FICTIONAL"]
FixtureQuality = Literal["VALID", "PARTIAL", "INVALID"]

INTEGRITY_NOT_FOUND_MESSAGE = (
    "Não consegui localizar um confronto esportivo válido."
)

# Tokens that are never valid football clubs/national teams for this product.
_FICTION_TOKENS: frozenset[str] = frozenset(
    {
        # Anime / games / fiction
        "goku",
        "naruto",
        "vegeta",
        "gohan",
        "luffy",
        "zoro",
        "saitama",
        "pikachu",
        "dragon",
        "ball",
        "dbz",
        "onepiece",
        "batman",
        "superman",
        "spiderman",
        "harry",
        "potter",
        "frodo",
        "vader",
        "thanos",
        "mario",
        "sonic",
        "zelda",
        "link",
        # Planets / nonsense "clubs"
        "marte",
        "jupiter",
        "saturno",
        "plutao",
        "venus",
        "mercurio",
        # Famous players used as fake "teams"
        "messi",
        "cristiano",
        "ronaldo",
        "cr7",
        "neymar",
        "mbappe",
        "haaland",
        "pele",
        "maradona",
    }
)

_FICTION_PHRASES: tuple[str, ...] = (
    "dragon ball",
    "one piece",
    "harry potter",
    "star wars",
    "marte fc",
    "real madrid de cartorio",
)


def _fold(text: str) -> str:
    t = (text or "").lower().strip()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _words(text: str) -> list[str]:
    return [w for w in _fold(text).split() if w]


def looks_fictional_name(name: str | None) -> bool:
    """True when the name is anime/celebrity/non-club fiction."""
    folded = _fold(name or "")
    if not folded:
        return False
    for phrase in _FICTION_PHRASES:
        if phrase in folded:
            return True
    tokens = set(_words(folded))
    if tokens & _FICTION_TOKENS:
        return True
    compact = "".join(tokens)
    for tok in _FICTION_TOKENS:
        if len(tok) >= 4 and tok in compact:
            return True
    return False


def looks_garbage_name(name: str | None) -> bool:
    """True for synthetic placeholders like teste123 / abc456."""
    folded = _fold(name or "")
    if not folded:
        return True
    compact = re.sub(r"\s+", "", folded)
    if re.fullmatch(r"[a-z]*\d+[a-z]*\d*", compact) and re.search(r"\d", compact):
        return True
    if re.fullmatch(r"[a-z]{2,}\d{2,}", compact) or re.fullmatch(r"\d{2,}[a-z]{2,}", compact):
        return True
    if re.fullmatch(r"(teste|test|abc|xyz|foo|bar)\d*", compact):
        return True
    return False


def status_to_quality(status: str | None) -> FixtureQuality:
    if status == "FOUND":
        return "VALID"
    if status == "PARTIAL":
        return "PARTIAL"
    return "INVALID"


@dataclass(frozen=True)
class FixtureIntegrityResult:
    status: FixtureStatus
    home: str | None
    away: str | None
    markets_blocked: bool
    header_blocked: bool
    confidence_label: str  # unavailable | insufficient | moderate | strong
    confidence_score: float
    message: str | None
    reasons: tuple[str, ...]
    entity_match_score: float = 0.0

    @property
    def quality(self) -> FixtureQuality:
        return status_to_quality(self.status)

    @property
    def fixture_found(self) -> bool:
        return self.status == "FOUND"

    @property
    def is_usable(self) -> bool:
        return self.status == "FOUND"

    @property
    def is_blocked(self) -> bool:
        return self.status in ("NOT_FOUND", "FICTIONAL")

    @property
    def market_generation_enabled(self) -> bool:
        return self.status == "FOUND" and not self.markets_blocked


def _blocked(
    *,
    status: FixtureStatus,
    home: str | None,
    away: str | None,
    reasons: tuple[str, ...],
    entity_match_score: float = 0.0,
) -> FixtureIntegrityResult:
    # INVALID → confiança muito baixa (insufficient), never moderate
    return FixtureIntegrityResult(
        status=status,
        home=home,
        away=away,
        markets_blocked=True,
        header_blocked=True,
        confidence_label="insufficient",
        confidence_score=1.0,
        message=INTEGRITY_NOT_FOUND_MESSAGE,
        reasons=reasons,
        entity_match_score=entity_match_score,
    )


def assess_named_fixture(home: str | None, away: str | None) -> FixtureIntegrityResult:
    """
    Pre-analyze integrity from extracted team names only.
    """
    h = (home or "").strip() or None
    a = (away or "").strip() or None
    reasons: list[str] = []

    if not h or not a:
        result = _blocked(
            status="NOT_FOUND", home=h, away=a, reasons=("missing_teams",),
        )
        _log_integrity(result, stage="precheck")
        return result

    fic_h = looks_fictional_name(h)
    fic_a = looks_fictional_name(a)
    gar_h = looks_garbage_name(h)
    gar_a = looks_garbage_name(a)

    if fic_h or fic_a:
        if fic_h:
            reasons.append(f"fiction_home:{h}")
        if fic_a:
            reasons.append(f"fiction_away:{a}")
        result = _blocked(
            status="FICTIONAL",
            home=h,
            away=a,
            reasons=tuple(reasons),
        )
        _log_integrity(result, stage="precheck")
        return result

    if gar_h or gar_a:
        if gar_h:
            reasons.append(f"garbage_home:{h}")
        if gar_a:
            reasons.append(f"garbage_away:{a}")
        result = _blocked(
            status="NOT_FOUND",
            home=h,
            away=a,
            reasons=tuple(reasons),
        )
        _log_integrity(result, stage="precheck")
        return result

    # Entity validator — fail CLOSED on errors (v3.3.2-beta)
    try:
        from src.core.entity_validator import validate_fixture_entities

        ok, hv, av = validate_fixture_entities(h, a)
        score = min(float(hv.similarity), float(av.similarity))
        if not ok:
            reasons.extend(list(hv.reasons) + list(av.reasons))
            result = _blocked(
                status="NOT_FOUND",
                home=h,
                away=a,
                reasons=tuple(reasons) or ("entity_invalid",),
                entity_match_score=score,
            )
            _log_integrity(result, stage="precheck")
            return result
        entity_score = score
    except Exception as exc:
        logger.error(
            "fixture_integrity: entity_validator FAILED CLOSED (%s)", exc,
        )
        result = _blocked(
            status="NOT_FOUND",
            home=h,
            away=a,
            reasons=(f"validator_error:{type(exc).__name__}",),
        )
        _log_integrity(result, stage="precheck")
        return result

    result = FixtureIntegrityResult(
        status="FOUND",
        home=h,
        away=a,
        markets_blocked=False,
        header_blocked=False,
        confidence_label="moderate",
        confidence_score=6.0,
        message=None,
        reasons=("precheck_ok",),
        entity_match_score=entity_score,
    )
    _log_integrity(result, stage="precheck")
    return result


def assess_analyze_result(
    home: str | None,
    away: str | None,
    *,
    fixture_id: Any = None,
    is_partial: bool = False,
    data_completeness: float = 1.0,
) -> FixtureIntegrityResult:
    """
    Post-analyze integrity using API fixture resolution signals.
    """
    pre = assess_named_fixture(home, away)
    if pre.is_blocked:
        return pre

    try:
        fid = int(fixture_id or 0)
    except (TypeError, ValueError):
        fid = 0

    if is_partial or fid <= 0:
        result = _blocked(
            status="NOT_FOUND",
            home=home,
            away=away,
            reasons=(
                "api_fixture_missing",
                f"fixture_id={fid}",
                f"partial={is_partial}",
            ),
            entity_match_score=pre.entity_match_score,
        )
        _log_integrity(result, stage="postcheck")
        return result

    if data_completeness < 0.35:
        result = FixtureIntegrityResult(
            status="PARTIAL",
            home=home,
            away=away,
            markets_blocked=True,
            header_blocked=True,
            confidence_label="insufficient",
            confidence_score=1.5,
            message=None,
            reasons=(f"low_completeness:{data_completeness:.2f}",),
            entity_match_score=pre.entity_match_score,
        )
        _log_integrity(result, stage="postcheck")
        return result

    result = FixtureIntegrityResult(
        status="FOUND",
        home=home,
        away=away,
        markets_blocked=False,
        header_blocked=False,
        confidence_label="moderate",
        confidence_score=6.0,
        message=None,
        reasons=("fixture_found", f"fixture_id={fid}"),
        entity_match_score=pre.entity_match_score,
    )
    _log_integrity(result, stage="postcheck")
    return result


def _log_integrity(result: FixtureIntegrityResult, *, stage: str) -> None:
    logger.warning(
        "[DEBUG] fixture_resolver=%s fixture_found=%s fixture_quality=%s "
        "fixture_status=%s entity_match_score=%.3f market_generation_enabled=%s "
        "home=%r away=%r reasons=%s",
        stage,
        result.fixture_found,
        result.quality,
        result.status,
        result.entity_match_score,
        result.market_generation_enabled,
        result.home,
        result.away,
        result.reasons,
    )


def blocked_integrity_payload(
    result: FixtureIntegrityResult,
    *,
    brain: dict | None = None,
) -> dict[str, Any]:
    """Copilot payload for NOT_FOUND / FICTIONAL — no markets, no sports header."""
    from src.brain import get_brain_meta
    from src.core.debug_audit import audit_blocked

    msg = result.message or INTEGRITY_NOT_FOUND_MESSAGE
    label = (
        f"{result.home} x {result.away}"
        if result.home and result.away
        else None
    )
    conf_label = result.confidence_label
    conf_score = float(result.confidence_score)
    quality = result.quality

    return {
        "intent": "analyze_match",
        "entities": {
            "home": result.home,
            "away": result.away,
            "fixture_status": result.status,
            "fixture_quality": quality,
            "fixture_found": False,
            "entity_invalid": True,
            "markets_blocked": True,
            "market_generation_enabled": False,
            "entity_match_score": result.entity_match_score,
        },
        "match": label,
        "status": result.status,
        "is_live": False,
        "minute": None,
        "fixture_status": result.status,
        "fixture_quality": quality,
        "fixture_found": False,
        "_audit": {
            **audit_blocked(
                fixture_status=result.status,
                home=result.home,
                away=result.away,
            ),
            "fixture_resolver": "integrity_blocked",
            "entity_match_score": result.entity_match_score,
            "market_generation_enabled": False,
            "fixture_quality": quality,
        },
        "executive_summary": msg,
        "best_markets": [],
        "confidence": {
            "score": conf_score,
            "label": conf_label,
            "explanation": (
                "Confiança muito baixa — confronto sem fixture esportiva válida."
            ),
            "data_sources": ["Fixture Integrity Guard"],
        },
        "risk": {
            "level": "High",
            "flags": list(result.reasons) or ["fixture_integrity"],
            "invalidation_conditions": [],
        },
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0,
            "method": "quarter-Kelly",
            "examples": {},
            "no_bet": True,
            "reasoning": msg,
        },
        "positive_factors": [],
        "negative_factors": [],
        "historical_references": [],
        "knowledge_notes": [],
        "final_recommendation": msg,
        "aurora_version": "Aurora v3.3.2-beta",
        "brain": brain or get_brain_meta(),
        "match_card": None,
        "response_metadata": {
            "fixture_status": result.status,
            "fixture_quality": quality,
            "fixture_found": False,
            "markets_blocked": True,
            "header_blocked": True,
            "market_generation_enabled": False,
            "entity_match_score": result.entity_match_score,
        },
    }


def apply_integrity_to_payload(
    payload: dict[str, Any],
    result: FixtureIntegrityResult,
) -> dict[str, Any]:
    """Mutate/copy payload to enforce integrity blocks after analyze."""
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    quality = result.quality
    out["fixture_status"] = result.status
    out["fixture_quality"] = quality
    out["fixture_found"] = bool(result.fixture_found)

    ents = dict(out.get("entities") or {})
    ents["fixture_status"] = result.status
    ents["fixture_quality"] = quality
    ents["fixture_found"] = bool(result.fixture_found)
    ents["markets_blocked"] = bool(result.markets_blocked)
    ents["market_generation_enabled"] = bool(result.market_generation_enabled)
    ents["entity_match_score"] = result.entity_match_score
    out["entities"] = ents

    meta = dict(out.get("response_metadata") or {})
    meta["fixture_status"] = result.status
    meta["fixture_quality"] = quality
    meta["fixture_found"] = bool(result.fixture_found)
    meta["markets_blocked"] = bool(result.markets_blocked)
    meta["header_blocked"] = bool(result.header_blocked)
    meta["market_generation_enabled"] = bool(result.market_generation_enabled)
    meta["entity_match_score"] = result.entity_match_score
    out["response_metadata"] = meta

    if result.is_blocked or quality == "INVALID":
        from src.core.debug_audit import audit_blocked

        out["best_markets"] = []
        out["match_card"] = None
        out["fixture_found"] = False
        out["executive_summary"] = result.message or INTEGRITY_NOT_FOUND_MESSAGE
        out["final_recommendation"] = result.message or INTEGRITY_NOT_FOUND_MESSAGE
        out["status"] = result.status
        out["_audit"] = {
            **audit_blocked(
                fixture_status=result.status,
                home=result.home,
                away=result.away,
            ),
            "fixture_resolver": "integrity_blocked",
            "entity_match_score": result.entity_match_score,
            "market_generation_enabled": False,
            "fixture_quality": quality,
        }
        out["confidence"] = {
            "score": result.confidence_score,
            "label": "insufficient",
            "explanation": (
                "Confiança muito baixa — confronto sem fixture esportiva válida."
            ),
            "data_sources": ["Fixture Integrity Guard"],
        }
        bank = dict(out.get("bankroll_recommendation") or {})
        bank["recommended_stake_pct"] = 0.0
        bank["examples"] = {}
        bank["no_bet"] = True
        bank["reasoning"] = result.message or INTEGRITY_NOT_FOUND_MESSAGE
        out["bankroll_recommendation"] = bank
        return out

    if result.status == "PARTIAL" or quality == "PARTIAL":
        out["best_markets"] = []
        out["fixture_found"] = False
        audit = dict(out.get("_audit") or {})
        audit["markets_source"] = None
        audit["market_reasoning"] = None
        audit["market_generation_enabled"] = False
        audit["fixture_quality"] = "PARTIAL"
        audit["fixture_found"] = False
        out["_audit"] = audit
        conf = dict(out.get("confidence") or {})
        conf["score"] = min(float(conf.get("score") or 10), 1.5)
        conf["label"] = "insufficient"
        conf["explanation"] = (
            "Confiança muito baixa — fixture parcial / dados incompletos."
        )
        out["confidence"] = conf
        bank = dict(out.get("bankroll_recommendation") or {})
        bank["recommended_stake_pct"] = 0.0
        bank["examples"] = {}
        bank["no_bet"] = True
        out["bankroll_recommendation"] = bank
        if result.header_blocked:
            out["match_card"] = None

    return out
