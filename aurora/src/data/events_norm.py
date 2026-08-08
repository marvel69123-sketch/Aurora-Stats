"""
P2b Wave 2 — Event normalization (append-only, no invention).
"""

from __future__ import annotations

from typing import Any

# Canonical event kinds for live momentum / DRS
KIND_MAP = {
    "goal": "goal",
    "card": "card",
    "subst": "substitution",
    "substitution": "substitution",
    "var": "var",
}


def _kind(raw_type: Any, detail: Any) -> str:
    t = str(raw_type or "").strip().lower()
    d = str(detail or "").strip().lower()
    if t in KIND_MAP:
        kind = KIND_MAP[t]
    elif "goal" in t:
        kind = "goal"
    elif "card" in t:
        kind = "card"
    elif "subst" in t:
        kind = "substitution"
    elif "var" in t:
        kind = "var"
    else:
        kind = t or "other"

    if kind == "goal" and ("own" in d or d == "own goal"):
        return "own_goal"
    if kind == "goal" and "penalty" in d:
        return "penalty_goal"
    if kind == "card" and "red" in d:
        return "red_card"
    if kind == "card" and "yellow" in d:
        return "yellow_card"
    return kind


def _event_id(ev: dict[str, Any], idx: int) -> str:
    if ev.get("event_id") not in (None, ""):
        return str(ev["event_id"])
    if ev.get("id") not in (None, ""):
        return str(ev["id"])
    # Stable synthetic key from facts only (not invented content).
    # Index is used only when the fact key is empty (should not happen for real events).
    parts = [
        str(ev.get("minute") if ev.get("minute") is not None else ""),
        str(ev.get("extra_minute") if ev.get("extra_minute") is not None else ""),
        str(ev.get("team_id") or ev.get("team") or ""),
        str(ev.get("type") or ""),
        str(ev.get("detail") or ""),
        str(ev.get("player_id") or ev.get("player") or ""),
    ]
    key = "|".join(parts)
    if key.strip("|") == "":
        return f"anon|{idx}"
    return key


def normalize_event(ev: Any, *, idx: int = 0) -> dict[str, Any] | None:
    if not isinstance(ev, dict):
        return None
    minute = ev.get("minute")
    if minute is None and isinstance(ev.get("time"), dict):
        minute = ev["time"].get("elapsed")
    extra = ev.get("extra_minute")
    if extra is None and isinstance(ev.get("time"), dict):
        extra = ev["time"].get("extra")
    team = ev.get("team")
    team_id = ev.get("team_id")
    if isinstance(team, dict):
        team_id = team_id or team.get("id")
        team = team.get("name")
    player = ev.get("player")
    player_id = ev.get("player_id")
    if isinstance(player, dict):
        player_id = player_id or player.get("id")
        player = player.get("name")
    raw_type = ev.get("type")
    detail = ev.get("detail")
    return {
        "event_id": _event_id(
            {
                "event_id": ev.get("event_id"),
                "id": ev.get("id"),
                "minute": minute,
                "extra_minute": extra,
                "team_id": team_id,
                "team": team,
                "type": raw_type,
                "detail": detail,
                "player_id": player_id,
                "player": player,
            },
            idx,
        ),
        "minute": minute,
        "extra_minute": extra,
        "team": team,
        "team_id": team_id,
        "type": raw_type,
        "detail": detail,
        "kind": _kind(raw_type, detail),
        "player": player,
        "player_id": player_id,
        "assist": ev.get("assist") if not isinstance(ev.get("assist"), dict) else ev["assist"].get("name"),
        "comments": ev.get("comments"),
    }


def normalize_events(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, ev in enumerate(raw):
        norm = normalize_event(ev, idx=i)
        if not norm:
            continue
        eid = norm["event_id"]
        if eid in seen:
            continue
        seen.add(eid)
        out.append(norm)
    # Chronological when minutes available
    def _sort_key(e: dict[str, Any]) -> tuple:
        m = e.get("minute")
        x = e.get("extra_minute")
        try:
            mi = int(m) if m is not None else -1
        except (TypeError, ValueError):
            mi = -1
        try:
            xi = int(x) if x is not None else 0
        except (TypeError, ValueError):
            xi = 0
        return (mi, xi, e.get("event_id") or "")

    out.sort(key=_sort_key)
    return out


def merge_events_append_only(
    primary: list[dict[str, Any]],
    secondary: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Append-only merge by event_id — primary wins on conflict."""
    merged = list(primary or [])
    seen = {e.get("event_id") for e in merged if e.get("event_id")}
    for ev in secondary or []:
        eid = ev.get("event_id")
        if not eid or eid in seen:
            continue
        seen.add(eid)
        merged.append(ev)
    return normalize_events(merged)


def event_coverage(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    evs = events or []
    kinds: dict[str, int] = {}
    for e in evs:
        k = str(e.get("kind") or "other")
        kinds[k] = kinds.get(k, 0) + 1
    return {
        "count": len(evs),
        "has_goals": any(k.startswith("goal") or k in {"own_goal", "penalty_goal"} for k in kinds),
        "has_cards": any("card" in k for k in kinds),
        "kinds": kinds,
        "covered": len(evs) > 0,
    }
