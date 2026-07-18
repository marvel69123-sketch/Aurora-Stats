#!/usr/bin/env python3
"""Phase 8.4-A.8 — short follow-up continuity smoke."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

REFUSAL_CAL = "tem jogo (agenda)"
INTEL = "intelligence_fallback"


def _post(client, msg: str, sid: str) -> dict:
    r = client.post(
        "/aurora/copilot",
        json={"message": msg, "session_id": sid, "debug": True},
    )
    return r.json()


def main() -> int:
    client = TestClient(app)
    failures: list[str] = []
    capture: dict = {"cases": {}}

    # After match_opinion
    sid = "fu84a8_opinion"
    op = _post(client, "o que você achou do jogo do fluminense ontem?", sid)
    oents = op.get("entities") or {}
    capture["cases"]["opinion"] = {
        "type": oents.get("response_type"),
        "owner": oents.get("response_owner"),
    }
    if oents.get("response_type") != "match_opinion":
        failures.append("opinion_not_match_opinion")

    for msg, key in (
        ("mercados?", "mercados_after_opinion"),
        ("placar?", "placar_after_opinion"),
        ("estatísticas?", "estats_after_opinion"),
        ("favorito?", "favorito_after_opinion"),
        ("escalações?", "escalacoes_after_opinion"),
    ):
        d = _post(client, msg, sid)
        e = d.get("entities") or {}
        summary = str(d.get("executive_summary") or "")
        entry = {
            "intent": d.get("intent"),
            "overwrite_by": e.get("overwrite_by"),
            "fallback_kind": e.get("fallback_kind"),
            "followup_context_found": e.get("followup_context_found"),
            "followup_source": e.get("followup_source"),
            "followup_resolved_team": e.get("followup_resolved_team"),
            "followup_resolved_fixture": e.get("followup_resolved_fixture"),
            "followup_before_fallback": e.get("followup_before_fallback"),
            "continuity_followup": e.get("continuity_followup"),
            "agenda_text": REFUSAL_CAL in summary.lower(),
            "prefix": summary[:200].replace("\n", " | "),
        }
        capture["cases"][key] = entry
        if entry["overwrite_by"] == INTEL:
            failures.append(f"{key}_intel_overwrite")
        if entry["agenda_text"] or e.get("fallback_kind") == "calendar_authority":
            failures.append(f"{key}_calendar_steal")
        if not entry["followup_context_found"]:
            failures.append(f"{key}_no_audit_context")
        if not entry["followup_before_fallback"]:
            failures.append(f"{key}_not_before_fallback")
        if not entry["followup_resolved_team"]:
            failures.append(f"{key}_no_resolved_team")
        if entry["prefix"].strip() in {"?", "…", "..."} or len(entry["prefix"].strip()) < 20:
            failures.append(f"{key}_useless_text")
        print(
            "[%s] team=%s before=%s overwrite=%s agenda=%s"
            % (
                key,
                entry["followup_resolved_team"],
                entry["followup_before_fallback"],
                entry["overwrite_by"],
                entry["agenda_text"],
            )
        )

    # After partial analysis
    sid2 = "fu84a8_partial"
    p = _post(client, "analise argentina x espanha", sid2)
    pents = p.get("entities") or {}
    capture["cases"]["partial"] = {
        "prelim": pents.get("preliminary_analysis"),
        "owner": pents.get("response_owner"),
    }
    if not pents.get("preliminary_analysis"):
        failures.append("partial_not_prelim")

    m = _post(client, "mercados?", sid2)
    me = m.get("entities") or {}
    msum = str(m.get("executive_summary") or "")
    capture["cases"]["mercados_after_partial"] = {
        "followup_context_found": me.get("followup_context_found"),
        "followup_source": me.get("followup_source"),
        "followup_resolved_team": me.get("followup_resolved_team"),
        "followup_resolved_fixture": me.get("followup_resolved_fixture"),
        "followup_before_fallback": me.get("followup_before_fallback"),
        "overwrite_by": me.get("overwrite_by"),
        "agenda": REFUSAL_CAL in msum.lower(),
        "prefix": msum[:180].replace("\n", " | "),
    }
    if me.get("overwrite_by") == INTEL or REFUSAL_CAL in msum.lower():
        failures.append("partial_mercados_stolen")
    if not me.get("followup_context_found") or not me.get("followup_before_fallback"):
        failures.append("partial_mercados_audit")
    print(
        "[mercados_after_partial] team=%s source=%s overwrite=%s"
        % (
            me.get("followup_resolved_team"),
            me.get("followup_source"),
            me.get("overwrite_by"),
        )
    )

    # Non-regression: oi / identity still ok on fresh sessions
    st = _post(client, "oi", "fu84a8_st")
    capture["cases"]["small_talk"] = {"intent": st.get("intent")}
    if st.get("intent") not in {"small_talk", "conversation_assist"}:
        if (st.get("entities") or {}).get("assistant_kind") != "small_talk":
            failures.append("regression_small_talk")

    out = ROOT / "observations" / "phase84a8" / "05_CAPTURE.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"failures": failures, **capture}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print()
    if failures:
        print("FAIL", failures)
        return 1
    print("PASS — 8.4-A.8 follow-up continuity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
