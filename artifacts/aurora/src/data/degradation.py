"""
P2b Wave 1 — Graceful degradation T4 → T0.

Maps DRS tier to honesty / product posture. Never invents data.
"""

from __future__ import annotations

from typing import Any


def tier_from_drs(drs: int | float | None) -> str:
    try:
        v = int(drs or 0)
    except (TypeError, ValueError):
        v = 0
    if v < 20:
        return "T0"
    if v < 40:
        return "T1"
    if v < 60:
        return "T2"
    if v < 80:
        return "T3"
    return "T4"


# Tier → posture (compatible with P2.5 honesty modes)
_TIER_PLAN: dict[str, dict[str, Any]] = {
    "T4": {
        "posture": "premium_analyst",
        "honesty_modes": [],
        "allow_markets": True,
        "allow_live_claims": True,
        "no_bet_hard": False,
        "clarify_required": False,
        "max_claim_strength": "high",
    },
    "T3": {
        "posture": "standard_analyst",
        "honesty_modes": [],
        "allow_markets": True,
        "allow_live_claims": True,
        "no_bet_hard": False,
        "clarify_required": False,
        "max_claim_strength": "medium_high",
    },
    "T2": {
        "posture": "limited_analyst",
        "honesty_modes": ["DATA_PARTIAL"],
        "allow_markets": True,
        "allow_live_claims": False,
        "withhold_fragile_markets": True,
        "no_bet_hard": False,
        "clarify_required": False,
        "max_claim_strength": "medium",
    },
    "T1": {
        "posture": "data_partial_no_bet",
        "honesty_modes": ["DATA_PARTIAL", "PARTIAL_ANALYSIS", "NO_BET_HARD"],
        "allow_markets": False,
        "allow_live_claims": False,
        "no_bet_hard": True,
        "clarify_required": False,
        "max_claim_strength": "low",
    },
    "T0": {
        "posture": "clarify_or_refuse",
        "honesty_modes": ["DATA_PARTIAL", "NO_BET_HARD"],
        "allow_markets": False,
        "allow_live_claims": False,
        "no_bet_hard": True,
        "clarify_required": True,
        "max_claim_strength": "none",
        "never_invent": True,
    },
}


def apply_degradation_plan(
    drs_result: dict[str, Any] | None,
    *,
    rate_limited: bool = False,
    user_wants_live: bool = False,
) -> dict[str, Any]:
    """Return degradation plan for a DRS result. Never fabricates signals."""
    if not isinstance(drs_result, dict):
        tier = "T0"
        drs = 0
    else:
        tier = str(drs_result.get("tier") or tier_from_drs(drs_result.get("drs")))
        try:
            drs = int(drs_result.get("drs") or 0)
        except (TypeError, ValueError):
            drs = 0

    plan = dict(_TIER_PLAN.get(tier, _TIER_PLAN["T0"]))
    modes = list(plan.get("honesty_modes") or [])
    if rate_limited and "RATE_LIMITED" not in modes:
        modes.append("RATE_LIMITED")
    if user_wants_live and tier in {"T0", "T1", "T2"} and "LIVE_UNCONFIRMED" not in modes:
        modes.append("LIVE_UNCONFIRMED")

    missing = list((drs_result or {}).get("missing") or [])
    confirmed = list((drs_result or {}).get("confirmed") or [])

    return {
        "tier": tier,
        "drs": drs,
        "posture": plan.get("posture"),
        "honesty_modes": modes,
        "allow_markets": bool(plan.get("allow_markets")),
        "allow_live_claims": bool(plan.get("allow_live_claims")),
        "withhold_fragile_markets": bool(plan.get("withhold_fragile_markets")),
        "no_bet_hard": bool(plan.get("no_bet_hard")),
        "clarify_required": bool(plan.get("clarify_required")),
        "max_claim_strength": plan.get("max_claim_strength"),
        "never_invent": True,
        "confirmed_signals": confirmed,
        "missing_signals": missing,
        "empty_partial_risk": tier in {"T0", "T1"} and not confirmed,
    }
