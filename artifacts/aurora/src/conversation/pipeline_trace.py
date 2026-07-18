"""
Phase 7.7/7.8 — temporary pipeline observability (fail-open).

Tags:
  [INTENT] [ENTITIES] [PLANNER] [ENGINE] [FALLBACK] [RECOVERY] [FINAL_RESPONSE]
  [OWNER] [PAYLOAD_BEFORE] [PAYLOAD_AFTER] [NRF_INPUT] [NRF_OUTPUT]

Env: AURORA_PIPELINE_TRACE=1 (default) / 0 to disable.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("aurora.pipeline_trace")

_ENABLED = os.environ.get("AURORA_PIPELINE_TRACE", "1").strip() not in {
    "0",
    "false",
    "False",
    "off",
}

# In-memory ring for Phase 7.8 harness (does not change behavior)
_CAPTURE: list[str] = []
_CAPTURE_MAX = 2000


def clear_capture() -> None:
    _CAPTURE.clear()


def get_capture() -> list[str]:
    return list(_CAPTURE)


def _safe(val: Any, limit: int = 160) -> str:
    try:
        s = str(val)
    except Exception:
        return "?"
    s = s.replace("\n", " ").strip()
    return s if len(s) <= limit else s[: limit - 1] + "…"


def trace(tag: str, **fields: Any) -> None:
    """Emit one structured audit line. Never raises."""
    if not _ENABLED:
        return
    try:
        parts = [f"{k}={_safe(v)}" for k, v in fields.items() if v is not None]
        line = f"[{tag}] " + " ".join(parts)
        logger.warning("%s", line)
        _CAPTURE.append(line)
        if len(_CAPTURE) > _CAPTURE_MAX:
            del _CAPTURE[: len(_CAPTURE) - _CAPTURE_MAX]
    except Exception:
        pass


def snapshot_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "has_payload": False,
            "intent": None,
            "owner": None,
            "fallback": None,
            "has_confidence": False,
            "keys": [],
        }
    ents = payload.get("entities") if isinstance(payload.get("entities"), dict) else {}
    return {
        "has_payload": True,
        "intent": payload.get("intent"),
        "owner": ents.get("turn_owner"),
        "locked": bool(ents.get("rewrite_locked")),
        "hce_kind": ents.get("hce_kind"),
        "assistant_kind": ents.get("assistant_kind"),
        "fallback": ents.get("fallback") or ents.get("intelligence_fallback"),
        "has_confidence": isinstance(payload.get("confidence"), dict),
        "has_risk": isinstance(payload.get("risk"), dict),
        "has_bankroll": isinstance(payload.get("bankroll_recommendation"), dict),
        "keys": sorted(str(k) for k in payload.keys()),
        "summary_prefix": _safe(payload.get("executive_summary"), 60),
    }


def trace_owner(stage: str, payload: dict[str, Any] | None, **extra: Any) -> None:
    snap = snapshot_payload(payload)
    trace(
        "OWNER",
        stage=stage,
        owner=snap.get("owner") or "none",
        locked=snap.get("locked"),
        intent=snap.get("intent"),
        **extra,
    )


def trace_payload(tag: str, stage: str, payload: dict[str, Any] | None, **extra: Any) -> None:
    snap = snapshot_payload(payload)
    trace(
        tag,
        stage=stage,
        intent=snap.get("intent"),
        owner=snap.get("owner"),
        locked=snap.get("locked"),
        has_confidence=snap.get("has_confidence"),
        has_risk=snap.get("has_risk"),
        has_bankroll=snap.get("has_bankroll"),
        summary_prefix=snap.get("summary_prefix"),
        keys=",".join(snap.get("keys") or []),
        **extra,
    )
