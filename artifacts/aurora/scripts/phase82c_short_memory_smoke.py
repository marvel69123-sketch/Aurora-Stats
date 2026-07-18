#!/usr/bin/env python3
"""Phase 8.2-C — short conversation memory smoke."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.conversation.conversation_repair import (  # noqa: E402
    is_repair_signal,
    note_repair_memory,
    try_conversation_repair,
)
from src.conversation.master_intent_router import apply_master_intent  # noqa: E402
from src.conversation.short_conversation_memory import (  # noqa: E402
    apply_short_memory_resolve,
    get_short_memory,
    note_short_memory,
)

ENTENDI = "Entendi. Posso te ajudar"


def main() -> int:
    failures: list[str] = []

    # --- Test 1: último jogo → o que achou dele? ---
    ctx1: dict = {}
    q1 = "qual foi o último jogo do flamengo?"
    note_short_memory(
        ctx1,
        q1,
        {
            "executive_summary": "Último jogo do Flamengo…",
            "entities": {"team": "Flamengo"},
        },
    )
    mem1 = get_short_memory(ctx1)
    if mem1.get("last_team") != "Flamengo":
        failures.append(f"T1 last_team={mem1.get('last_team')}")
    if mem1.get("last_question_type") != "last_match":
        failures.append(f"T1 qtype={mem1.get('last_question_type')}")
    if "Flamengo" not in str(mem1.get("last_fixture") or ""):
        failures.append(f"T1 fixture={mem1.get('last_fixture')}")

    follow1 = "o que você achou dele?"
    resolved1 = apply_short_memory_resolve(follow1, ctx1)
    if "Flamengo" not in resolved1:
        failures.append(f"T1 resolve miss team: {resolved1!r}")
    if "último jogo" not in resolved1.lower() and "ultimo jogo" not in resolved1.lower():
        failures.append(f"T1 resolve miss last game: {resolved1!r}")
    if "dele" in resolved1.lower():
        failures.append(f"T1 still has pronoun: {resolved1!r}")

    m = apply_master_intent(resolved1, ctx1)
    if not m.allow_sport_pipeline:
        failures.append(f"T1 master not sport after resolve: {m.intent}")

    print(f"[T1] {follow1!r} → {resolved1!r} master={m.intent} sport={m.allow_sport_pipeline}")

    # --- Test 2: flamengo → e o palmeiras? → e dele? ---
    ctx2: dict = {}
    note_short_memory(
        ctx2,
        "qual foi o último jogo do flamengo?",
        {"executive_summary": "…", "entities": {"team": "Flamengo"}},
    )
    note_short_memory(
        ctx2,
        "e o palmeiras?",
        {"executive_summary": "Sobre o Palmeiras…", "entities": {"team": "Palmeiras"}},
    )
    mem2 = get_short_memory(ctx2)
    if mem2.get("last_team") != "Palmeiras":
        failures.append(f"T2 entity switch failed: {mem2.get('last_team')}")
    if "Palmeiras" not in str(mem2.get("last_fixture") or ""):
        failures.append(f"T2 fixture not updated: {mem2.get('last_fixture')}")

    follow2 = "e o dele?"
    resolved2 = apply_short_memory_resolve(follow2, ctx2)
    if "Palmeiras" not in resolved2:
        failures.append(f"T2 dele should be Palmeiras: {resolved2!r}")
    if "Flamengo" in resolved2:
        failures.append(f"T2 stale Flamengo: {resolved2!r}")
    print(f"[T2] {follow2!r} → {resolved2!r} team={mem2.get('last_team')}")

    # --- Test 3: repair still works ---
    ctx3: dict = {}
    note_repair_memory(
        ctx3,
        "o que você achou do jogo do fluminense ontem?",
        {
            "executive_summary": "agenda…",
            "entities": {"team": "Fluminense"},
        },
    )
    note_short_memory(
        ctx3,
        "o que você achou do jogo do fluminense ontem?",
        {
            "executive_summary": "agenda…",
            "entities": {"team": "Fluminense"},
        },
    )
    if not is_repair_signal("não foi isso"):
        failures.append("T3 repair signal missing")
    # resolve must NOT swallow repair
    if apply_short_memory_resolve("não foi isso", ctx3) != "não foi isso":
        failures.append("T3 short memory rewrote repair signal")
    rep = try_conversation_repair("não foi isso", ctx3)
    text = str((rep or {}).get("executive_summary") or "")
    if not rep or not (rep.get("entities") or {}).get("conversation_repair"):
        failures.append("T3 repair payload missing")
    if ENTENDI in text:
        failures.append("T3 Entendi leaked")
    if "Fluminense" not in text:
        failures.append(f"T3 repair lost team: {text!r}")
    print(f"[T3] repair ok text={text[:90]!r}")

    print()
    if failures:
        print(f"FAIL ({len(failures)})")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS — all 8.2-C short memory checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
