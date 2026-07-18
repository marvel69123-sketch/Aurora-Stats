#!/usr/bin/env python3
"""Manual 9-case battery for phase 8.4-A.7."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402


def main() -> int:
    client = TestClient(app)
    sid = "manual84a7"
    cases = [
        (1, "analise argentina x espanha"),
        (2, "argentina x espanha"),
        (3, "o que você achou do jogo do fluminense ontem?"),
        (4, "mercados?"),
        (5, "placar?"),
        (6, "quando é o próximo jogo do fluminense?"),
        (7, "oi"),
        (8, "quem é você?"),
        (9, "goku x naruto"),
    ]
    out = []
    for n, msg in cases:
        r = client.post(
            "/aurora/copilot",
            json={"message": msg, "session_id": sid, "debug": True},
        )
        d = r.json()
        e = d.get("entities") or {}
        summary = str(d.get("executive_summary") or "")
        entry = {
            "n": n,
            "message": msg,
            "http": r.status_code,
            "intent": d.get("intent"),
            "fixture_quality": e.get("fixture_quality") or d.get("fixture_quality"),
            "preliminary_analysis": e.get("preliminary_analysis"),
            "entity_invalid": e.get("entity_invalid"),
            "response_type": e.get("response_type"),
            "assistant_kind": e.get("assistant_kind"),
            "response_owner": e.get("response_owner"),
            "overwrite_by": e.get("overwrite_by"),
            "conf_label": (d.get("confidence") or {}).get("label"),
            "conf_score": (d.get("confidence") or {}).get("score"),
            "markets": len(d.get("best_markets") or []),
            "refusal": "manteve a conversa com confian" in summary.lower(),
            "summary_prefix": summary[:320].replace("\n", " | "),
        }
        out.append(entry)

    path = ROOT / "observations" / "phase84a7" / "09_MANUAL_BATTERY.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"session_id": sid, "cases": out}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # ASCII-safe console summary
    for entry in out:
        prefix = entry["summary_prefix"].encode("ascii", "replace").decode("ascii")
        print(
            "[%d] intent=%s prelim=%s invalid=%s type=%s kind=%s refusal=%s"
            % (
                entry["n"],
                entry["intent"],
                entry["preliminary_analysis"],
                entry["entity_invalid"],
                entry["response_type"],
                entry["assistant_kind"],
                entry["refusal"],
            )
        )
        print("    ", prefix[:160])
    print("saved", str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
