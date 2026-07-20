"""
P2b Wave 1 — Data Richness Score (DRS).
P2b Wave 2 — recalibration for xG / events / live_momentum / stale recovery.

Does not modify confidence_engine formulas.
"""

from __future__ import annotations

from typing import Any

from src.data.nmb import NormalizedMatchBundle, SignalSlot


def _q(slot: SignalSlot | None) -> str:
    return str(slot.quality) if slot else "missing"


def score_binding(nmb: NormalizedMatchBundle) -> int:
    bq = str(nmb.binding_quality or "").upper()
    if bq in {"FICTION", "INVALID", "NONE"}:
        if not nmb.home and not nmb.away and not nmb.fixture_id:
            return 0
    if bq in {"CLARIFY", "AMBIGUOUS"}:
        return 2
    if bq == "TEAM_ONLY":
        return 4
    if nmb.fixture_id and int(nmb.fixture_id) > 0:
        status_ok = _q(nmb.signals.get("status")) == "confirmed"
        kickoff_ok = bool(nmb.kickoff)
        if status_ok and kickoff_ok:
            return 20
        return 18
    if nmb.home and nmb.away:
        return 10
    if nmb.home or nmb.away:
        return 4
    return 0


def _core_points(name: str, q: str, confirmed: int, inferred: int) -> int:
    """Wave 2: stale recovers half confirmed credit (cache SWR)."""
    if q == "confirmed":
        return confirmed
    if q == "inferred":
        return inferred
    if q == "stale":
        return max(1, confirmed // 2)
    return 0


def score_core(nmb: NormalizedMatchBundle) -> tuple[int, dict[str, int]]:
    table = {
        "statistics": (12, 4),
        "xg": (12, 3),
        "standings": (10, 4),
        "events": (8, 2),
    }
    parts: dict[str, int] = {}
    total = 0
    for name, (c_pts, i_pts) in table.items():
        q = _q(nmb.signals.get(name))
        pts = _core_points(name, q, c_pts, i_pts)
        parts[name] = pts
        total += pts

    # live_or_finished: status confirmed + non-NS
    live_pts = 0
    status = nmb.signals.get("status")
    if status and status.quality in {"confirmed", "stale"}:
        short = str(nmb.status_short or "").upper()
        if short and short not in {"NS", "TBD", "PST", "CANC", "ABD", "AWD", "WO"}:
            live_pts = 8 if status.quality == "confirmed" else 4
    parts["live_or_finished"] = live_pts
    total += live_pts
    return min(50, total), parts


def score_context(nmb: NormalizedMatchBundle) -> tuple[int, dict[str, int]]:
    weights = {"lineups": 8, "score": 4, "h2h": 4, "referee": 4}
    parts: dict[str, int] = {}
    total = 0
    for name, pts in weights.items():
        q = _q(nmb.signals.get(name))
        if q == "confirmed":
            parts[name] = pts
        elif q == "stale":
            parts[name] = max(1, pts // 2)
        else:
            parts[name] = 0
        total += parts[name]

    # Wave 2 — live_momentum fills unused H2H budget when present
    lm_q = _q(nmb.signals.get("live_momentum"))
    if lm_q == "confirmed":
        # If h2h missing, award up to 6; else +2 synergy on top of remaining cap
        if parts.get("h2h", 0) == 0:
            parts["live_momentum"] = 6
        else:
            parts["live_momentum"] = 2
        total += parts["live_momentum"]
    elif lm_q == "stale":
        parts["live_momentum"] = 3 if parts.get("h2h", 0) == 0 else 1
        total += parts["live_momentum"]
    else:
        parts["live_momentum"] = 0

    # Wave 3 — calendar context when confirmed (uses residual context budget)
    cal_q = _q(nmb.signals.get("calendar"))
    if cal_q == "confirmed":
        parts["calendar"] = 4
        total += 4
    elif cal_q == "stale":
        parts["calendar"] = 2
        total += 2
    else:
        parts["calendar"] = 0

    return min(20, total), parts


def score_market(nmb: NormalizedMatchBundle) -> tuple[int, dict[str, int]]:
    odds = nmb.signals.get("odds")
    parts = {"pre_match_odd": 0, "live_multi": 0}
    total = 0
    if odds and odds.quality == "confirmed":
        parts["pre_match_odd"] = 6
        total += 6
        val = odds.value
        if isinstance(val, dict) and (val.get("live") or val.get("multi")):
            parts["live_multi"] = 4
            total += 4
    elif odds and odds.quality == "stale":
        # Wave 3 — stale odds still recover market half-credit
        parts["pre_match_odd"] = 3
        total += 3
    return min(10, total), parts


def _wave2_synergy(nmb: NormalizedMatchBundle) -> int:
    """Small bonus when xG + events + live context co-occur (T3/T4 lift)."""
    xg_ok = _q(nmb.signals.get("xg")) in {"confirmed", "stale"}
    ev_ok = _q(nmb.signals.get("events")) in {"confirmed", "stale"}
    live_ok = _q(nmb.signals.get("live_momentum")) in {"confirmed", "stale"}
    if xg_ok and ev_ok and live_ok:
        return 4
    if xg_ok and ev_ok:
        return 2
    return 0


def _wave3_premium(nmb: NormalizedMatchBundle) -> int:
    """
    Wave 3 premium edge — odds/calendar/lineups/injuries/narrative.
    Additive; capped so max DRS remains 100.
    """
    bonus = 0
    odds_ok = _q(nmb.signals.get("odds")) in {"confirmed", "stale"}
    cal_ok = _q(nmb.signals.get("calendar")) in {"confirmed", "stale"}
    lu_ok = _q(nmb.signals.get("lineups")) in {"confirmed", "stale"}
    if odds_ok:
        bonus += 4
    if cal_ok:
        bonus += 3
    if lu_ok:
        val = (nmb.signals.get("lineups") or SignalSlot("lineups")).value
        if isinstance(val, dict) and (val.get("both_xi") or val.get("any_formation")):
            bonus += 3
        else:
            bonus += 1
    if _q(nmb.signals.get("injuries")) == "confirmed":
        bonus += 2
    if _q(nmb.signals.get("narrative")) == "confirmed":
        narr = (nmb.signals.get("narrative") or SignalSlot("narrative")).value
        if isinstance(narr, dict) and narr.get("premium_ready"):
            bonus += 2
        elif isinstance(narr, dict) and len(narr.get("tags") or []) >= 3:
            bonus += 1
    # Cluster bonus: calendar + lineups (premium pre-match pack)
    if cal_ok and lu_ok:
        bonus += 2
    if odds_ok and lu_ok and cal_ok:
        bonus += 2
    return min(12, bonus)


def _penalties(nmb: NormalizedMatchBundle) -> dict[str, int]:
    inference = 0
    for name in ("statistics", "xg", "standings", "events"):
        if _q(nmb.signals.get(name)) == "inferred":
            inference += 3
    inference = min(15, inference)

    freshness = 0
    if nmb.user_wants_live:
        for name in ("statistics", "events", "xg", "live_momentum"):
            q = _q(nmb.signals.get(name))
            if q == "stale":
                freshness += 5
        freshness = min(10, freshness)

    rate_limit = 5 if nmb.rate_limited else 0
    assume = 5 if str(nmb.meta.get("binding_assume_undisclosed")) else 0

    return {
        "inference": inference,
        "freshness": freshness,
        "rate_limit": rate_limit,
        "assume_undisclosed": assume,
    }


def tier_of(drs: int) -> str:
    if drs < 20:
        return "T0"
    if drs < 40:
        return "T1"
    if drs < 60:
        return "T2"
    if drs < 80:
        return "T3"
    return "T4"


def compute_drs(nmb: NormalizedMatchBundle) -> dict[str, Any]:
    binding = score_binding(nmb)
    core, core_parts = score_core(nmb)
    context, ctx_parts = score_context(nmb)
    market, mkt_parts = score_market(nmb)
    synergy = _wave2_synergy(nmb)
    premium = _wave3_premium(nmb)
    pens = _penalties(nmb)
    pen_total = sum(pens.values())
    raw = binding + core + context + market + synergy + premium - pen_total
    drs = max(0, min(100, int(raw)))
    tier = tier_of(drs)

    confirmed = [n for n, s in nmb.signals.items() if s.quality == "confirmed"]
    inferred = [n for n, s in nmb.signals.items() if s.quality == "inferred"]
    missing = [
        n
        for n, s in nmb.signals.items()
        if s.quality in {"missing", "empty", "rate_limited"}
    ]
    stale = [n for n, s in nmb.signals.items() if s.quality == "stale"]

    return {
        "drs": drs,
        "tier": tier,
        "components": {
            "binding": binding,
            "core": core,
            "context": context,
            "market": market,
            "synergy": synergy,
            "premium": premium,
            "core_parts": core_parts,
            "context_parts": ctx_parts,
            "market_parts": mkt_parts,
        },
        "penalties": pens,
        "confirmed": confirmed,
        "inferred": inferred,
        "missing": missing,
        "stale": stale,
        "completion_rate": nmb.completion_rate(),
        "wave2_completion_rate": nmb.wave2_completion_rate(),
        "wave3_completion_rate": nmb.wave3_completion_rate(),
        "xg_coverage": nmb.xg_coverage(),
        "event_coverage": nmb.event_coverage(),
        "odds_coverage": nmb.odds_coverage(),
        "calendar_coverage": nmb.calendar_coverage(),
        "lineup_coverage": nmb.lineup_coverage(),
        "injury_coverage": nmb.injury_coverage(),
        "premium_analysis": tier in {"T3", "T4"},
        "data_freshness_score": (nmb.meta.get("freshness") or {}).get(
            "freshness_score"
        ),
    }
