"""
Phase 7.9-A — P0-1 defensive soft sections.

Fills missing confidence / risk / bankroll_recommendation so CopilotResponse
never raises KeyError. Does not change engines, routing, NRF, or UX text.
"""

from __future__ import annotations

from typing import Any

_SOFT_CONFIDENCE: dict[str, Any] = {
    "score": 0.0,
    "label": "insufficient",
    "explanation": "Seções suaves preenchidas defensivamente (payload incompleto).",
    "data_sources": ["SoftSections"],
}

_SOFT_RISK: dict[str, Any] = {
    "level": "Unknown",
    "flags": [],
    "invalidation_conditions": [],
}

_SOFT_BANKROLL: dict[str, Any] = {
    "recommended_stake_pct": 0.0,
    "method": "quarter-Kelly",
    "examples": {},
    "no_bet": True,
    "reasoning": "",
}


def ensure_soft_sections(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    Ensure payload has confidence / risk / bankroll_recommendation dicts.
    Idempotent. Fail-open: returns payload unchanged on unexpected types.
    """
    if not isinstance(payload, dict):
        return payload
    out = payload
    if not isinstance(out.get("confidence"), dict):
        out["confidence"] = dict(_SOFT_CONFIDENCE)
    if not isinstance(out.get("risk"), dict):
        out["risk"] = dict(_SOFT_RISK)
    if not isinstance(out.get("bankroll_recommendation"), dict):
        out["bankroll_recommendation"] = dict(_SOFT_BANKROLL)
    return out
