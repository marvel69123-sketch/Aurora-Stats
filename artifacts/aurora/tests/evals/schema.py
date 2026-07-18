"""AEP case schema helpers (JSON-driven, no engine imports)."""

from __future__ import annotations

from typing import Any


REQUIRED_CASE_KEYS = ("id", "category", "steps")


def validate_case(case: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    if not isinstance(case, dict):
        return ["case_not_object"]
    for key in REQUIRED_CASE_KEYS:
        if key not in case:
            errs.append(f"missing_{key}")
    steps = case.get("steps")
    if not isinstance(steps, list) or not steps:
        errs.append("steps_empty")
    else:
        for i, step in enumerate(steps):
            if not isinstance(step, dict) or not str(step.get("message") or "").strip():
                errs.append(f"step_{i}_invalid")
    return errs
