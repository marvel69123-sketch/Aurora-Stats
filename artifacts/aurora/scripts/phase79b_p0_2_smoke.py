"""
FASE 7.9-B — Smoke P0-2 (NRF anti-loop).
Modifica apenas o caminho early NRF (igual ao router) para medir Entendi/bypass.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.conversation.general_assistant import reply_general, try_general_assistant
from src.conversation.human_conversation_engine import (
    note_hce_after_response,
    try_human_conversation,
)
from src.conversation.master_intent_router import apply_master_intent
from src.conversation.natural_response_engine import (
    apply_natural_response,
    try_natural_social_payload,
)
from src.conversation.natural_response_filter import filter_or_regenerate
from src.conversation.pipeline_trace import clear_capture, get_capture
from src.conversation.turn_ownership import finalize_early_ownership

ENTENDI = "Entendi. Posso te ajudar"


def turn(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    clear_capture()
    master = apply_master_intent(message, ctx)
    ga = None
    payload = None
    if not master.allow_sport_pipeline:
        ga = try_general_assistant(message, master.intent, ctx)
        if ga:
            txt = str(ga.get("executive_summary") or "")
            txt2 = filter_or_regenerate(
                txt,
                master_intent=master.intent,
                ctx=ctx,
                regenerate=txt,  # mirrors router early NRF
            )
            ga = dict(ga)
            ga["executive_summary"] = txt2
            ga["final_recommendation"] = txt2
    hce = try_human_conversation(
        message, ctx, master_intent=master.intent, existing_payload=ga
    )
    payload = hce or ga
    if payload is None:
        payload = try_natural_social_payload(message, ctx)
    elif payload is not None:
        payload = apply_natural_response(message, payload, ctx) or payload
    if payload is not None:
        payload = finalize_early_ownership(payload) or payload
    if payload is None:
        summary = f"[no-payload] {master.intent}"
        source = "none"
    else:
        summary = str(payload.get("executive_summary") or "")
        ents = payload.get("entities") or {}
        source = (
            ctx.get("nrf_last_action")
            or ents.get("turn_owner")
            or ents.get("assistant_kind")
            or "payload"
        )
        note_hce_after_response(ctx, message, payload)
    logs = get_capture()
    return {
        "message": message,
        "intent": master.intent,
        "summary": summary,
        "entendi": ENTENDI in summary,
        "source": source,
        "loop_logs": [l for l in logs if "NRF_LOOP_DETECTED" in l or "NRF_BYPASS" in l],
        "nrf_logs": [l for l in logs if "[NRF_" in l],
    }


def run_case(title: str, turns: list[str]) -> dict[str, Any]:
    print()
    print("=" * 64)
    print(title)
    print("=" * 64)
    ctx: dict[str, Any] = {}
    rows = []
    consec = 0
    max_consec = 0
    entendi_n = 0
    for i, msg in enumerate(turns, 1):
        r = turn(msg, ctx)
        rows.append(r)
        if r["entendi"]:
            entendi_n += 1
            consec += 1
            max_consec = max(max_consec, consec)
        else:
            consec = 0
        print(f"\n── turno {i} ──")
        print(f"Você: {msg}")
        print(f"intent={r['intent']} entendi={r['entendi']} source={r['source']}")
        print(f"Aurora: {r['summary'][:200]}")
        for line in r["loop_logs"]:
            print(f"  {line}")
    return {
        "title": title,
        "turns": rows,
        "entendi_count": entendi_n,
        "max_consecutive_entendi": max_consec,
        "loop_detected": any(r["loop_logs"] for r in rows),
    }


def main() -> int:
    print("FASE 7.9-B P0-2 SMOKE — NRF anti-loop")
    cases = [
        ("P1 — vc está em loop", ["me ajuda com uma coisa", "vc está em loop"]),
        ("P2 — para de repetir isso", ["preciso de ajuda", "para de repetir isso"]),
        ("P3 — não funciona", ["me explica", "não funciona"]),
        ("P4 — estou triste", ["estou triste"]),
        (
            "T2 — vague → frustração",
            ["preciso de ajuda", "você não entendeu", "tenta de novo"],
        ),
        (
            "T5 — tempo + general loop",
            ["que horas são?", "ok e agora?", "então me ajuda"],
        ),
    ]
    results = [run_case(t, turns) for t, turns in cases]

    print()
    print("=" * 64)
    print("MÉTRICAS")
    total_entendi = sum(c["entendi_count"] for c in results)
    max_c = max(c["max_consecutive_entendi"] for c in results)
    loops = sum(1 for c in results if c["loop_detected"])
    print(f"  Entendi total (todas as falas): {total_entendi}")
    print(f"  Máx repetições consecutivas Entendi: {max_c}")
    print(f"  Casos com NRF_LOOP_DETECTED/BYPASS: {loops}")
    sticky_fail = max_c >= 2
    print(f"  Loop sticky (>=2 Entendi seguidos): {'SIM (FAIL)' if sticky_fail else 'NÃO (OK)'}")
    print()
    # Unit-level proof of regenerate loop break
    from src.conversation.natural_response_filter import filter_or_regenerate as fr

    ctx2: dict[str, Any] = {}
    g = reply_general("x")
    a1 = fr(g, master_intent="GENERAL_CHAT", ctx=ctx2, regenerate=g)
    a2 = fr(g, master_intent="GENERAL_CHAT", ctx=ctx2, regenerate=g)
    a3 = fr(g, master_intent="GENERAL_CHAT", ctx=ctx2, regenerate=g)
    print("UNIT regenerate×3:")
    print(f"  1 entendi={ENTENDI in a1} prefix={a1[:50]!r}")
    print(f"  2 entendi={ENTENDI in a2} prefix={a2[:50]!r}")
    print(f"  3 entendi={ENTENDI in a3} prefix={a3[:50]!r}")
    unit_ok = (ENTENDI in a1) and (ENTENDI not in a2) and (ENTENDI not in a3)
    print(f"  unit_ok={unit_ok}")
    return 0 if unit_ok and not sticky_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
