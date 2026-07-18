#!/usr/bin/env python3
"""
Aurora Evaluation Platform (AEP) v1.0 — Phase 1 runner.

Usage (from artifacts/aurora):
  python scripts/run_evals.py
  python scripts/run_evals.py --category capabilities
  python scripts/run_evals.py --id cap_001_o_que_voce_faz
  python scripts/run_evals.py --json-out observations/aep_v1/last_run.json

Does not modify engines. Exit code 0 when all cases PASS.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

from tests.evals.harness import load_cases, run_case, summarize  # noqa: E402


def _print_report(summary: dict, results: list) -> None:
    print("---------------------------------")
    print(f"TOTAL: {summary['total']}")
    print(f"PASS : {summary['pass']}")
    print(f"FAIL : {summary['fail']}")
    print(f"SUCCESS RATE: {summary['success_rate']}%")
    print(f"SCORE AVG: {summary['evaluation_score_avg']}")
    print("---------------------------------")
    if summary.get("by_category"):
        print("BY CATEGORY:")
        for cat, counts in sorted(summary["by_category"].items()):
            print(f"  {cat}: pass={counts['pass']} fail={counts['fail']}")
        print("---------------------------------")
    fails = [r for r in results if not r.evaluation_pass]
    if fails:
        print("FAILURES:")
        for r in fails:
            print(f"  [{r.category}] {r.id}: {r.evaluation_fail_reason}")
            print(
                f"    logs: evaluation_pass={r.evaluation_pass} "
                f"evaluation_score={r.evaluation_score} "
                f"loop_detected={r.loop_detected} "
                f"frustration_detected={r.frustration_detected} "
                f"context_preserved={r.context_preserved}"
            )
        print("---------------------------------")


def main() -> int:
    parser = argparse.ArgumentParser(description="Aurora Evaluation Platform runner")
    parser.add_argument("--category", help="Filter by category folder name")
    parser.add_argument("--id", help="Filter by case id")
    parser.add_argument(
        "--json-out",
        default=str(ROOT / "observations" / "aep_v1" / "last_run.json"),
        help="Write full JSON report path",
    )
    parser.add_argument(
        "--evals-root",
        default=str(ROOT / "tests" / "evals"),
        help="Root directory with category/cases.json files",
    )
    args = parser.parse_args()

    evals_root = Path(args.evals_root)
    cases = load_cases(evals_root)
    if args.category:
        cases = [c for c in cases if str(c.get("category")) == args.category]
    if args.id:
        cases = [c for c in cases if str(c.get("id")) == args.id]

    if not cases:
        print("No eval cases found.")
        return 2

    client = TestClient(app)
    results = []
    for case in cases:
        result = run_case(client, case)
        results.append(result)
        status = "PASS" if result.evaluation_pass else "FAIL"
        print(
            f"[{status}] {result.category}/{result.id} "
            f"score={result.evaluation_score} "
            f"ms={result.duration_ms}"
            + (f" reason={result.evaluation_fail_reason}" if not result.evaluation_pass else "")
        )

    summary = summarize(results)
    _print_report(summary, results)

    out_path = Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "platform": "AEP",
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "results": [r.to_dict() for r in results],
        "log_fields": [
            "evaluation_score",
            "evaluation_pass",
            "evaluation_fail_reason",
            "loop_detected",
            "frustration_detected",
            "context_preserved",
        ],
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"JSON report: {out_path}")

    return 0 if summary["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
