"""
ENTITY-EDGE-001 — Edge entity resolution (RapidFuzz + league-aware).

Additive wrapper around alias/fuzzy identity. Fail-open.
Feature flag: ENABLE_ENTITY_EDGE (default OFF — legacy path unchanged).

Does not invent fixtures. Does not weaken PATCH-001 entity_safety stopwords.
Does not modify methodology/market/confidence/intelligence/learning engines.
"""

from __future__ import annotations

import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_FLAG_ENV = "ENABLE_ENTITY_EDGE"

# RapidFuzz WRatio cutoff (0–100). Tuned above difflib ~0.74 equivalent.
_RF_CUTOFF = 86.0
_RF_MIN_LEN = 4

# League / geography cues for short-name collisions
_LEAGUE_CUES: dict[str, re.Pattern[str]] = {
    "ecuador": re.compile(
        r"\b(?:"
        r"ecuador|equador|guayaquil|liga\s*pro|serie\s*a\s*(?:do\s*)?ecuador|"
        r"barcelona\s*sc|barcelona\s*sporting|emelec|ldu|independiente\s*del\s*valle"
        r")\b",
        re.I,
    ),
    "la_liga": re.compile(
        r"\b(?:"
        r"laliga|la\s*liga|spain|espanha|españa|espana|uefa|champions|"
        r"camp\s*nou|catalunha|catalonia|madrid|atm|atletico\s*madrid"
        r")\b",
        re.I,
    ),
    "brasileirao": re.compile(
        r"\b(?:"
        r"brasileir|brasileirao|serie\s*a|galo|mineiro|bahia|flamengo|"
        r"palmeiras|corinthians|santos|botafogo|fluminense|sao\s*paulo|"
        r"vasco|gremio|internacional|cruzeiro|fortaleza"
        r")\b",
        re.I,
    ),
}

# Ambiguous short tokens → (default_canon, league→canon overrides)
# Exact multi-word aliases (barcelona sc, real madrid, …) still win upstream.
_EDGE_COLLISIONS: dict[str, dict[str, Any]] = {
    "barcelona": {
        "default": "Barcelona",
        "by_league": {
            "ecuador": "Barcelona SC",
            "la_liga": "Barcelona",
        },
    },
    "atletico": {
        "default": "Atletico Madrid",
        "by_league": {
            "brasileirao": "Atletico Mineiro",
            "la_liga": "Atletico Madrid",
        },
    },
    "atlético": {
        "default": "Atletico Madrid",
        "by_league": {
            "brasileirao": "Atletico Mineiro",
            "la_liga": "Atletico Madrid",
        },
    },
}

# Explicit compound forms that must resolve (league cues optional)
_EXPLICIT_CANONS: dict[str, str] = {
    "barcelona sc": "Barcelona SC",
    "barcelona sporting club": "Barcelona SC",
    "barcelona guayaquil": "Barcelona SC",
    "barcelona de guayaquil": "Barcelona SC",
    "real madrid": "Real Madrid",
    "atletico madrid": "Atletico Madrid",
    "atlético madrid": "Atletico Madrid",
    "atleti": "Atletico Madrid",
}


@dataclass
class EdgeResolveResult:
    canonical: str | None
    confidence: float = 0.0
    source: str = "none"
    candidates: list[str] = field(default_factory=list)
    league_hint: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical": self.canonical,
            "confidence": self.confidence,
            "source": self.source,
            "candidates": list(self.candidates),
            "league_hint": self.league_hint,
            "notes": list(self.notes),
        }


def entity_edge_enabled() -> bool:
    """ENABLE_ENTITY_EDGE default OFF — empty/missing → legacy unchanged."""
    raw = (os.environ.get(_FLAG_ENV) or "0").strip().lower()
    return raw in {"1", "true", "on", "yes"}


def fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def detect_league_cues(message: str, league_hint: str | None = None) -> str | None:
    """Return first matching league key from hint or message text."""
    if league_hint:
        key = fold(league_hint).replace(" ", "_")
        if key in _LEAGUE_CUES:
            return key
        # Loose hint synonyms
        if key in {"ecuador", "equador", "liga_pro", "guayaquil"}:
            return "ecuador"
        if key in {"la_liga", "laliga", "spain", "espanha", "uefa"}:
            return "la_liga"
        if key in {"brasileirao", "brasil", "brazil", "serie_a_br"}:
            return "brasileirao"
    msg = message or ""
    for league, pat in _LEAGUE_CUES.items():
        if pat.search(msg):
            return league
    return None


def _is_stopword(token: str) -> bool:
    """Honor PATCH-001 stopwords — never fuzzy-map them."""
    try:
        from src.conversation.entity_safety import is_entity_stopword

        return bool(is_entity_stopword(token))
    except Exception:
        return False


def _explicit_hit(name: str) -> str | None:
    f = fold(name)
    if f in _EXPLICIT_CANONS:
        return _EXPLICIT_CANONS[f]
    # Compact key
    compact = re.sub(r"\s+", "", f)
    for key, canon in _EXPLICIT_CANONS.items():
        if re.sub(r"\s+", "", key) == compact:
            return canon
    return None


def disambiguate_short_name(
    name: str,
    *,
    message: str = "",
    league_hint: str | None = None,
    current_canon: str | None = None,
) -> EdgeResolveResult | None:
    """
    League-aware override for known short-name collisions.

    Returns None when no edge rule applies (caller keeps legacy alias).
    """
    f = fold(name)
    rule = _EDGE_COLLISIONS.get(f)
    if not rule:
        return None

    league = detect_league_cues(message, league_hint)
    by_league: dict[str, str] = rule.get("by_league") or {}
    default = str(rule.get("default") or "")
    candidates = list({default, *by_league.values()})
    if current_canon and current_canon not in candidates:
        candidates.append(current_canon)

    if league and league in by_league:
        chosen = by_league[league]
        return EdgeResolveResult(
            canonical=chosen,
            confidence=0.93,
            source="edge_league",
            candidates=candidates,
            league_hint=league,
            notes=[f"disambiguate:{f}->{chosen}:{league}"],
        )

    # No cue → keep default (matches existing TEAM_ALIASES for barcelona/atletico)
    if default:
        return EdgeResolveResult(
            canonical=default,
            confidence=0.90 if current_canon == default or not current_canon else 0.88,
            source="edge_default",
            candidates=candidates,
            league_hint=league,
            notes=[f"disambiguate:{f}->{default}:default"],
        )
    return None


def _alias_canonical(name: str) -> str | None:
    try:
        from src.core.entity_resolver import alias_keys
        from src.core.team_aliases import TEAM_ALIASES

        for candidate in alias_keys(name):
            if candidate in TEAM_ALIASES:
                return TEAM_ALIASES[candidate]
    except Exception as exc:
        logger.debug("entity_edge alias lookup fail-open: %s", exc)
    return None


def _rf_candidates() -> list[tuple[str, str]]:
    """(query_string, canonical) pairs for RapidFuzz."""
    from src.core.team_aliases import TEAM_ALIASES

    pairs: dict[str, str] = {}
    for key, canonical in TEAM_ALIASES.items():
        canon = str(canonical or "").strip()
        if not canon:
            continue
        for raw in (key, canon):
            f = fold(str(raw))
            if f and len(f) >= _RF_MIN_LEN:
                pairs.setdefault(f, canon)
            c = re.sub(r"\s+", "", f)
            if c and len(c) >= _RF_MIN_LEN:
                pairs.setdefault(c, canon)
    return sorted(pairs.items(), key=lambda x: x[0])


def rapidfuzz_correct_team(
    name: str,
    *,
    cutoff: float = _RF_CUTOFF,
) -> tuple[str | None, float]:
    """
    Typo correction via RapidFuzz against TEAM_ALIASES.

    Never invents names outside the alias table. Skips stopwords / short tokens.
    """
    raw = (name or "").strip()
    q = fold(raw)
    if not q or len(q) < _RF_MIN_LEN:
        return None, 0.0
    if _is_stopword(raw):
        return None, 0.0

    try:
        from rapidfuzz import fuzz, process
    except ImportError:
        logger.debug("entity_edge: rapidfuzz not installed — fail-open")
        return None, 0.0

    choices = _rf_candidates()
    if not choices:
        return None, 0.0

    keys = [k for k, _ in choices]
    # Prefer token_sort_ratio for multi-word; WRatio as primary
    result = process.extractOne(
        q,
        keys,
        scorer=fuzz.WRatio,
        score_cutoff=cutoff,
    )
    if not result:
        # Compact fallback
        qc = re.sub(r"\s+", "", q)
        if len(qc) >= _RF_MIN_LEN:
            result = process.extractOne(
                qc,
                keys,
                scorer=fuzz.WRatio,
                score_cutoff=cutoff,
            )
    if not result:
        return None, 0.0

    best_key, score, _idx = result
    canon_map = dict(choices)
    canon = canon_map.get(best_key)
    if not canon:
        return None, 0.0
    return canon, round(float(score) / 100.0, 3)


def maybe_override_alias(
    raw: str,
    alias_canon: str,
    *,
    message: str = "",
    league_hint: str | None = None,
) -> str | None:
    """
    When edge ON: optionally override a bare ambiguous alias with league cue.

    Returns new canon or None to keep alias_canon unchanged.
    """
    if not entity_edge_enabled():
        return None
    try:
        # Explicit compounds never overridden away from their exact target
        explicit = _explicit_hit(raw)
        if explicit:
            return explicit if explicit != alias_canon else None

        f = fold(raw)
        if f not in _EDGE_COLLISIONS:
            return None
        edge = disambiguate_short_name(
            raw,
            message=message,
            league_hint=league_hint,
            current_canon=alias_canon,
        )
        if edge and edge.canonical and edge.canonical != alias_canon:
            # Only override when a league cue actually selected a different club
            if edge.source == "edge_league":
                return edge.canonical
        return None
    except Exception as exc:
        logger.debug("maybe_override_alias fail-open: %s", exc)
        return None


def resolve_edge_entity(
    name: str,
    *,
    message: str = "",
    league_hint: str | None = None,
) -> EdgeResolveResult:
    """
    Public edge resolver.

    Order: explicit compound → exact alias (+ league override) → RapidFuzz → miss.
    When flag OFF, returns source=disabled (caller must use legacy).
    """
    raw = (name or "").strip()
    if not entity_edge_enabled():
        return EdgeResolveResult(
            canonical=None,
            confidence=0.0,
            source="disabled",
            notes=["ENABLE_ENTITY_EDGE=0"],
        )
    if not raw:
        return EdgeResolveResult(canonical=None, source="empty")

    try:
        # 1) Explicit compounds (Barcelona SC, Real Madrid, Atletico Madrid)
        explicit = _explicit_hit(raw)
        if explicit:
            return EdgeResolveResult(
                canonical=explicit,
                confidence=1.0,
                source="edge_explicit",
                candidates=[explicit],
                league_hint=detect_league_cues(message, league_hint),
                notes=[f"explicit:{raw}->{explicit}"],
            )

        # 2) Exact alias + optional league disambiguation
        alias = _alias_canonical(raw)
        if alias:
            override = maybe_override_alias(
                raw, alias, message=message, league_hint=league_hint
            )
            if override:
                return EdgeResolveResult(
                    canonical=override,
                    confidence=0.93,
                    source="edge_league",
                    candidates=[alias, override],
                    league_hint=detect_league_cues(message, league_hint),
                    notes=[f"alias_override:{alias}->{override}"],
                )
            # Bare collision without cue: report default (same as alias)
            if fold(raw) in _EDGE_COLLISIONS:
                edge = disambiguate_short_name(
                    raw, message=message, league_hint=league_hint, current_canon=alias
                )
                if edge and edge.canonical:
                    return edge
            return EdgeResolveResult(
                canonical=alias,
                confidence=1.0,
                source="alias",
                candidates=[alias],
                league_hint=detect_league_cues(message, league_hint),
                notes=[f"alias:{raw}->{alias}"],
            )

        # 3) RapidFuzz typo path (skip stopwords)
        if _is_stopword(raw):
            return EdgeResolveResult(
                canonical=None,
                source="stopword",
                notes=["entity_safety_stopword"],
            )

        hit, score = rapidfuzz_correct_team(raw)
        if hit:
            # League re-check if RapidFuzz landed on a collision family
            override = maybe_override_alias(
                fold(hit).split()[0] if hit else raw,
                hit,
                message=message or raw,
                league_hint=league_hint,
            )
            # Prefer disambiguating from the *query* token when it is a short name
            if fold(raw) in _EDGE_COLLISIONS:
                edge = disambiguate_short_name(
                    raw, message=message, league_hint=league_hint, current_canon=hit
                )
                if edge and edge.source == "edge_league" and edge.canonical:
                    return edge
            return EdgeResolveResult(
                canonical=override or hit,
                confidence=float(score),
                source="rapidfuzz",
                candidates=[hit],
                league_hint=detect_league_cues(message, league_hint),
                notes=[f"rapidfuzz:{raw}->{override or hit}:{score}"],
            )

        return EdgeResolveResult(
            canonical=None,
            confidence=0.0,
            source="miss",
            league_hint=detect_league_cues(message, league_hint),
        )
    except Exception as exc:
        logger.debug("resolve_edge_entity fail-open: %s", exc)
        return EdgeResolveResult(
            canonical=None,
            source="error",
            notes=[f"fail_open:{exc}"],
        )


def edge_fuzzy_correct(
    name: str,
    *,
    message: str = "",
    league_hint: str | None = None,
    cutoff: float = _RF_CUTOFF,
) -> tuple[str | None, float]:
    """
    Drop-in enhancer for entity_resolver.fuzzy_correct_team when flag ON.

    Returns (None, 0.0) to signal caller to keep legacy difflib path.
    """
    if not entity_edge_enabled():
        return None, 0.0
    try:
        result = resolve_edge_entity(name, message=message, league_hint=league_hint)
        if result.canonical and result.source in {
            "edge_explicit",
            "edge_league",
            "edge_default",
            "alias",
            "rapidfuzz",
        }:
            conf = result.confidence
            if result.source == "rapidfuzz":
                # Already 0–1 from rapidfuzz_correct_team
                return result.canonical, conf
            return result.canonical, conf if conf > 0 else 1.0
        # Try pure RapidFuzz even if resolve missed alias path
        return rapidfuzz_correct_team(name, cutoff=cutoff)
    except Exception as exc:
        logger.debug("edge_fuzzy_correct fail-open: %s", exc)
        return None, 0.0
