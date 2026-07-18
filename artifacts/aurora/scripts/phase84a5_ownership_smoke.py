#!/usr/bin/env python3
"""Phase 8.4-A.5 — ownership patch smoke + light regressions."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

BAD = ("leitura rápida", "leitura rapida", "panorama", "Agenda à frente", "Fase atual")


def ask(client: TestClient, msg: str) -> dict:
    r = client.post("/aurora/copilot", json={"message": msg, "debug": True})
    data = r.json()
    ents = data.get("entities") or {}
    summary = str(data.get("executive_summary") or "")
    return {
        "http": r.status_code,
        "msg": msg,
        "intent": data.get("intent"),
        "summary": summary,
        "response_type": ents.get("response_type"),
        "overwrite_by": ents.get("overwrite_by"),
        "fallback_kind": ents.get("fallback_kind"),
        "match_opinion_renderer": ents.get("match_opinion_renderer"),
        "final_response": ents.get("final_response"),
        "response_owner": ents.get("response_owner"),
        "turn_owner": ents.get("turn_owner"),
        "rewrite_locked": ents.get("rewrite_locked"),
        "natural_kind": ents.get("natural_kind"),
        "hce_kind": ents.get("hce_kind"),
        "assistant_kind": ents.get("assistant_kind"),
        "bad_tokens": [b for b in BAD if b.lower() in summary.lower()],
    }


def main() -> int:
    client = TestClient(app)
    failures: list[str] = []
    results: dict[str, dict] = {}

    # Primary
    r = ask(client, "o que você achou do jogo do fluminense ontem?")
    results["opinion"] = r
    ok = (
        r["response_type"] == "match_opinion"
        and r["match_opinion_renderer"] is True
        and r["overwrite_by"] is None
        and not r["bad_tokens"]
        and len(r["summary"]) > 40
        and "achou" in r["summary"].lower()
        or "opini" in r["summary"].lower()
        or "partida" in r["summary"].lower()
        or "jogo" in r["summary"].lower()
    )
    # tighten
    ok = (
        r["response_type"] == "match_opinion"
        and r["overwrite_by"] is None
        and not r["bad_tokens"]
        and r["match_opinion_renderer"] is True
        and "Momento" not in r["summary"]
        and "**Fluminense** leitura" not in r["summary"]
    )
    print(f"[opinion] {'OK' if ok else 'FAIL'} type={r['response_type']} "
          f"overwrite={r['overwrite_by']} bad={r['bad_tokens']}")
    print(f"  summary={r['summary'][:140]!r}")
    if not ok:
        failures.append("opinion")

    # Regressions
    cases = {
        "calendar": "tem jogo do fluminense hoje?",
        "team_summary": "me fale sobre o flamengo",
        "small_talk": "oi",
        "repair_setup": "o que você achou do jogo do fluminense ontem?",
    }
    for name, msg in cases.items():
        rr = ask(client, msg)
        results[name] = rr
        if name == "calendar":
            stolen = rr["response_type"] == "match_opinion" and rr.get("match_opinion_renderer")
            # calendar may fail open without API key — must not be mop opinion steal of agenda ask
            cok = not stolen or rr.get("natural_kind") == "team_calendar"
            # Accept team_calendar or empty type, never mop on explicit hoje agenda
            cok = rr.get("natural_kind") in {"team_calendar", "calendar_today", None} or (
                "jogo" in rr["summary"].lower() or "agenda" in rr["summary"].lower()
                or "não achei" in rr["summary"].lower()
                or "nao achei" in rr["summary"].lower()
            )
            cok = rr["response_type"] != "match_opinion"
            print(f"[calendar] {'OK' if cok else 'FAIL'} kind={rr.get('natural_kind')} "
                  f"type={rr['response_type']}")
            if not cok:
                failures.append("calendar")
        elif name == "team_summary":
            # intentional team talk may be team_summary / team_opinion — not overwritten mop-only
            tok = rr["overwrite_by"] is None
            # should not force match_opinion unless recent-match ask
            tok = tok and rr["response_type"] != "match_opinion"
            print(f"[team_summary] {'OK' if tok else 'FAIL'} type={rr['response_type']} "
                  f"overwrite={rr['overwrite_by']}")
            print(f"  summary={rr['summary'][:100]!r}")
            if not tok:
                failures.append("team_summary")
        elif name == "small_talk":
            sok = rr["response_type"] != "match_opinion"
            print(f"[small_talk] {'OK' if sok else 'FAIL'} intent={rr['intent']} "
                  f"type={rr['response_type']}")
            if not sok:
                failures.append("small_talk")

    # Repair: setup then correction
    ask(client, "o que você achou do jogo do fluminense ontem?")
    rep = ask(client, "não foi isso")
    results["repair"] = rep
    rtext = rep["summary"].lower()
    rok = "entendi. posso" not in rtext and len(rep["summary"]) > 20
    # repair should not be leitura rápida panorama
    rok = rok and not rep["bad_tokens"]
    print(f"[repair] {'OK' if rok else 'FAIL'} summary={rep['summary'][:120]!r}")
    if not rok:
        failures.append("repair")

    out_path = ROOT / "observations" / "phase84a5" / "04_FINAL_CAPTURE.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"results": results, "failures": failures}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print()
    if failures:
        print(f"FAIL {failures}")
        return 1
    print("PASS — 8.4-A.5 ownership patch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
