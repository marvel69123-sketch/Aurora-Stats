"""
Aurora v3.3.1-beta — Entity validation (pre-analyze gate).

Rejects garbage / conversational leftovers as team names before the
analyze pipeline runs. Does NOT change methodology engines.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

INVALID_FIXTURE_MESSAGE = (
    "Partida não localizada. Tente informar os nomes completos dos times."
)

_MAX_CHARS = 35
_MAX_WORDS = 4
_MIN_SIMILARITY = 0.72

# Conversational leftovers that must never appear inside a team entity
_ENTITY_STOP_WORDS: frozenset[str] = frozenset(
    {
        "aurora",
        "quero",
        "saber",
        "sobre",
        "agora",
        "amanha",
        "hoje",
        "analise",
        "analisar",
        "analisa",
        "por",
        "favor",
        "me",
        "diga",
        "como",
        "esta",
        "ao",
        "vivo",
        "versus",
        "contra",
    }
)


def _fold(text: str) -> str:
    t = (text or "").lower().strip()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _words(text: str) -> list[str]:
    return [w for w in _fold(text).split() if w]


@dataclass(frozen=True)
class EntityValidation:
    name: str
    valid: bool
    reasons: tuple[str, ...]
    similarity: float


_KNOWN_TEAMS_CACHE: list[str] | None = None


def _known_team_names() -> list[str]:
    global _KNOWN_TEAMS_CACHE
    if _KNOWN_TEAMS_CACHE is not None:
        return _KNOWN_TEAMS_CACHE
    try:
        from src.core.team_aliases import TEAM_ALIASES

        names: set[str] = set()
        for key, canonical in TEAM_ALIASES.items():
            if canonical:
                names.add(_fold(str(canonical)))
            # Keep compact keys only when short (avoid scanning huge phrase keys)
            if key and " " not in str(key) and len(str(key)) <= 24:
                names.add(_fold(str(key)))
        _KNOWN_TEAMS_CACHE = sorted(n for n in names if len(n) >= 3)
    except Exception as exc:
        logger.warning("entity_validator: TEAM_ALIASES unavailable (%s)", exc)
        _KNOWN_TEAMS_CACHE = []
    return _KNOWN_TEAMS_CACHE


def team_similarity(name: str) -> float:
    """Best similarity of *name* against the local team alias base."""
    folded = _fold(name)
    if not folded:
        return 0.0
    try:
        from src.core.entity_resolver import has_alias

        if has_alias(name):
            return 1.0
    except Exception:
        pass

    best = 0.0
    for known in _known_team_names():
        if folded == known:
            return 1.0
        if len(folded) >= 4 and (folded in known or known in folded):
            # Only reward near-equal contains (avoid Inglaterraamanha ≈ Inglaterra)
            if abs(len(folded) - len(known)) <= 2:
                best = max(best, 0.9)
            continue
        # Skip expensive ratio when lengths differ a lot
        if abs(len(folded) - len(known)) > max(8, len(folded)):
            continue
        ratio = SequenceMatcher(None, folded, known).ratio()
        if ratio > best:
            best = ratio
        if best >= 0.95:
            return round(best, 3)
    return round(best, 3)


def validate_team_entity(name: str | None) -> EntityValidation:
    """
    Validate a single home/away entity.

    Invalid when any of:
      - length > 35
      - more than 4 words
      - contains stop words (token or glued substring)
      - low similarity vs team alias base
    """
    raw = (name or "").strip()
    reasons: list[str] = []
    if not raw:
        return EntityValidation(name="", valid=False, reasons=("empty",), similarity=0.0)

    if len(raw) > _MAX_CHARS:
        reasons.append("too_long")

    words = _words(raw)
    if len(words) > _MAX_WORDS:
        reasons.append("too_many_words")

    stop_hits = [w for w in words if w in _ENTITY_STOP_WORDS]
    compact = "".join(words)
    for stop in _ENTITY_STOP_WORDS:
        if len(stop) < 4:
            continue
        if stop in compact and compact != stop and stop not in stop_hits:
            # Glued leftovers: Inglaterraamanha, auroraquerosaber...
            stop_hits.append(stop)
    if stop_hits:
        reasons.append(f"stop_words:{','.join(sorted(set(stop_hits)))}")

    sim = team_similarity(raw)
    if sim < _MIN_SIMILARITY:
        reasons.append(f"low_similarity:{sim:.2f}")

    valid = not reasons
    logger.warning(
        "ENTITY_VALIDATE name=%r valid=%s similarity=%.3f reasons=%s",
        raw, valid, sim, reasons or None,
    )
    return EntityValidation(
        name=raw,
        valid=valid,
        reasons=tuple(reasons),
        similarity=sim,
    )


def validate_fixture_entities(
    home: str | None,
    away: str | None,
) -> tuple[bool, EntityValidation, EntityValidation]:
    """Return (ok, home_validation, away_validation)."""
    hv = validate_team_entity(home)
    av = validate_team_entity(away)
    ok = hv.valid and av.valid and bool(hv.name) and bool(av.name)
    if hv.name and av.name and hv.name.lower() == av.name.lower():
        ok = False
    return ok, hv, av


def invalid_fixture_payload(
    *,
    home: str | None,
    away: str | None,
    brain: dict | None = None,
    reasons: list[str] | None = None,
) -> dict:
    """Copilot payload: no markets, clear user message."""
    from src.brain import get_brain_meta

    msg = INVALID_FIXTURE_MESSAGE
    label = f"{home or '?'} x {away or '?'}" if (home or away) else None
    return {
        "intent": "analyze_match",
        "entities": {"home": home, "away": away, "entity_invalid": True},
        "match": label,
        "status": "NotFound",
        "is_live": False,
        "minute": None,
        "executive_summary": msg,
        "best_markets": [],
        "confidence": {
            "score": 1.0,
            "label": "insufficient",
            "explanation": (
                "Fixture não localizada — confiança muito baixa. "
                "Entidades de time inválidas ou não reconhecidas."
            ),
            "data_sources": ["Entity Validator"],
        },
        "risk": {
            "level": "High",
            "flags": list(reasons or ["invalid_entities"]),
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
        "aurora_version": "Aurora v3.3.1-beta",
        "brain": brain or get_brain_meta(),
        "match_card": None,
    }
