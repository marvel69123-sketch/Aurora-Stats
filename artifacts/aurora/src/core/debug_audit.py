"""
Aurora — DEBUG audit block for fixture / market / confidence provenance.

When debug mode is on, the copilot payload includes a `debug` object with
explicit fields. Missing values are marked as the string DATA_MISSING
(never silently filled with generic baselines).
"""

from __future__ import annotations

import os
from typing import Any

DATA_MISSING = "DATA_MISSING"

_AUDIT_KEYS: tuple[str, ...] = (
    "fixture_found",
    "fixture_id",
    "data_source",
    "markets_source",
    "market_reasoning",
    "fallback_used",
    "confidence_source",
    "corner_average",
    "goal_average",
    "xg_home",
    "xg_away",
    "form_score",
    "fixture_resolver",
    "entity_match_score",
    "market_generation_enabled",
    "fixture_quality",
)


def debug_mode_enabled(
    request_debug: bool | None = None,
    *,
    message: str | None = None,
) -> bool:
    """True when request flag, env, or #debug token enables audit mode."""
    if request_debug is True:
        return True
    env = (os.environ.get("AURORA_DEBUG") or "").strip().lower()
    if env in ("1", "true", "yes", "on"):
        return True
    msg = (message or "").lower()
    if "#debug" in msg or "modo debug" in msg:
        return True
    return False


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    if isinstance(value, (list, dict)) and len(value) == 0:
        return False
    return True


def mark_missing(value: Any) -> Any:
    """Return value if present; otherwise DATA_MISSING."""
    return value if _present(value) else DATA_MISSING


def build_debug_audit(raw: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Normalize an audit dict: every required key is present;
    absent/empty values become DATA_MISSING.
    """
    src = dict(raw or {})
    out: dict[str, Any] = {}
    for key in _AUDIT_KEYS:
        if key in ("fixture_found", "fallback_used", "market_generation_enabled"):
            val = src.get(key)
            if isinstance(val, bool):
                out[key] = val
            elif val is None:
                out[key] = DATA_MISSING
            else:
                out[key] = bool(val)
            continue
        out[key] = mark_missing(src.get(key))
    return out


def audit_from_analyze(
    *,
    fixture_located: bool,
    fixture_id: Any,
    is_partial: bool,
    best_markets: list[dict] | None,
    data_sources: list[str] | None,
    meth: Any = None,
    ictx: Any = None,
    standings_home: dict | None = None,
    standings_away: dict | None = None,
    used_baseline_markets: bool = False,
) -> dict[str, Any]:
    """Build raw audit fields from an analyze-pipeline snapshot."""
    from src.core.methodology_engine import _form_score

    fid = None
    try:
        fid_int = int(fixture_id or 0)
        if fid_int > 0:
            fid = fid_int
    except (TypeError, ValueError):
        fid = None

    markets = list(best_markets or [])
    reasoning_parts = [
        str(m.get("rationale") or "").strip()
        for m in markets[:3]
        if str(m.get("rationale") or "").strip()
    ]
    sources = [s for s in (data_sources or []) if s]

    has_xg = bool(getattr(meth, "has_xg", False)) if meth is not None else False
    has_stats = bool(getattr(meth, "has_stats", False)) if meth is not None else False
    has_standings = (
        bool(getattr(meth, "has_standings", False)) if meth is not None else False
    )
    is_live = bool(getattr(meth, "is_live", False)) if meth is not None else False
    minute = int(getattr(meth, "minute", 0) or 0) if meth is not None else 0
    total_corners = (
        int(getattr(meth, "total_corners", 0) or 0) if meth is not None else 0
    )

    corner_average = None
    if has_stats and is_live and minute > 0:
        corner_average = round(total_corners / minute * 90.0, 2)
    elif has_stats and total_corners > 0:
        corner_average = float(total_corners)

    goal_average = None
    if has_standings and meth is not None:
        goal_average = round(
            (float(meth.h_gpg) + float(meth.a_gpg)) / 2.0,
            3,
        )

    xg_home = round(float(meth.h_xg_val), 3) if (has_xg and meth is not None) else None
    xg_away = round(float(meth.a_xg_val), 3) if (has_xg and meth is not None) else None

    h_form = (standings_home or {}).get("form") if standings_home else None
    a_form = (standings_away or {}).get("form") if standings_away else None
    form_score = None
    if h_form or a_form:
        form_score = round((_form_score(h_form) + _form_score(a_form)) / 2.0, 3)

    missing_signals = list(getattr(ictx, "missing_signals", None) or [])
    completeness = float(getattr(ictx, "data_completeness", 1.0) or 1.0)
    fallback = bool(
        is_partial
        or not fixture_located
        or used_baseline_markets
        or (not has_xg)
        or (not has_standings)
        or completeness < 0.85
        or bool(missing_signals)
    )

    return {
        "fixture_found": bool(fixture_located),
        "fixture_id": fid,
        "data_source": "API-Football" if fixture_located else None,
        "markets_source": "DecisionCenter" if markets else None,
        "market_reasoning": " | ".join(reasoning_parts) if reasoning_parts else None,
        "fallback_used": fallback,
        "confidence_source": (
            ", ".join(sources)
            if sources
            else ("confidence_engine" if fixture_located else None)
        ),
        "corner_average": corner_average,
        "goal_average": goal_average,
        "xg_home": xg_home,
        "xg_away": xg_away,
        "form_score": form_score,
    }


def audit_blocked(
    *,
    fixture_status: str | None = None,
    home: str | None = None,
    away: str | None = None,
) -> dict[str, Any]:
    """Audit block for NOT_FOUND / FICTIONAL / invalid fixtures."""
    _ = (fixture_status, home, away)  # reserved for future labels
    return {
        "fixture_found": False,
        "fixture_id": None,
        "data_source": None,
        "markets_source": None,
        "market_reasoning": None,
        "fallback_used": False,
        "confidence_source": "Fixture Integrity Guard",
        "corner_average": None,
        "goal_average": None,
        "xg_home": None,
        "xg_away": None,
        "form_score": None,
        "fixture_resolver": "integrity_blocked",
        "entity_match_score": None,
        "market_generation_enabled": False,
        "fixture_quality": "INVALID",
    }


def attach_debug_to_payload(
    payload: dict[str, Any],
    *,
    enabled: bool,
) -> dict[str, Any]:
    """
    If enabled, set payload['debug'] from _audit raw or blocked defaults.
    Always strip internal _audit / _partial keys from the public-facing dict
    when building the final response (caller may also ignore them).
    """
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    raw = out.pop("_audit", None)
    if not enabled:
        out.pop("debug", None)
        return out

    status = out.get("fixture_status") or (out.get("entities") or {}).get(
        "fixture_status"
    )
    markets_blocked = bool((out.get("entities") or {}).get("markets_blocked"))
    if raw is None and (
        markets_blocked or status in ("NOT_FOUND", "FICTIONAL")
    ):
        raw = audit_blocked(
            fixture_status=str(status) if status else None,
            home=(out.get("entities") or {}).get("home"),
            away=(out.get("entities") or {}).get("away"),
        )
    elif isinstance(raw, dict) and (
        markets_blocked or status in ("NOT_FOUND", "FICTIONAL", "PARTIAL")
    ):
        # Integrity blocked markets — never claim DecisionCenter markets
        raw = dict(raw)
        if status in ("NOT_FOUND", "FICTIONAL") or markets_blocked:
            raw["fixture_found"] = False if status != "PARTIAL" else raw.get(
                "fixture_found", False
            )
            raw["markets_source"] = None
            raw["market_reasoning"] = None
            if status in ("NOT_FOUND", "FICTIONAL"):
                raw["data_source"] = None
                raw["fixture_id"] = None
                raw["corner_average"] = None
                raw["goal_average"] = None
                raw["xg_home"] = None
                raw["xg_away"] = None
                raw["form_score"] = None
                raw["confidence_source"] = "Fixture Integrity Guard"
                raw["fallback_used"] = False

    out["debug"] = build_debug_audit(raw if isinstance(raw, dict) else {})
    return out
