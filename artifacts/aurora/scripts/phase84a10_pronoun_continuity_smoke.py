#!/usr/bin/env python3
"""Phase 8.4-A.10 — Pronoun Continuity Layer smoke."""

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

    # 1) e dele? → fixture reused
    sid = "pr84a10_1"
    _post(client, "Argentina x Brasil", sid)
    d = _post(client, "e dele?", sid)
    e = d.get("entities") or {}
    entry = {
        "intent": d.get("intent"),
        "pronoun_detected": e.get("pronoun_detected"),
        "pronoun_resolved": e.get("pronoun_resolved"),
        "pronoun_fixture": e.get("pronoun_fixture"),
        "pronoun_before_fallback": e.get("pronoun_before_fallback"),
        "followup_context_found": e.get("followup_context_found"),
        "loop": LOOP in str(d.get("executive_summary") or "").lower(),
        "prefix": str(d.get("executive_summary") or "")[:200].replace("\n", " | "),
    }
    capture["cases"]["e_dele"] = entry
    if not entry["pronoun_resolved"] or not entry["pronoun_fixture"]:
        failures.append("e_dele_fixture_not_reused")
    if entry["loop"]:
        failures.append("e_dele_loop")
    print(f"[1] e dele? resolved={entry['pronoun_resolved']} fx={entry['pronoun_fixture']}")

    # 2) e o outro? → entity resolved
    sid = "pr84a10_2"
    _post(client, "Barcelona x Real Madrid", sid)
    d = _post(client, "e o outro?", sid)
    e = d.get("entities") or {}
    entry = {
        "pronoun_resolved": e.get("pronoun_resolved"),
        "pronoun_entity": e.get("pronoun_entity"),
        "entity_resolved": e.get("entity_resolved"),
        "prefix": str(d.get("executive_summary") or "")[:160].replace("\n", " | "),
    }
    capture["cases"]["e_o_outro"] = entry
    if not entry["entity_resolved"] or not entry["pronoun_entity"]:
        failures.append("e_o_outro_entity_missing")
    print(f"[2] e o outro? entity={entry['pronoun_entity']}")

    # 3) e esse time? → followup context
    sid = "pr84a10_3"
    _post(client, "Flamengo x Palmeiras", sid)
    d = _post(client, "e esse time?", sid)
    e = d.get("entities") or {}
    entry = {
        "followup_context_found": e.get("followup_context_found"),
        "pronoun_value": e.get("pronoun_value"),
        "pronoun_before_fallback": e.get("pronoun_before_fallback"),
        "prefix": str(d.get("executive_summary") or "")[:160].replace("\n", " | "),
    }
    capture["cases"]["e_esse_time"] = entry
    if not entry["followup_context_found"]:
        failures.append("e_esse_time_no_context")
    if not entry["pronoun_before_fallback"]:
        failures.append("e_esse_time_not_before_fallback")
    print(f"[3] e esse time? followup={entry['followup_context_found']}")

    # 4) INVALID → no invention
    sid = "pr84a10_4"
    _post(client, "Goku x Naruto", sid)
    d = _post(client, "e dele?", sid)
    e = d.get("entities") or {}
    summary = str(d.get("executive_summary") or "").lower()
    entry = {
        "fixture_quality": e.get("fixture_quality") or d.get("fixture_quality"),
        "entity_invalid": e.get("entity_invalid"),
        "pronoun_resolved": e.get("pronoun_resolved"),
        "invented": any(
            m in summary
            for m in ("probabilidade de", "stake recomendado", "melhor mercado", "xg=")
        ),
        "prefix": str(d.get("executive_summary") or "")[:200].replace("\n", " | "),
    }
    capture["cases"]["invalid_pronoun"] = entry
    if entry["fixture_quality"] != "INVALID" or entry["entity_invalid"] is not True:
        failures.append("invalid_pronoun_not_invalid")
    if entry["invented"]:
        failures.append("invalid_pronoun_invented")
    print(f"[4] invalid e dele? fq={entry['fixture_quality']} invented={entry['invented']}")

    out = ROOT / "observations" / "phase84a10" / "05_CAPTURE_AFTER_PATCH.json"
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
