#!/usr/bin/env python3
"""Phase 8.3-B — conversation continuity smoke."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.conversation.conversation_continuity import (  # noqa: E402
    apply_continuity_resolve,
    get_continuity,
    note_continuity,
)
from src.conversation.conversation_repair import (  # noqa: E402
    note_repair_memory,
    try_conversation_repair,
)
from src.conversation.master_intent_router import apply_master_intent  # noqa: E402
from src.conversation.short_conversation_memory import note_short_memory  # noqa: E402

ENTENDI = "Entendi. Posso te ajudar"


def main() -> int:
    failures: list[str] = []

    # --- Arm via repair + memory ---
    ctx: dict = {}
    note_repair_memory(
        ctx,
        "o que você achou do jogo do fluminense ontem?",
        {
            "executive_summary": "agenda errada",
            "entities": {"team": "Fluminense"},
        },
    )
    note_short_memory(
        ctx,
        "o que você achou do jogo do fluminense ontem?",
        {
            "executive_summary": "agenda errada",
            "entities": {"team": "Fluminense"},
        },
    )
    rep = try_conversation_repair("não foi isso", ctx)
    note_continuity(ctx, "não foi isso", rep)
    cont = get_continuity(ctx)
    if not cont.get("active"):
        failures.append("T0 continuity not armed after repair")

    # --- sim → should rewrite to Fluminense opinion, sport master ---
    sim = apply_continuity_resolve("sim", ctx)
    if "Fluminense" not in sim and "fluminense" not in sim.lower():
        failures.append(f"T1 sim rewrite missing team: {sim!r}")
    if sim.strip().lower() == "sim":
        failures.append("T1 sim was not rewritten")
    m = apply_master_intent(sim, dict(ctx))
    if not m.allow_sport_pipeline:
        failures.append(f"T1 master not sport after sim: {m.intent}")
    print(f"[T1] sim → {sim!r} master={m.intent} sport={m.allow_sport_pipeline}")

    # Simulate opinion reply after affirm
    note_continuity(
        ctx,
        sim,
        {
            "executive_summary": "opinião…",
            "entities": {
                "team": "Fluminense",
                "response_type": "match_opinion",
                "match_opinion_renderer": True,
                "recent_match": True,
                "opinion_time": True,
            },
        },
    )

    # --- leitura rápida ---
    lr = apply_continuity_resolve("leitura rápida", ctx)
    if "Fluminense" not in lr:
        failures.append(f"T2 leitura missing team: {lr!r}")
    if "leitura" not in lr.lower():
        failures.append(f"T2 leitura rewrite odd: {lr!r}")
    m2 = apply_master_intent(lr, dict(ctx))
    if not m2.allow_sport_pipeline:
        failures.append(f"T2 not sport: {m2.intent}")
    print(f"[T2] leitura rápida → {lr!r} sport={m2.allow_sport_pipeline}")
    note_continuity(
        ctx,
        lr,
        {
            "entities": {
                "team": "Fluminense",
                "response_type": "match_opinion",
                "match_opinion_renderer": True,
            }
        },
    )

    # --- placar ---
    pl = apply_continuity_resolve("placar", ctx)
    if "placar" not in pl.lower() or "Fluminense" not in pl:
        failures.append(f"T3 placar: {pl!r}")
    print(f"[T3] placar → {pl!r}")

    # --- e mercados? ---
    mk = apply_continuity_resolve("e mercados?", ctx)
    if "mercado" not in mk.lower() or "Fluminense" not in mk:
        failures.append(f"T4 mercados: {mk!r}")
    print(f"[T4] e mercados? → {mk!r}")

    # --- without continuity, sim stays sim (GA path allowed) ---
    cold = apply_continuity_resolve("sim", {})
    if cold != "sim":
        failures.append(f"T5 cold sim rewritten: {cold!r}")
    print(f"[T5] cold sim → {cold!r}")

    # --- repair still works ---
    ctx_r: dict = {}
    note_repair_memory(
        ctx_r,
        "o que você achou do jogo do fluminense ontem?",
        {"entities": {"team": "Fluminense"}, "executive_summary": "x"},
    )
    r = try_conversation_repair("não foi isso", ctx_r)
    text = str((r or {}).get("executive_summary") or "")
    if ENTENDI in text or not r:
        failures.append("T6 repair broken")
    # continuity must not rewrite repair
    if apply_continuity_resolve("não foi isso", ctx) != "não foi isso":
        # with armed ctx from before — repair signal must pass through
        from src.conversation.conversation_continuity import apply_continuity_resolve as ac

        if ac("não foi isso", ctx) != "não foi isso":
            failures.append("T6 continuity rewrote repair signal")
    print(f"[T6] repair ok")

    print()
    if failures:
        print(f"FAIL ({len(failures)})")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS — 8.3-B conversation continuity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
