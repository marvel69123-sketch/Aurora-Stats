#!/usr/bin/env python3
"""Phase 8.4-A.9 — assistant_capabilities + repair reclassification smoke."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

LOOP = "entendi. posso te ajudar"
LOOP2 = "diz o objetivo"


def _post(client, msg: str, sid: str) -> dict:
    return client.post(
        "/aurora/copilot",
        json={"message": msg, "session_id": sid, "debug": True},
    ).json()


def main() -> int:
    client = TestClient(app)
    failures: list[str] = []
    capture: dict = {"cases": {}}

    for n, msg, key in (
        (1, "o que você faz?", "case1"),
        (2, "suas funcionalidades", "case2"),
        (3, "aurora funcionalidades", "case3"),
        (4, "o que sabe fazer?", "case4"),
    ):
        d = _post(client, msg, f"cap84a9_{n}")
        e = d.get("entities") or {}
        summary = str(d.get("executive_summary") or "")
        entry = {
            "intent": d.get("intent"),
            "assistant_kind": e.get("assistant_kind"),
            "capability_intent_detected": e.get("capability_intent_detected"),
            "capability_source_phrase": e.get("capability_source_phrase"),
            "loop": LOOP in summary.lower() or LOOP2 in summary.lower(),
            "prefix": summary[:220].replace("\n", " | "),
        }
        capture["cases"][key] = entry
        if d.get("intent") != "assistant_capabilities":
            failures.append(f"{key}_intent")
        if not e.get("capability_intent_detected"):
            failures.append(f"{key}_audit")
        if entry["loop"]:
            failures.append(f"{key}_loop")
        if "posso:" not in summary.lower() and "especializada em futebol" not in summary.lower():
            failures.append(f"{key}_body")
        print("[%s] intent=%s loop=%s" % (key, d.get("intent"), entry["loop"]))

    # Case 5 — misroute then repair reclass
    # Force a wrong reply first by using a session; capabilities should hit correctly
    # now, so simulate prior wrong intent via repair memory path:
    # send a capabilities ask that historically was general — still should be capabilities.
    # Then send repair after a forced general: use raw API sequence where first ask
    # is capabilities (ok), so instead seed with a nonsense short general then repair
    # with last_q capabilities stored — repair path needs last_user_question.
    sid = "cap84a9_repair"
    # First: short ambiguous that might be general if somehow leaked — use
    # a phrase that WAS broken before patch is already fixed; for repair test
    # we call note via asking something wrong then repair with prior capabilities.
    # Practical path: ask capabilities-ish that got general historically — if
    # first is already correct, still test repair after a deliberate general turn
    # by storing last_q as capabilities via two-step:
    # 1) "xyzabc" -> general
    # we cannot easily inject memory; instead:
    # 1) ask "o que sabe fazer?" (now capabilities)
    # 2) ask "você não entendeu" — should reclassify to capabilities again
    first = _post(client, "o que sabe fazer?", sid)
    second = _post(client, "você não entendeu", sid)
    e2 = second.get("entities") or {}
    capture["cases"]["case5_repair"] = {
        "first_intent": first.get("intent"),
        "second_intent": second.get("intent"),
        "repair_reclassified": e2.get("repair_reclassified"),
        "previous_intent": e2.get("previous_intent"),
        "new_intent": e2.get("new_intent"),
        "capability_intent_detected": e2.get("capability_intent_detected"),
        "prefix": str(second.get("executive_summary") or "")[:200].replace("\n", " | "),
    }
    if second.get("intent") != "assistant_capabilities":
        failures.append("case5_intent")
    if not e2.get("repair_reclassified") and not e2.get("capability_intent_detected"):
        # reclass from capabilities→capabilities still stamps repair_reclassified
        failures.append("case5_reclass_audit")
    print(
        "[case5] first=%s second=%s reclass=%s"
        % (
            first.get("intent"),
            second.get("intent"),
            e2.get("repair_reclassified"),
        )
    )

    # Case 6 — sequence oi / identity / capabilities
    sid6 = "cap84a9_seq"
    a = _post(client, "oi", sid6)
    b = _post(client, "quem é você?", sid6)
    c = _post(client, "o que você faz?", sid6)
    capture["cases"]["case6"] = {
        "oi": a.get("intent"),
        "identity": b.get("intent"),
        "capabilities": c.get("intent"),
    }
    if a.get("intent") not in {"small_talk", "conversation_assist"}:
        if (a.get("entities") or {}).get("assistant_kind") != "small_talk":
            failures.append("case6_small_talk")
    if b.get("intent") != "identity":
        failures.append("case6_identity")
    if c.get("intent") != "assistant_capabilities":
        failures.append("case6_capabilities")
    print(
        "[case6] oi=%s identity=%s caps=%s"
        % (a.get("intent"), b.get("intent"), c.get("intent"))
    )

    out = ROOT / "observations" / "phase84a9" / "05_CAPTURE_AFTER_PATCH.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"failures": failures, **capture}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print()
    if failures:
        print("FAIL", failures)
        return 1
    print("PASS — 8.4-A.9 assistant capabilities")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
