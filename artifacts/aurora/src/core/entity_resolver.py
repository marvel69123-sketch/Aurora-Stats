"""
EntityResolver — unique Source of Truth for team identity.

Phase 5A: consolidates aliases, unicode fold/compact, ID resolution,
ambiguity/candidates, live name matching, and a simple in-memory cache.

Callers should prefer resolve_team / resolve_team_async. Legacy helpers in
copilot_engine and analyze remain as thin compatibility wrappers.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Awaitable

from src.core.team_aliases import TEAM_ALIASES

logger = logging.getLogger(__name__)

# Re-export for gradual migration
__all__ = [
    "TEAM_ALIASES",
    "TeamResolveResult",
    "EntityResolver",
    "get_resolver",
    "resolve_team",
    "resolve_team_async",
    "fold",
    "compact",
    "alias_keys",
    "normalize_team_name",
    "search_variants",
    "name_match",
    "team_score",
    "pick_best_team",
    "match_team_in_fixture_names",
]


# ---------------------------------------------------------------------------
# Unicode / string normalization
# ---------------------------------------------------------------------------

def fold(text: str) -> str:
    """Lowercase, strip accents/apostrophes/hyphens/punctuation → spaced tokens."""
    t = (text or "").lower().strip()
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    t = re.sub(r"[''`´’]", "", t)
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"[-_]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def compact(text: str) -> str:
    """Fully compacted key: O'Higgins → ohiggins, Ñublense → nublense."""
    return re.sub(r"\s+", "", fold(text))


def alias_keys(name: str) -> list[str]:
    """Build lookup keys: raw, spaced, ascii, compacted."""
    key = (name or "").lower().strip()
    key = re.sub(r"[''`´’]", "", key)
    key_spaced = re.sub(r"[-_]+", " ", key)
    key_spaced = re.sub(r"\s+", " ", key_spaced).strip()
    ascii_spaced = (
        unicodedata.normalize("NFKD", key_spaced)
        .encode("ascii", "ignore")
        .decode()
    )
    compact_key = re.sub(r"[\s\-_]+", "", ascii_spaced)
    out: list[str] = []
    for k in (key, key_spaced, ascii_spaced, compact_key, (name or "").lower().strip()):
        if k and k not in out:
            out.append(k)
    return out


def normalize_team_name(name: str) -> str:
    """Resolve aliases / accented variants to the canonical display name."""
    keys = alias_keys(name)
    for candidate in keys:
        if candidate in TEAM_ALIASES:
            canonical = TEAM_ALIASES[candidate]
            logger.warning(
                "[AUDIT] entity_resolver.normalize: %r → %r (alias key=%r)",
                name, canonical, candidate,
            )
            return canonical

    spaced = keys[1] if len(keys) > 1 else (keys[0] if keys else name)
    display = " ".join(w.capitalize() for w in spaced.split()) if spaced else name
    logger.warning(
        "[AUDIT] entity_resolver.normalize: %r → NO ALIAS → %r", name, display,
    )
    return display


def has_alias(name: str) -> bool:
    """True when any alias key maps in TEAM_ALIASES."""
    return any(k in TEAM_ALIASES for k in alias_keys(name))


def search_variants(name: str) -> list[str]:
    """API /teams?search= variants for international / smaller clubs."""
    folded = fold(name)
    compacted = compact(name)
    variants: list[str] = []
    for v in (
        compacted,
        folded,
        (name or "").replace("'", "").replace("'", "").strip(),
        (name or "").strip(),
        folded.replace(" ", "-"),
        folded.split()[0] if folded.split() else folded,
    ):
        if v and v not in variants and len(v) >= 3:
            variants.append(v)
    return variants


def name_match(api_name: str, query: str) -> bool:
    """Fuzzy / contains match against API-Football team names."""
    api_f = fold(api_name)
    q_f = fold(query)
    api_c = compact(api_name)
    q_c = compact(query)
    if not q_f or not api_f:
        return False
    if q_f == api_f or q_c == api_c:
        return True
    if q_f in api_f or api_f in q_f or q_c in api_c or api_c in q_c:
        return True
    q_words = [w for w in q_f.split() if len(w) > 1]
    if q_words and all(w in api_f or w in api_c for w in q_words):
        return True
    hits = sum(1 for w in q_words if w in api_f or w in api_c)
    return bool(q_words) and hits >= max(1, (len(q_words) + 1) // 2)


def team_score(api_team: dict, query: str) -> float:
    """Rank API /teams results — prefer exact/folded/compact match."""
    name = (api_team.get("team") or {}).get("name") or ""
    country = ((api_team.get("team") or {}).get("country") or "").lower()
    q_f, n_f = fold(query), fold(name)
    q_c, n_c = compact(query), compact(name)
    score = 0.0
    if n_c == q_c or n_f == q_f:
        score += 100
    elif q_c in n_c or n_c in q_c or q_f in n_f or n_f in q_f:
        score += 60
    q_words = [w for w in q_f.split() if len(w) > 1]
    if q_words and all(w in n_f or w in n_c for w in q_words):
        score += 40
    else:
        score += 10 * sum(1 for w in q_words if w in n_f or w in n_c)
    if any(c in country for c in ("brazil", "brasil", "chile")):
        score += 15
    if not (api_team.get("team") or {}).get("national"):
        score += 5
    return score


def pick_best_team(teams: list[dict], query: str) -> dict | None:
    """Score and pick the best /teams search hit for *query*."""
    if not teams:
        return None
    ranked = sorted(teams, key=lambda t: team_score(t, query), reverse=True)
    best = ranked[0]
    logger.info(
        "entity_resolver pick_team query=%r selected=%r score=%.1f candidates=%s",
        query,
        (best.get("team") or {}).get("name"),
        team_score(best, query),
        [(t.get("team") or {}).get("name") for t in ranked[:5]],
    )
    return best


def match_team_in_fixture_names(query: str, home: str, away: str) -> bool:
    """Live feed match: query team appears in home or away (folded word match)."""
    q = fold(query)
    if not q:
        return False
    words = [w for w in q.split() if w]
    if not words:
        return False
    h, a = fold(home), fold(away)
    # Prefer EntityResolver name_match when query looks like a full team name
    if name_match(home, query) or name_match(away, query):
        return True
    return all(w in h for w in words) or all(w in a for w in words)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class TeamResolveResult:
    canonical: str | None
    team_id: int | None
    candidates: list[dict[str, Any]] = field(default_factory=list)
    ambiguity: bool = False
    confidence: float = 0.0
    alias_hit: bool = False
    query: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------

_MIN_ID_SCORE = 40.0
_AMBIGUITY_GAP = 15.0  # top vs 2nd within this → ambiguous


class EntityResolver:
    """Single SoT for team alias + ID + live matching."""

    def __init__(self) -> None:
        # cache key → TeamResolveResult (alias-only or full ID resolve)
        self._cache: dict[str, TeamResolveResult] = {}

    def clear_cache(self) -> None:
        self._cache.clear()

    def _cache_key(self, name: str, with_id: bool) -> str:
        return f"{'id' if with_id else 'alias'}:{compact(name) or fold(name)}"

    def resolve_team(self, name: str) -> TeamResolveResult:
        """
        Sync resolution: aliases + normalization only (no API).

        team_id is always None here — use resolve_team_async for ID lookup.
        """
        raw = (name or "").strip()
        if not raw:
            return TeamResolveResult(
                canonical=None,
                team_id=None,
                candidates=[],
                ambiguity=False,
                confidence=0.0,
                alias_hit=False,
                query=raw,
            )

        key = self._cache_key(raw, with_id=False)
        if key in self._cache:
            return self._cache[key]

        alias_hit = has_alias(raw)
        canonical = normalize_team_name(raw)
        confidence = 0.95 if alias_hit else 0.55

        # Ambiguity signal for known collisions (e.g. bare "botafogo" vs PB)
        # — currently exact alias wins; flag only when multiple distinct
        # canonicals share overlapping compact prefixes (rare).
        ambiguity = False
        candidates: list[dict[str, Any]] = []
        if alias_hit:
            candidates.append({"name": canonical, "source": "alias", "score": confidence})
        else:
            candidates.append({"name": canonical, "source": "titlecase", "score": confidence})

        result = TeamResolveResult(
            canonical=canonical,
            team_id=None,
            candidates=candidates,
            ambiguity=ambiguity,
            confidence=confidence,
            alias_hit=alias_hit,
            query=raw,
        )
        self._cache[key] = result
        return result

    async def resolve_team_async(
        self,
        name: str,
        *,
        teams_search: Callable[[str], Awaitable[list[dict]]] | None = None,
        min_score: float = _MIN_ID_SCORE,
    ) -> TeamResolveResult:
        """
        Full resolution: alias normalize + multi-variant /teams search + ID.

        *teams_search* is injectable (defaults to analyze._safe_teams_search)
        so tests can stub the API.
        """
        raw = (name or "").strip()
        base = self.resolve_team(raw)
        if not raw:
            return base

        key = self._cache_key(raw, with_id=True)
        if key in self._cache and self._cache[key].team_id is not None:
            return self._cache[key]

        if teams_search is None:
            from src.routers.analyze import _safe_teams_search
            teams_search = _safe_teams_search

        query_for_api = base.canonical or raw
        all_hits: list[dict] = []
        seen_ids: set[int] = set()

        for variant in search_variants(query_for_api):
            hits = await teams_search(variant)
            logger.info(
                "entity_resolver teams_search variant=%r hits=%d names=%s",
                variant, len(hits),
                [(h.get("team") or {}).get("name") for h in hits[:5]],
            )
            for h in hits:
                tid = (h.get("team") or {}).get("id")
                if tid is not None and tid not in seen_ids:
                    seen_ids.add(tid)
                    all_hits.append(h)
            pick = pick_best_team(hits, query_for_api)
            if pick and team_score(pick, query_for_api) >= min_score:
                return self._finalize_id_result(base, pick, all_hits, query_for_api, key)

        pick = pick_best_team(all_hits, query_for_api)
        if pick:
            return self._finalize_id_result(base, pick, all_hits, query_for_api, key)

        result = TeamResolveResult(
            canonical=base.canonical,
            team_id=None,
            candidates=base.candidates,
            ambiguity=False,
            confidence=min(base.confidence, 0.3),
            alias_hit=base.alias_hit,
            query=raw,
        )
        self._cache[key] = result
        return result

    def _finalize_id_result(
        self,
        base: TeamResolveResult,
        pick: dict,
        all_hits: list[dict],
        query: str,
        cache_key: str,
    ) -> TeamResolveResult:
        ranked = sorted(all_hits, key=lambda t: team_score(t, query), reverse=True)
        top_score = team_score(pick, query)
        ambiguity = False
        if len(ranked) >= 2:
            second = team_score(ranked[1], query)
            if top_score - second < _AMBIGUITY_GAP and top_score < 100:
                ambiguity = True

        candidates = [
            {
                "name": (t.get("team") or {}).get("name"),
                "team_id": (t.get("team") or {}).get("id"),
                "score": round(team_score(t, query), 1),
                "source": "api",
            }
            for t in ranked[:5]
        ]

        # Confidence: map score 40–100 → 0.5–0.98, penalize ambiguity
        conf = min(0.98, max(0.5, (top_score / 100.0) * 0.98))
        if base.alias_hit:
            conf = min(0.99, conf + 0.05)
        if ambiguity:
            conf = max(0.4, conf - 0.2)

        api_name = (pick.get("team") or {}).get("name")
        result = TeamResolveResult(
            canonical=api_name or base.canonical,
            team_id=(pick.get("team") or {}).get("id"),
            candidates=candidates,
            ambiguity=ambiguity,
            confidence=round(conf, 3),
            alias_hit=base.alias_hit,
            query=base.query,
        )
        self._cache[cache_key] = result
        return result


# Module-level singleton
_RESOLVER: EntityResolver | None = None


def get_resolver() -> EntityResolver:
    global _RESOLVER
    if _RESOLVER is None:
        _RESOLVER = EntityResolver()
    return _RESOLVER


def resolve_team(name: str) -> dict[str, Any]:
    """Public sync API — returns the suggested dict shape."""
    return get_resolver().resolve_team(name).to_dict()


async def resolve_team_async(
    name: str,
    *,
    teams_search: Callable[[str], Awaitable[list[dict]]] | None = None,
) -> dict[str, Any]:
    """Public async API with ID resolution."""
    return (await get_resolver().resolve_team_async(name, teams_search=teams_search)).to_dict()
