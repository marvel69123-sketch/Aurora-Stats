"""
P2b Wave 2 — Freshness propagation across related NMB signals.
"""

from __future__ import annotations

import time
from typing import Any

from src.data.cache import TTL_SEC
from src.data.nmb import NormalizedMatchBundle

# Parent → children that inherit stale / fetched_at
PROPAGATION: dict[str, tuple[str, ...]] = {
    "statistics": ("xg",),
    "events": ("live_momentum",),
    "status": ("live_momentum", "score"),
    "lineups": ("narrative",),
    "odds": ("narrative",),
    "injuries": ("narrative",),
    "calendar": ("narrative",),
}

LIVE_SHORT = frozenset(
    {"1H", "2H", "HT", "ET", "BT", "P", "LIVE", "INT", "SUSP"}
)


def _ttl_for(signal: str, *, live: bool) -> float:
    if signal == "statistics":
        return TTL_SEC["statistics" if live else "statistics_pre"]
    if signal == "events":
        return TTL_SEC["events" if live else "events_pre"]
    if signal == "xg":
        return TTL_SEC["statistics" if live else "statistics_pre"]
    if signal == "live_momentum":
        return TTL_SEC["events" if live else "events_pre"]
    if signal == "status":
        return TTL_SEC["status"] if live else TTL_SEC.get("fixture", 600.0)
    return float(TTL_SEC.get(signal, 300.0))


def propagate_freshness(
    nmb: NormalizedMatchBundle,
    *,
    now: float | None = None,
) -> dict[str, Any]:
    """
    Demote dependent signals when parents are stale; stamp ages.
    Mutates nmb signals in place. Returns freshness report.
    """
    ts = now if now is not None else time.time()
    live = str(nmb.status_short or "").upper() in LIVE_SHORT or bool(nmb.user_wants_live)
    ages: dict[str, float | None] = {}
    demoted: list[str] = []

    for name, slot in list(nmb.signals.items()):
        if slot.fetched_at is not None:
            ages[name] = round(ts - float(slot.fetched_at), 3)
            ttl = _ttl_for(name, live=live)
            if ages[name] is not None and ages[name] > ttl and slot.quality == "confirmed":
                slot.quality = "stale"
                slot.note = (slot.note or "") + "|ttl_exceeded"
                demoted.append(name)
        else:
            ages[name] = None

    for parent, children in PROPAGATION.items():
        p = nmb.signals.get(parent)
        if not p:
            continue
        if p.quality != "stale":
            continue
        for child in children:
            c = nmb.signals.get(child)
            if not c:
                continue
            if c.quality == "confirmed":
                c.quality = "stale"
                c.note = (c.note or "") + f"|inherited_stale_from_{parent}"
                demoted.append(child)
            if c.fetched_at is None and p.fetched_at is not None:
                c.fetched_at = p.fetched_at
                ages[child] = round(ts - float(p.fetched_at), 3)

    # Live ask + missing live signals → flag on meta
    live_gap = False
    if nmb.user_wants_live or live:
        for name in ("events", "statistics", "live_momentum"):
            s = nmb.signals.get(name)
            if not s or s.quality in {"missing", "empty", "rate_limited"}:
                live_gap = True
                break
            if s.quality == "stale":
                live_gap = True
                break

    report = {
        "ages_sec": ages,
        "demoted": sorted(set(demoted)),
        "live_context": live,
        "live_gap": live_gap,
        "freshness_score": _freshness_score(nmb, ages, live=live),
    }
    nmb.meta["freshness"] = report
    return report


def _freshness_score(
    nmb: NormalizedMatchBundle,
    ages: dict[str, float | None],
    *,
    live: bool,
) -> float:
    """0..1 — share of important signals that are confirmed and within TTL."""
    important = ("status", "statistics", "events", "xg", "live_momentum", "score")
    score = 0.0
    weight = 0.0
    for name in important:
        s = nmb.signals.get(name)
        if not s:
            continue
        weight += 1.0
        if s.quality == "confirmed":
            age = ages.get(name)
            ttl = _ttl_for(name, live=live)
            if age is None:
                score += 0.85  # confirmed but unstamped
            elif age <= ttl:
                score += 1.0
            else:
                score += 0.35
        elif s.quality == "stale":
            score += 0.35
        elif s.quality == "inferred":
            score += 0.2
    if weight <= 0:
        return 0.0
    return round(score / weight, 4)
