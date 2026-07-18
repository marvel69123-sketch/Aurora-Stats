#!/usr/bin/env python3
"""
AEP Phase 3 — Frustration Analytics runner.

Usage (from artifacts/aurora):
  python scripts/run_frustration.py
  python scripts/run_frustration.py --sessions 100
  python scripts/run_frustration.py --sessions 1000 --quiet

Observability only — does not modify engines.
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

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

from tests.frustration.engine import run_frustration_session  # noqa: E402
from tests.frustration.metrics import build_report  # noqa: E402
from tests.frustration.scenarios import generate_frustration_batch  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="AEP Frustration Analytics")
    parser.add_argument(
        "--sessions",
        type=int,
        default=100,
        help="Number of frustration-focused sessions",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--json-out",
        default=str(
            ROOT / "tests" / "frustration" / "results" / "last_frustration.json"
        ),
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if args.sessions <= 0:
        print("--sessions must be > 0")
        return 2

    scripts = generate_frustration_batch(args.sessions, base_seed=args.seed)
    client = TestClient(app)

    print("---------------------------------")
    print("AEP Frustration Analytics v3")
    print(f"SESSIONS: {args.sessions}  SEED: {args.seed}")
    print("---------------------------------")

    results = []
    t0 = time.perf_counter()
    progress_every = max(1, min(25, args.sessions // 10 or 1))
    for i, script in enumerate(scripts, start=1):
        result = run_frustration_session(client, script)
        results.append(result)
        if not args.quiet and (result.had_frustration or args.sessions <= 50):
            rec = result.recovered
            print(
                f"[{i}/{args.sessions}] {result.script_id} "
                f"frust={result.had_frustration} recovered={rec} "
                f"types={result.frustration_types}"
            )
        elif i % progress_every == 0 or i == args.sessions:
            fr = sum(1 for r in results if r.had_frustration)
            print(f"... progress {i}/{args.sessions} frustrated_so_far={fr}")

    report = build_report(
        results, requested_sessions=args.sessions, seed=args.seed
    )
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["elapsed_sec"] = round(time.perf_counter() - t0, 2)

    out_path = Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("---------------------------------")
    print(f"TOTAL SESSIONS: {report['total_sessions']}")
    print(f"FRUSTRATION RATE: {report['frustration_rate']}%")
    print(f"RECOVERY RATE: {report['recovery_rate']}%")
    print(f"REPEATED FRUSTRATION RATE: {report['repeated_frustration_rate']}%")
    print(f"TURNS UNTIL FRUSTRATION AVG: {report['turns_until_frustration_avg']}")
    print(f"TOP CAUSES: {report['top_causes']}")
    print("---------------------------------")
    print(f"JSON: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
