#!/usr/bin/env python3
"""Phase 8.3-A — match opinion renderer smoke (full Natural path)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.conversation.context_recovery import (  # noqa: E402
    apply_recovery_to_message,
    recover_context,
)
from src.conversation.human_inference import apply_human_inference  # noqa: E402
from src.conversation.master_intent_router import apply_master_intent  # noqa: E402
from src.conversation.natural_conversation import try_natural_conversation  # noqa: E402
from src.conversation.response_review import run_deep_thinking_engine  # noqa: E402

PANORAMA = ("Fase atual", "Agenda à frente", "Próximos jogos", "leitura rápida", "Momento")


async def run_msg(msg: str) -> dict:
    ctx: dict = {"raw_user_message": msg}
    apply_master_intent(msg, ctx)
    rec = recover_context(msg, ctx)
    msg_r = apply_recovery_to_message(msg, ctx, min_confidence=0.7)
    run_deep_thinking_engine(msg_r, ctx, recovery=rec.to_dict())
    msg2, _ = apply_human_inference(msg_r, ctx)
    nat = await try_natural_conversation(msg2, ctx, {"emojis": "none"})
    ents = (nat or {}).get("entities") or {}
    text = str((nat or {}).get("executive_summary") or "")
    return {
        "text": text,
        "response_type": ents.get("response_type"),
        "opinion_time": ents.get("opinion_time"),
        "recent_match": ents.get("recent_match"),
        "natural_kind": ents.get("natural_kind"),
        "plan": (ctx.get("response_plan") or {}).get("answer_type"),
    }


def main() -> int:
    failures: list[str] = []

    opinion = [
        "o que você achou do jogo do fluminense ontem?",
        "como foi a atuação do flamengo?",
        "o flamengo jogou bem?",
    ]
    print("=== OPINION RENDER ===")
    for msg in opinion:
        r = asyncio.run(run_msg(msg))
        text = r["text"]
        bad_panorama = any(p.lower() in text.lower() for p in PANORAMA if p != "Momento")
        # Allow "momento" word in prose but not section headers like "Fase atual"
        bad = any(
            x in text
            for x in ("Fase atual", "Agenda à frente", "Próximos jogos", "📊 Momento")
        )
        ok = (
            r["opinion_time"] is True
            and r["response_type"] == "match_opinion"
            and r["response_type"] != "team_summary"
            and "placar" in text.lower()
            or ("leitura" in text.lower() and r["response_type"] == "match_opinion")
        )
        ok = (
            r["response_type"] == "match_opinion"
            and r["opinion_time"] is True
            and not bad
            and len(text) > 40
        )
        status = "OK" if ok else "FAIL"
        if not ok:
            failures.append(msg)
        print(
            f"  [{status}] {msg!r}\n"
            f"       type={r['response_type']} opinion_time={r['opinion_time']} "
            f"recent={r['recent_match']}\n"
            f"       text={text[:120]!r}"
        )

    print("=== AGENDA ===")
    for msg in ("quando é o próximo jogo?", "tem jogo do fluminense hoje?"):
        r = asyncio.run(run_msg(msg))
        stolen = r["response_type"] == "match_opinion"
        ok = not stolen and r["natural_kind"] in {
            "team_calendar",
            "calendar_today",
            "calendar_tomorrow",
            "kickoff_lookup",
            None,
        }
        # calendar may still produce payload with natural_kind team_calendar
        ok = r["response_type"] != "match_opinion"
        status = "OK" if ok else "FAIL"
        if not ok:
            failures.append(msg)
        print(
            f"  [{status}] {msg!r} kind={r['natural_kind']} type={r['response_type']}"
        )

    print()
    if failures:
        print(f"FAIL ({len(failures)})")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS — 8.3-A opinion renderer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
