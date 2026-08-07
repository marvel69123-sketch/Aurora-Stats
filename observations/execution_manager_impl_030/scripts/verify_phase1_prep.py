#!/usr/bin/env python3
"""Phase 1 Prep reproducibility — inventory scripts (no product mutation)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OBS = Path(__file__).resolve().parents[1]
BASELINES = OBS / "baselines"
SOT = ROOT / "artifacts" / "aurora"

EM_FLAGS = [
    "ENABLE_EXECUTION_MANAGER_SHADOW",
    "ENABLE_EXECUTION_MANAGER",
    "ENABLE_EM_PIPELINE_BANKROLL",
    "ENABLE_EM_PIPELINE_LEARNING",
    "ENABLE_EM_PIPELINE_KNOWLEDGE",
    "ENABLE_EM_PIPELINE_LIVE",
    "ENABLE_EM_PIPELINE_ANALYZE",
    "ENABLE_EM_PIPELINE_LIVE_TEAM",
    *(f"ENABLE_EM_PGR_0{i}" for i in range(1, 7)),
]

REQUIRED_BASELINES = [
    "appendix_a_keys.json",
    "hard_abort_blocked_payload_shape.json",
    "analyze_success_payload_keys.json",
    "live_payload_keys.json",
    "thin_payload_keys.json",
]


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> None:
    for name in REQUIRED_BASELINES:
        path = BASELINES / name
        if not path.is_file():
            _fail(f"missing baseline {path}")
        json.loads(path.read_text(encoding="utf-8"))

    hard = json.loads(
        (BASELINES / "hard_abort_blocked_payload_shape.json").read_text(encoding="utf-8")
    )
    inv = hard.get("hard_abort_invariants") or {}
    if inv.get("fixture_quality") != "INVALID":
        _fail("HARD-ABORT invariant fixture_quality != INVALID")
    if inv.get("entity_invalid") is not True:
        _fail("HARD-ABORT invariant entity_invalid != true")

    fq = json.loads(
        (BASELINES / "analyze_success_payload_keys.json").read_text(encoding="utf-8")
    ).get("fixture_quality_closed_set_plan_3_2")
    expected = {"VALID", "PARTIAL", "INVALID", "VALID_LOCATED"}
    if set(fq or []) != expected:
        _fail(f"fixture_quality closed set mismatch: {fq}")

    router = SOT / "src" / "routers" / "copilot_unified_router.py"
    integrity = SOT / "src" / "core" / "fixture_integrity.py"
    if not router.is_file() or not integrity.is_file():
        _fail("SoT router or fixture_integrity missing")
    text = router.read_text(encoding="utf-8", errors="replace")
    for needle in (
        "async def _run_analyze",
        "async def _run_live",
        "def _run_bankroll",
        "def _run_learning",
        "def _run_knowledge",
        "blocked_integrity_payload",
    ):
        if needle not in text and needle not in integrity.read_text(
            encoding="utf-8", errors="replace"
        ):
            # blocked helper lives in integrity; others in router
            if needle == "blocked_integrity_payload":
                if needle not in integrity.read_text(encoding="utf-8", errors="replace"):
                    _fail(f"missing {needle}")
            else:
                _fail(f"missing {needle} in router")

    for flag in EM_FLAGS:
        raw = (os.environ.get(flag) or "0").strip().lower()
        if raw not in {"0", "false", "off", ""}:
            _fail(f"flag {flag} must be OFF for Prep; got {raw!r}")
    pct = (os.environ.get("EM_ACTIVATION_PCT") or "0").strip()
    if pct not in {"0", "0.0", ""}:
        _fail(f"EM_ACTIVATION_PCT must be 0; got {pct!r}")

    # Phase 2 Infrastructure may have landed execution_manager/; Prep baselines
    # remain valid. Package presence is no longer a Prep failure.
    em_pkg = SOT / "src" / "execution_manager"
    if em_pkg.exists() and not (em_pkg / "__init__.py").is_file():
        _fail("execution_manager present but missing __init__.py")

    print("PASS: Phase 1 Prep baselines + flags OFF + SoT inventory reproducible")


if __name__ == "__main__":
    main()
