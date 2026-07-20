"""
P2b Wave 2 — Live enrichment / momentum from confirmed events + score/status.
Never invents goals or minutes.
"""

from __future__ import annotations

from typing import Any

LIVE_SHORT = frozenset(
    {"1H", "2H", "HT", "ET", "BT", "P", "LIVE", "INT", "SUSP"}
)
FINISHED_SHORT = frozenset({"FT", "AET", "PEN"})


def _minute(status: dict[str, Any] | None, score_block: dict | None = None) -> int | None:
    if isinstance(status, dict):
        for k in ("minute", "elapsed"):
            if status.get(k) is not None:
                try:
                    return int(status[k])
                except (TypeError, ValueError):
                    pass
    return None


def _goal_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for e in events or []:
        kind = str(e.get("kind") or "").lower()
        typ = str(e.get("type") or "").lower()
        if kind in {"goal", "own_goal", "penalty_goal"} or typ == "goal":
            out.append(e)
    return out


def build_live_momentum(
    *,
    status_short: str | None,
    status: dict[str, Any] | None,
    score: dict[str, Any] | None,
    events: list[dict[str, Any]] | None,
    home_id: int | None = None,
    away_id: int | None = None,
) -> dict[str, Any] | None:
    """
    Derive live momentum snapshot from confirmed facts only.
    Returns None when there is no live/finished context and no events.
    """
    short = str(status_short or "").upper()
    is_live = short in LIVE_SHORT
    is_finished = short in FINISHED_SHORT or short.startswith("FT")
    evs = list(events or [])
    goals = _goal_events(evs)
    minute = _minute(status if isinstance(status, dict) else None)

    cur = {}
    if isinstance(score, dict):
        cur = score.get("current") or {}
    try:
        sh = int(cur["home"]) if cur.get("home") is not None else None
    except (TypeError, ValueError):
        sh = None
    try:
        sa = int(cur["away"]) if cur.get("away") is not None else None
    except (TypeError, ValueError):
        sa = None

    if not is_live and not is_finished and not goals and sh is None and sa is None:
        return None

    # Recent window: last 15' of available event minutes
    recent_goals = []
    if minute is not None:
        lo = max(0, minute - 15)
        for g in goals:
            try:
                gm = int(g.get("minute")) if g.get("minute") is not None else None
            except (TypeError, ValueError):
                gm = None
            if gm is not None and lo <= gm <= minute + 2:
                recent_goals.append(g)
    else:
        recent_goals = goals[-3:] if goals else []

    home_goals = 0
    away_goals = 0
    for g in goals:
        tid = g.get("team_id")
        kind = str(g.get("kind") or "")
        if home_id is not None and tid == home_id:
            if kind == "own_goal":
                away_goals += 1
            else:
                home_goals += 1
        elif away_id is not None and tid == away_id:
            if kind == "own_goal":
                home_goals += 1
            else:
                away_goals += 1

    pressure = "balanced"
    if len(recent_goals) >= 2:
        # side of last recent goal
        last = recent_goals[-1]
        tid = last.get("team_id")
        if home_id is not None and tid == home_id:
            pressure = "home"
        elif away_id is not None and tid == away_id:
            pressure = "away"
        else:
            pressure = "active"
    elif len(recent_goals) == 1:
        pressure = "active"

    cards = sum(
        1
        for e in evs
        if "card" in str(e.get("kind") or "").lower()
        or str(e.get("type") or "").lower() == "card"
    )

    return {
        "status_short": short or None,
        "is_live": is_live,
        "is_finished": is_finished,
        "minute": minute,
        "score": {"home": sh, "away": sa},
        "goals_from_events": {"home": home_goals, "away": away_goals},
        "recent_goals_15m": len(recent_goals),
        "pressure_side": pressure,
        "cards_total": cards,
        "events_used": len(evs),
        "source": "events+status+score",
    }


def live_enrichment_quality(
    momentum: dict[str, Any] | None,
    *,
    events_quality: str,
    status_quality: str,
) -> str:
    if not momentum:
        return "missing"
    if events_quality == "stale" or status_quality == "stale":
        return "stale"
    if events_quality == "rate_limited":
        return "rate_limited"
    # Confirmed when we have live/finished status confirmed OR events confirmed
    if status_quality == "confirmed" and (
        momentum.get("is_live") or momentum.get("is_finished") or momentum.get("events_used", 0) > 0
    ):
        return "confirmed"
    if events_quality == "confirmed" and momentum.get("events_used", 0) > 0:
        return "confirmed"
    return "missing"
