"""
P2b Wave 3 — Lineup normalization (confirmed XI only, no invention).
"""

from __future__ import annotations

from typing import Any


def _norm_player(p: Any) -> dict[str, Any] | None:
    if not isinstance(p, dict):
        return None
    # analyze shape
    if p.get("name") or p.get("id"):
        return {
            "id": p.get("id"),
            "name": p.get("name"),
            "number": p.get("number"),
            "position": p.get("position") or p.get("pos"),
            "grid": p.get("grid"),
        }
    # raw API startXI shape
    player = p.get("player") or {}
    if isinstance(player, dict) and (player.get("name") or player.get("id")):
        return {
            "id": player.get("id"),
            "name": player.get("name"),
            "number": player.get("number"),
            "position": player.get("pos") or player.get("position"),
            "grid": player.get("grid"),
        }
    return None


def normalize_side_lineup(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict) or not raw:
        return None
    xi_raw = raw.get("starting_xi") or raw.get("startXI") or []
    subs_raw = raw.get("substitutes") or []
    xi = []
    for p in xi_raw:
        np = _norm_player(p)
        if np:
            xi.append(np)
    subs = []
    for p in subs_raw:
        np = _norm_player(p)
        if np:
            subs.append(np)
    coach = raw.get("coach")
    if isinstance(coach, dict):
        coach_out = {
            "id": coach.get("id"),
            "name": coach.get("name"),
            "photo": coach.get("photo"),
        }
    else:
        coach_out = {"id": None, "name": coach, "photo": None} if coach else None
    formation = raw.get("formation")
    if not formation and not xi and not coach_out:
        return None
    return {
        "formation": formation,
        "coach": coach_out,
        "starting_xi": xi,
        "substitutes": subs,
        "xi_count": len(xi),
        "confirmed_xi": len(xi) >= 11,
    }


def normalize_lineups(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    home = normalize_side_lineup(raw.get("home"))
    away = normalize_side_lineup(raw.get("away"))
    if not home and not away:
        return None
    return {
        "home": home,
        "away": away,
        "both_xi": bool(
            home
            and away
            and home.get("confirmed_xi")
            and away.get("confirmed_xi")
        ),
        "any_formation": bool(
            (home or {}).get("formation") or (away or {}).get("formation")
        ),
    }


def lineup_coverage(value: Any, quality: str) -> float:
    if quality not in {"confirmed", "stale"} or not isinstance(value, dict):
        return 0.0
    score = 0.0
    for side in ("home", "away"):
        row = value.get(side) or {}
        if not isinstance(row, dict):
            continue
        if row.get("formation"):
            score += 0.15
        if row.get("confirmed_xi"):
            score += 0.35
        elif (row.get("xi_count") or 0) > 0:
            score += 0.2
    if quality == "stale":
        score *= 0.5
    return round(min(1.0, score), 4)
