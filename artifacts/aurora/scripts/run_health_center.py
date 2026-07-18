#!/usr/bin/env python3
"""
AEP Phase 5 — Aurora Health Center.

Consolidates AEP + Simulator + Frustration + LLM Judge into
observations/health/health_report.json

Usage (from artifacts/aurora):
  python scripts/run_health_center.py
  python scripts/run_health_center.py --refresh
  python scripts/run_health_center.py --refresh --quick

Observability only — does not modify engines.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.health.consolidate import build_health_report, persist_report  # noqa: E402


def _run(cmd: list[str]) -> int:
    print(">>", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(ROOT))
    return int(proc.returncode or 0)


def refresh_sources(*, quick: bool) -> None:
    py = sys.executable
    # Keep refresh bounded so Health Center stays usable
    aep = [py, "scripts/run_evals.py"]
    sim_n = "20" if quick else "100"
    frust_n = "20" if quick else "100"
    judge_n = "12" if quick else "40"
    sim = [py, "scripts/run_simulations.py", "--runs", sim_n, "--quiet", "--allow-custom-runs"]
    frust = [py, "scripts/run_frustration.py", "--sessions", frust_n, "--quiet"]
    judge = [py, "scripts/run_llm_judge.py", "--conversations", judge_n, "--quiet"]

    codes = []
    for cmd in (aep, sim, frust, judge):
        codes.append(_run(cmd))
    if any(c not in (0,) for c in codes):
        print(
            "[WARN] One or more refresh steps returned non-zero; "
            "Health Center will consolidate whatever artifacts exist."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Aurora Health Center")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-run AEP/Simulator/Frustration/Judge before consolidating",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="With --refresh, use smaller sample sizes",
    )
    parser.add_argument(
        "--json-out",
        default=str(ROOT / "observations" / "health" / "health_report.json"),
        help="Override output path (default observations/health/health_report.json)",
    )
    args = parser.parse_args()

    if args.refresh:
        refresh_sources(quick=args.quick)

    report = build_health_report(root=ROOT)
    out = persist_report(report, ROOT)
    if Path(args.json_out).resolve() != out.resolve():
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(out.read_text(encoding="utf-8"), encoding="utf-8")

    print("---------------------------------")
    print("AURORA HEALTH CENTER")
    print(f"HEALTH SCORE: {report['health_score']}")
    print(f"STATUS: {report['status']}")
    print(f"LOOP RATE: {report['loop_rate']}%")
    print(f"FRUSTRATION RATE: {report['frustration_rate']}%")
    print(f"LLM OVERALL: {report['llm_overall']}")
    print(f"TREND: {report['trend']}")
    print("---------------------------------")
    m = report["metrics"]
    print(f"Conversation Success: {m['conversation_success']}%")
    print(f"Context Preservation: {m['context_preservation']}%")
    print(f"Recovery Rate: {m['recovery_rate']}%")
    print(f"Naturalness: {m['naturalness']}  Credibility: {m['credibility']}")
    print(f"Sources: {report['sources']}")
    print("---------------------------------")
    print(f"JSON: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
