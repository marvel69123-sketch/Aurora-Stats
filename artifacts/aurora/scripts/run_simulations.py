#!/usr/bin/env python3
"""
AEP Phase 2 — Conversation Simulator runner.

Usage (from artifacts/aurora):
  python scripts/run_simulations.py
  python scripts/run_simulations.py --runs 100
  python scripts/run_simulations.py --runs 1000 --persona short_followup
  python scripts/run_simulations.py --runs 5000 --seed 7
  python scripts/run_simulations.py --runs 10000 --quiet

Does not modify engines. Discovers conversational failures at scale.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ALLOWED_RUNS = (100, 1000, 5000, 10000)

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

from tests.simulator.engine import run_conversation  # noqa: E402
from tests.simulator.metrics import build_report  # noqa: E402
from tests.simulator.personas import PERSONAS, generate_batch  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="AEP Conversation Simulator")
    parser.add_argument(
        "--runs",
        type=int,
        default=100,
        help="Number of simulated conversations (100|1000|5000|10000)",
    )
    parser.add_argument(
        "--allow-custom-runs",
        action="store_true",
        help="Allow --runs values outside the standard set",
    )
    parser.add_argument("--seed", type=int, default=42, help="Base RNG seed")
    parser.add_argument(
        "--persona",
        choices=sorted(PERSONAS.keys()),
        default=None,
        help="Restrict to one persona",
    )
    parser.add_argument(
        "--json-out",
        default=str(ROOT / "tests" / "simulator" / "results" / "last_simulation.json"),
        help="Output JSON path",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Less per-conversation logging",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=0,
        help="Print progress every N runs (0 = auto)",
    )
    args = parser.parse_args()

    if args.runs <= 0:
        print("--runs must be > 0")
        return 2
    if args.runs not in ALLOWED_RUNS and not args.allow_custom_runs:
        print(
            f"--runs must be one of {ALLOWED_RUNS} "
            f"(or pass --allow-custom-runs). got={args.runs}"
        )
        return 2

    progress_every = args.progress_every
    if progress_every <= 0:
        progress_every = max(1, min(100, args.runs // 10 or 1))

    scripts = generate_batch(args.runs, base_seed=args.seed, persona=args.persona)
    client = TestClient(app)

    print("---------------------------------")
    print("AEP Conversation Simulator v2")
    print(f"RUNS: {args.runs}  SEED: {args.seed}  PERSONA: {args.persona or 'all'}")
    print("---------------------------------")

    results = []
    t0 = time.perf_counter()
    for i, script in enumerate(scripts, start=1):
        result = run_conversation(client, script)
        results.append(result)
        if not args.quiet and (not result.success or args.runs <= 100):
            status = "OK" if result.success else "FAIL"
            extra = (
                f" reasons={result.failure_reasons}" if not result.success else ""
            )
            print(
                f"[{status}] {i}/{args.runs} {result.persona_id} "
                f"seed={result.seed} turns={len(result.turns)}{extra}"
            )
        elif i % progress_every == 0 or i == args.runs:
            ok = sum(1 for r in results if r.success)
            print(f"... progress {i}/{args.runs} success_so_far={ok}")

    report = build_report(
        results,
        requested_runs=args.runs,
        seed=args.seed,
    )
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["elapsed_sec"] = round(time.perf_counter() - t0, 2)

    out_path = Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    m = report["metrics"]
    print("---------------------------------")
    print(f"TOTAL RUNS: {report['total_runs']}")
    print(f"SUCCESS RATE: {report['success_rate']}%")
    print(f"LOOPS: {report['loops']}")
    print(f"CONTEXT LOSS: {report['context_loss']}")
    print(f"FALLBACKS: {report['fallbacks']}")
    print(f"INTENT FLIPS: {report['intent_flips']}")
    print(f"HALLUCINATION RISK: {report['hallucination_risk']}")
    print(
        f"CONTEXT PRESERVATION: {m.get('context_preservation')}%  "
        f"INTENT ACCURACY: {m.get('intent_accuracy')}%  "
        f"AVG TURNS BEFORE FAIL: {m.get('average_turns_before_failure')}"
    )
    if report["top_failures"]:
        print("TOP FAILURES:")
        for item in report["top_failures"][:8]:
            print(f"  {item['reason']}: {item['count']}")
    print("---------------------------------")
    print(f"JSON: {out_path}")

    # Exit 0 even with discoveries — simulator is exploratory.
    # Use --strict via env? User didn't ask for fail CI. Keep exit 0.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
