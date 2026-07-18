#!/usr/bin/env python3
"""Phase 8.4-A.11 — Advanced Football Continuity smoke."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

LOOP = "entendi. posso te ajudar"


def _post(client, msg: str, sid: str) -> dict:
    return client.post(
        "/aurora/copilot",
        json={"message": msg, "session_id": sid, "debug": True},
    ).json()


def main() -> int:
    client = TestClient(app)
    failures: list[str] = []
    capture: dict = {"cases": {}}

    for i, msg, key in (
        (1, "xg?", "xg"),
        (2, "pressão?", "pressao"),
        (3, "kelly?", "kelly"),
        (4, "qual o edge?", "edge"),
    ):
        sid = f"adv84a11_{i}"
        _post(client, "Argentina x Brasil", sid)
        d = _post(client, msg, sid)
        e = d.get("entities") or {}
        summary = str(d.get("executive_summary") or "")
        entry = {
            "intent": d.get("intent"),
            "advanced_term_detected": e.get("advanced_term_detected"),
            "advanced_term": e.get("advanced_term"),
            "advanced_fixture_reused": e.get("advanced_fixture_reused"),
            "advanced_before_fallback": e.get("advanced_before_fallback"),
            "followup_context_found": e.get("followup_context_found"),
            "loop": LOOP in summary.lower(),
            "prefix": summary[:200].replace("\n", " | "),
        }
        capture["cases"][key] = entry
        if not entry["advanced_fixture_reused"]:
            failures.append(f"{key}_fixture_not_reused")
        if not entry["advanced_before_fallback"]:
            failures.append(f"{key}_not_before_fallback")
        if entry["loop"]:
            failures.append(f"{key}_loop")
        print(
            f"[{i}] {msg} term={entry['advanced_term']} "
            f"reused={entry['advanced_fixture_reused']} loop={entry['loop']}"
        )

    out = ROOT / "observations" / "phase84a11" / "05_CAPTURE_AFTER_PATCH.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(capture, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"capture → {out}")
    if failures:
        print("FAIL:", failures)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
