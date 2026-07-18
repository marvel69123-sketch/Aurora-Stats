#!/usr/bin/env python3
"""Phase 8.4-A.7 — partial analysis recovery smoke."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.partial_analysis import (  # noqa: E402
    allow_partial_analysis,
    build_preliminary_executive,
    detect_rate_limited,
    is_rate_limit_error,
    resolve_preliminary_confidence,
)

REFUSAL = "manteve a conversa com confiança muito baixa"


def main() -> int:
    failures: list[str] = []
    capture: dict = {"cases": {}}

    # Gate: user diagnostic Argentina x Spain
    ok = allow_partial_analysis(
        entity_invalid=False,
        fixture_quality="PARTIAL",
        data_completeness=0.333,
        available_signals=["fixture", "teams", "standings"],
    )
    capture["cases"]["gate_partial_033"] = ok
    if not ok:
        failures.append("gate_partial_033")

    # Completeness 0.20 boundary
    ok20 = allow_partial_analysis(
        entity_invalid=False,
        fixture_quality="PARTIAL",
        data_completeness=0.20,
        available_signals=["teams"],
    )
    capture["cases"]["gate_020"] = ok20
    if not ok20:
        failures.append("gate_020")

    # Below threshold without rate limit
    deny = allow_partial_analysis(
        entity_invalid=False,
        fixture_quality="PARTIAL",
        data_completeness=0.10,
        available_signals=["teams"],
    )
    capture["cases"]["gate_010_deny"] = not deny
    if deny:
        failures.append("gate_010_should_deny")

    # Rate limit keeps analysis
    rl = allow_partial_analysis(
        entity_invalid=False,
        fixture_quality="PARTIAL",
        data_completeness=0.10,
        available_signals=["teams", "fixture"],
        rate_limited=True,
    )
    capture["cases"]["gate_rate_limit"] = rl
    if not rl:
        failures.append("gate_rate_limit")

    # Invalid still refuses
    inv = allow_partial_analysis(
        entity_invalid=True,
        fixture_quality="INVALID",
        data_completeness=0.9,
        available_signals=["teams"],
    )
    capture["cases"]["gate_invalid_deny"] = not inv
    if inv:
        failures.append("gate_invalid")

    # Rate limit detector
    if not is_rate_limit_error("Too many requests"):
        failures.append("rate_detect")
    if not detect_rate_limited(notes=["[api_fetch] Too many requests"]):
        failures.append("rate_detect_notes")

    score, label = resolve_preliminary_confidence(
        1.2, data_completeness=0.333, rate_limited=True
    )
    capture["cases"]["confidence"] = {"score": score, "label": label}
    if score < 2.0 or score > 5.5 or label not in {"weak", "adequate"}:
        failures.append(f"confidence_band {score} {label}")
    if score <= 1.5:
        failures.append("confidence_still_refusal_cap")

    text = build_preliminary_executive(
        "Argentina",
        "Spain",
        base_summary="Motor note placeholder.",
        missing_signals=["statistics", "xg", "lineups", "score", "referee"],
        available_signals=["fixture", "teams", "standings"],
        data={
            "standings": {
                "home": {"rank": 1, "points": 40, "form": "WWWDW"},
                "away": {"rank": 2, "points": 38, "form": "WDWLW"},
            }
        },
        rate_limited=True,
        confidence_label="weak",
    )
    capture["cases"]["prelim_text"] = text[:400]
    if REFUSAL in text.lower():
        failures.append("prelim_has_refusal")
    if "leitura preliminar" not in text.lower():
        failures.append("prelim_missing_header")
    if "ambas marcam" not in text.lower() and "btts" not in text.lower():
        failures.append("prelim_missing_markets_hint")
    # Must not invent fake xG numbers
    if "xG=" in text or "xg=" in text.lower():
        failures.append("prelim_invented_xg")

    # Integration: soft analyze path via TestClient (may be partial without API key)
    try:
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)
        for msg, key in (
            ("analise argentina x espanha", "case1"),
            ("argentina x espanha", "case2"),
        ):
            r = client.post("/aurora/copilot", json={"message": msg, "debug": True})
            data = r.json()
            summary = str(data.get("executive_summary") or "")
            ents = data.get("entities") or {}
            entry = {
                "http": r.status_code,
                "response_type": ents.get("response_type"),
                "fixture_quality": ents.get("fixture_quality")
                or data.get("fixture_quality"),
                "preliminary_analysis": ents.get("preliminary_analysis"),
                "has_refusal": REFUSAL in summary.lower(),
                "summary_prefix": summary[:220],
                "conf": (data.get("confidence") or {}).get("label"),
            }
            capture["cases"][key] = entry
            if entry["has_refusal"]:
                failures.append(f"{key}_refusal")
            if "leitura preliminar" not in summary.lower():
                failures.append(f"{key}_no_preliminary_text")
            if not ents.get("preliminary_analysis"):
                if ents.get("entity_invalid") is not True:
                    failures.append(f"{key}_no_preliminary_flag")
            if "leitura ainda cautelosa" in summary.lower():
                failures.append(f"{key}_personality_overwrite")
            print(
                f"[{key}] refusal={entry['has_refusal']} "
                f"prelim={entry['preliminary_analysis']} "
                f"q={entry['fixture_quality']} "
                f"text={entry['summary_prefix'][:80]!r}"
            )

        # Invalid fiction should still refuse / not be preliminary sports analysis
        bad = client.post(
            "/aurora/copilot",
            json={"message": "analise goku x naruto", "debug": True},
        ).json()
        bsum = str(bad.get("executive_summary") or "")
        bents = bad.get("entities") or {}
        capture["cases"]["case4_invalid"] = {
            "summary_prefix": bsum[:180],
            "entity_invalid": bents.get("entity_invalid"),
            "fixture_quality": bents.get("fixture_quality") or bad.get("fixture_quality"),
            "preliminary_analysis": bents.get("preliminary_analysis"),
        }
        # Must not look like a confident full match reading for fiction
        if bents.get("preliminary_analysis") is True and bents.get("entity_invalid") is True:
            failures.append("case4_prelim_on_invalid")
        print(
            f"[case4] invalid={bents.get('entity_invalid')} "
            f"prelim={bents.get('preliminary_analysis')} "
            f"q={bents.get('fixture_quality')}"
        )

        # Non-regression: opinion
        op = client.post(
            "/aurora/copilot",
            json={
                "message": "o que você achou do jogo do fluminense ontem?",
                "debug": True,
            },
        ).json()
        oents = op.get("entities") or {}
        capture["cases"]["regression_opinion"] = {
            "response_type": oents.get("response_type"),
            "overwrite_by": oents.get("overwrite_by"),
        }
        if oents.get("response_type") != "match_opinion":
            failures.append("regression_opinion")
        print(f"[opinion] type={oents.get('response_type')}")

        st = client.post(
            "/aurora/copilot", json={"message": "oi", "debug": True}
        ).json()
        capture["cases"]["regression_small_talk"] = {
            "intent": st.get("intent"),
            "assistant_kind": (st.get("entities") or {}).get("assistant_kind"),
        }
        if st.get("intent") not in {"small_talk", "conversation_assist"}:
            # small_talk expected
            if (st.get("entities") or {}).get("assistant_kind") != "small_talk":
                failures.append("regression_small_talk")
        print(f"[small_talk] intent={st.get('intent')}")
    except Exception as exc:
        failures.append(f"integration:{exc}")
        print("integration skipped/fail", exc)

    out = ROOT / "observations" / "phase84a7" / "05_CAPTURE_AFTER_PATCH.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"failures": failures, **capture}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    if failures:
        print("FAIL", failures)
        return 1
    print("PASS — 8.4-A.7 partial analysis recovery")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
