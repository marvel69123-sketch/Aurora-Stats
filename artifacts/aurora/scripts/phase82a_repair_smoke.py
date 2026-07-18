#!/usr/bin/env python3
"""Phase 8.2-A — conversation repair smoke (isolated, no sports engines)."""

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
from src.conversation.natural_response_engine import (  # noqa: E402
    classify_social_expression,
)

ENTENDI = "Entendi. Posso te ajudar"


def _text(payload: dict | None) -> str:
    if not payload:
        return ""
    return str(payload.get("executive_summary") or "")


def main() -> int:
    failures: list[str] = []
    ctx: dict = {}

    # --- signal detection ---
    signals = [
        "não foi isso",
        "voce nao entendeu",
        "pensa um pouco",
        "agora entendeu?",
        "voce esta em loop",
        "para de repetir",
        "nao era isso",
        "voce interpretou errado",
        "nao voce nao entendeu oque eu quis dizer",
        "paraaa de fica em loop",
    ]
    for s in signals:
        if not is_repair_signal(s):
            failures.append(f"signal miss: {s!r}")

    non = ["oi", "quem e voce?", "me fale do flamengo", "que bom"]
    for s in non:
        if is_repair_signal(s):
            failures.append(f"false positive: {s!r}")

    # --- que bom → NRE ack (not repair) ---
    if classify_social_expression("que bom") != "ack":
        failures.append("que bom should classify as NRE ack")

    # --- scripted memory + repair (Fluminense case) ---
    note_repair_memory(
        ctx,
        "oque voce achou do jogo do fluminense ontem?",
        {
            "executive_summary": "⚽ Jogos do Fluminense hoje\n...",
            "entities": {"team": "Fluminense", "natural_kind": "team_calendar"},
        },
    )

    p1 = try_conversation_repair("não foi isso", ctx)
    t1 = _text(p1)
    if not p1 or not p1.get("entities", {}).get("conversation_repair"):
        failures.append("repair payload missing for 'não foi isso'")
    if ENTENDI in t1:
        failures.append("Entendi template leaked on 'não foi isso'")
    if "Fluminense" not in t1:
        failures.append(f"expected Fluminense in repair reply, got: {t1!r}")
    if "opini" not in t1.lower() and "partida" not in t1.lower():
        failures.append(f"expected opinion/partida framing, got: {t1!r}")

    note_repair_memory(ctx, "não foi isso", p1)

    p2 = try_conversation_repair("pensa um pouco", ctx)
    t2 = _text(p2)
    if ENTENDI in t2:
        failures.append("Entendi on 'pensa um pouco'")
    if not p2:
        failures.append("no repair for 'pensa um pouco'")

    note_repair_memory(ctx, "pensa um pouco", p2)

    p3 = try_conversation_repair("agora entendeu?", ctx)
    t3 = _text(p3)
    if ENTENDI in t3:
        failures.append("Entendi on 'agora entendeu?'")
    if not p3:
        failures.append("no repair for 'agora entendeu?'")

    # --- approval flow (module-level) ---
    flow = [
        ("oi", False),
        ("quem é você?", False),
        ("que bom", False),
        ("me fale do flamengo", False),
        ("o que você achou do jogo do fluminense ontem?", False),
        ("não foi isso", True),
        ("pensa um pouco", True),
        ("agora entendeu?", True),
    ]
    ctx2: dict = {}
    print("=== Flow 8.2-A ===")
    for msg, expect_repair in flow:
        # simulate prior substantive turns feeding memory
        if "flamengo" in msg.lower():
            note_repair_memory(
                ctx2,
                msg,
                {
                    "executive_summary": "Flamengo leitura...",
                    "entities": {"team": "Flamengo", "natural_kind": "team_opinion"},
                },
            )
        elif "fluminense" in msg.lower() and "achou" in msg.lower():
            note_repair_memory(
                ctx2,
                msg,
                {
                    "executive_summary": "Jogos do Fluminense hoje...",
                    "entities": {"team": "Fluminense", "natural_kind": "team_calendar"},
                },
            )
        elif not expect_repair:
            note_repair_memory(ctx2, msg, {"executive_summary": "ok", "entities": {}})

        rep = try_conversation_repair(msg, ctx2)
        got = bool(rep)
        text = _text(rep) if rep else "(continue pipeline)"
        ok = got == expect_repair and ENTENDI not in text
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {msg!r} → repair={got} text={text[:90]!r}")
        if not ok:
            failures.append(f"flow fail: {msg!r} expect_repair={expect_repair} got={got}")
        if rep:
            note_repair_memory(ctx2, msg, rep)

    print()
    if failures:
        print(f"FAIL ({len(failures)})")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS — all 8.2-A repair checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
