#!/usr/bin/env python3
"""
AEP Phase 4 — LLM Judge runner.

Usage (from artifacts/aurora):
  python scripts/run_llm_judge.py
  python scripts/run_llm_judge.py --conversations 50
  python scripts/run_llm_judge.py --conversations 100 --persona advanced_football_v2

Default judge is the deterministic rubric (no API).
Optional LLM soft blend: AURORA_JUDGE_LLM=1 + OPENAI_API_KEY.

Evaluation only — does not modify engines.
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

from tests.judge.engine import generate_judge_batch, run_judged_conversation  # noqa: E402
from tests.judge.metrics import build_report  # noqa: E402
from tests.judge.optional_llm import llm_judge_enabled  # noqa: E402
from tests.simulator.personas import PERSONAS  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="AEP LLM Judge")
    parser.add_argument("--conversations", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--persona",
        choices=sorted(PERSONAS.keys()),
        default=None,
    )
    parser.add_argument(
        "--json-out",
        default=str(ROOT / "tests" / "judge" / "results" / "last_judge.json"),
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if args.conversations <= 0:
        print("--conversations must be > 0")
        return 2

    scripts = generate_judge_batch(
        args.conversations, base_seed=args.seed, persona=args.persona
    )
    client = TestClient(app)

    print("---------------------------------")
    print("AEP LLM Judge v4")
    print(
        f"CONVERSATIONS: {args.conversations}  SEED: {args.seed}  "
        f"PERSONA: {args.persona or 'all'}  "
        f"LLM: {'on' if llm_judge_enabled() else 'off (rubric)'}"
    )
    print("---------------------------------")

    results = []
    t0 = time.perf_counter()
    progress_every = max(1, min(20, args.conversations // 10 or 1))
    for i, script in enumerate(scripts, start=1):
        judged = run_judged_conversation(client, script)
        results.append(judged)
        if not args.quiet and args.conversations <= 60:
            s = judged.scores
            print(
                f"[{i}/{args.conversations}] {judged.persona_id} "
                f"overall={s.get('overall')} band={s.get('band')} "
                f"cont={s.get('continuity')} util={s.get('utility')}"
            )
        elif i % progress_every == 0 or i == args.conversations:
            avg = sum(float(r.scores.get("overall") or 0) for r in results) / len(
                results
            )
            print(f"... progress {i}/{args.conversations} overall_so_far={avg:.1f}")

    report = build_report(
        results, requested=args.conversations, seed=args.seed
    )
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["elapsed_sec"] = round(time.perf_counter() - t0, 2)
    report["llm_soft_enabled"] = llm_judge_enabled()

    out_path = Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("---------------------------------")
    print(f"OVERALL: {report['overall']}")
    print(f"UNDERSTANDING: {report['understanding']}")
    print(f"CONTINUITY: {report['continuity']}")
    print(f"UTILITY: {report['utility']}")
    print(f"CREDIBILITY: {report['credibility']}")
    print(f"NATURALNESS: {report['naturalness']}")
    print(f"CLARITY: {report['clarity']}")
    print(f"BAND: {report['band']}")
    print("---------------------------------")
    print(f"JSON: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
