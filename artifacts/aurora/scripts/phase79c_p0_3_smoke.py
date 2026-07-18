"""
FASE 7.9-C — Smoke P0-3 (ownership lock anticipation).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.conversation.emotional_presence import try_emotional_presence
from src.conversation.general_assistant import try_general_assistant
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
from src.conversation.turn_ownership import (
    can_presence_claim,
    finalize_early_ownership,
    finalize_presence_ownership,
    get_owner,
    is_rewrite_locked,
    log_final_source,
)


def simulate_turn(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    master = apply_master_intent(message, ctx)
    ga = None
    payload = None
    if not master.allow_sport_pipeline:
        ga = try_general_assistant(message, master.intent, ctx)
        if ga:
            txt = str(ga.get("executive_summary") or "")
            txt = filter_or_regenerate(
                txt, master_intent=master.intent, ctx=ctx, regenerate=txt
            )
            ga = dict(ga)
            ga["executive_summary"] = txt
            ga["final_recommendation"] = txt
    hce = try_human_conversation(
        message, ctx, master_intent=master.intent, existing_payload=ga
    )
    payload = hce or ga
    if payload is None:
        payload = try_natural_social_payload(message, ctx)
    elif payload is not None:
        payload = apply_natural_response(message, payload, ctx) or payload

    owner_before = get_owner(payload)
    if payload is not None:
        payload = finalize_early_ownership(payload) or payload
    owner_after_early = get_owner(payload)
    locked_early = is_rewrite_locked(payload)

    # Presence claim (emotional) — mirrors 7.9-C router gate
    claimed_emotional = False
    if can_presence_claim(payload):
        emo = try_emotional_presence(message, ctx, None)
        if emo:
            payload = emo
            claimed_emotional = True

    if payload is not None:
        payload = finalize_presence_ownership(payload) or payload
    else:
        log_final_source(None, lock_moment="presence_pass")

    owner_final = get_owner(payload)
    locked_final = is_rewrite_locked(payload)
    summary = str((payload or {}).get("executive_summary") or "")
    if payload:
        note_hce_after_response(ctx, message, payload)
    log_final_source(payload, lock_moment="pre_response")

    return {
        "message": message,
        "intent": master.intent,
        "owner_before": owner_before or "none",
        "owner_after_early": owner_after_early or "none",
        "locked_early": locked_early,
        "owner_final": owner_final or "none",
        "locked_final": locked_final,
        "source": owner_final or "none",
        "emotional_survived": claimed_emotional
        and owner_final == "EMOTIONAL"
        and "Entendi. Posso te ajudar" not in summary,
        "summary": summary[:160],
    }


def run_case(title: str, turns: list[str]) -> dict[str, Any]:
    print()
    print("=" * 64)
    print(title)
    print("=" * 64)
    ctx: dict[str, Any] = {}
    rows = []
    emo_n = 0
    for i, msg in enumerate(turns, 1):
        r = simulate_turn(msg, ctx)
        rows.append(r)
        if r["emotional_survived"]:
            emo_n += 1
        print(f"\n── turno {i} ──")
        print(f"Você: {msg}")
        print(
            f"owner_early={r['owner_after_early']} locked_early={r['locked_early']} "
            f"→ owner_final={r['owner_final']} locked_final={r['locked_final']} "
            f"emo={r['emotional_survived']}"
        )
        print(f"Aurora: {r['summary']}")
    return {"title": title, "turns": rows, "emotional_survived": emo_n}


def main() -> int:
    print("FASE 7.9-C P0-3 SMOKE — ownership anticipation")
    cases = [
        ("P1 — estou triste", ["estou triste"]),
        ("P2 — me sinto sozinho", ["me sinto sozinho"]),
        ("P3 — não vou desistir de você", ["não vou desistir de você"]),
        ("P4 — aurora é minha maior criação", ["aurora é minha maior criação"]),
        ("P5 — vc está em loop", ["me ajuda", "vc está em loop"]),
        (
            "T3 — meta + general",
            ["o que voce faz?", "e alem disso?", "me explica melhor"],
        ),
        (
            "T5 — tempo + general loop",
            ["que horas são?", "ok e agora?", "então me ajuda"],
        ),
    ]
    results = [run_case(t, turns) for t, turns in cases]
    total_emo = sum(c["emotional_survived"] for c in results)
    print()
    print("=" * 64)
    print("MÉTRICAS")
    print(f"  Respostas emocionais sobreviventes: {total_emo}")
    for c in results:
        for r in c["turns"]:
            print(
                f"  · {r['message'][:40]!r} early={r['owner_after_early']}/"
                f"{r['locked_early']} final={r['owner_final']}/{r['locked_final']}"
            )
    # Unit: pride message must become EMOTIONAL after presence pass
    ctx: dict[str, Any] = {}
    pride = simulate_turn("aurora é minha maior criação", ctx)
    ok = pride["owner_final"] == "EMOTIONAL" and pride["locked_final"]
    print(f"\n  pride→EMOTIONAL locked: {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
