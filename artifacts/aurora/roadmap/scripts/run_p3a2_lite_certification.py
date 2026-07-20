"""
P3-A.2 — Lite live-density certification (throttled + budgeted).

Ops-only: adaptive throttle, backoff, request budget, smaller corpus.
Does NOT change engines / Gateway internals / NMB / DRS.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_SCRIPT = Path(__file__).resolve().parent / "run_p3a1_live_certification.py"
_spec = importlib.util.spec_from_file_location("run_p3a1_live_certification", _SCRIPT)
assert _spec and _spec.loader
_p3a1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_p3a1)


def main() -> None:
    summary = asyncio.run(_p3a1.run_certification(min_n=24, mode="lite"))
    _p3a1._write_reports(summary, mode="lite")
    if summary.get("status") == "BLOCKED_NO_API_KEY":
        sys.exit(2)
    if (summary.get("certification") or {}).get("verdict") != "GO":
        sys.exit(1)


if __name__ == "__main__":
    main()
