"""
P2b Wave 2 — xG integration for NMB.

Confirmed xG from provider statistics only.
Optional season GPG prior as inferred (NMB slot only — never writes statistics.*.xg).
"""

from __future__ import annotations

from typing import Any

XG_FIELD_KEYS = ("xg", "expected_goals", "xG", "Expected Goals", "expectedGoals")


def _to_float(val: Any) -> float | None:
    if val is None or val == "":
        return None
    if isinstance(val, str):
        s = val.strip().replace("%", "")
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def extract_side_xg(row: dict[str, Any] | None) -> float | None:
    """Extract numeric xG from a team statistics row — no invention."""
    if not isinstance(row, dict):
        return None
    for k in XG_FIELD_KEYS:
        v = _to_float(row.get(k))
        if v is not None:
            return v
    return None


def extract_confirmed_xg(stats: Any) -> dict[str, float | None] | None:
    """
    Both-or-partial sides from confirmed stats.
    Returns None only when neither side has numeric xG.
    """
    if not isinstance(stats, dict):
        return None
    home = extract_side_xg(stats.get("home") if isinstance(stats.get("home"), dict) else None)
    away = extract_side_xg(stats.get("away") if isinstance(stats.get("away"), dict) else None)
    if home is None and away is None:
        return None
    return {"home": home, "away": away, "source": "statistics"}


def _gpg_from_standing(row: dict[str, Any] | None) -> float | None:
    if not isinstance(row, dict):
        return None
    gf = row.get("goals_for")
    played = row.get("played")
    try:
        gf_f = float(gf)
        pl = float(played)
    except (TypeError, ValueError):
        return None
    if pl <= 0:
        return None
    return round(gf_f / pl, 3)


def infer_xg_from_standings(standings: Any) -> dict[str, Any] | None:
    """
    Season GPG prior as inferred xG proxy.
    Never labeled confirmed. Never written into engine statistics.
    """
    if not isinstance(standings, dict):
        return None
    home = _gpg_from_standing(standings.get("home"))
    away = _gpg_from_standing(standings.get("away"))
    if home is None and away is None:
        return None
    return {
        "home": home,
        "away": away,
        "source": "standings_gpg_prior",
        "inferred": True,
        "note": "season_gpg_prior_not_match_xg",
    }


def resolve_xg_slot(
    stats: Any,
    standings: Any,
    *,
    allow_inferred: bool = True,
) -> tuple[Any, str, str, str | None]:
    """
    Returns (value, quality, source, note).
    Confirmed always wins over inferred.
    """
    confirmed = extract_confirmed_xg(stats)
    if confirmed is not None:
        # Partial side still confirmed for the present side(s)
        both = confirmed.get("home") is not None and confirmed.get("away") is not None
        note = None if both else "partial_side_xg"
        return confirmed, "confirmed", "statistics", note

    if allow_inferred:
        prior = infer_xg_from_standings(standings)
        if prior is not None:
            return prior, "inferred", "standings_gpg_prior", prior.get("note")

    return None, "missing", "none", None
