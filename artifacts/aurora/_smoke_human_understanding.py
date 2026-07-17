"""Smoke — Human Understanding Phase (no commit)."""
from __future__ import annotations

import asyncio

from src.conversation.brain_authority import should_block_analysis_engines
from src.conversation.context_recovery import apply_recovery_to_message, recover_context
from src.conversation.human_inference import (
    apply_human_inference,
    looks_like_encyclopedia_dump,
    repair_unintelligent_reply,
)
from src.conversation.natural_conversation import (
    detect_natural_intent,
    try_natural_conversation,
)
from src.conversation.response_review import run_deep_thinking_engine


CASES = [
    ("Analisar Arsenal x Chelsea", "match_analysis"),
    ("Arsenal x Chelsea", "match_analysis"),
    ("Botafogo", "general_team_talk"),
    ("Flamengo", "general_team_talk"),
    ("Como está o Flamengo?", "team_moment"),
    ("E o Botafogo?", "general_team_talk"),
    ("Mirassol x Grêmio hoje", "calendar_or_fixture"),
]


def fail(m, d=None):
    print("FAIL:", m)
    if d:
        print(" ", d)
    raise SystemExit(1)


async def main() -> None:
    print("=== HUMAN UNDERSTANDING SMOKE ===")
    for msg, want in CASES:
        ctx: dict = {"raw_user_message": msg}
        rec = recover_context(msg, ctx)
        recovered = apply_recovery_to_message(msg, ctx)
        run_deep_thinking_engine(recovered, ctx, recovery=rec.to_dict())
        out, inf = apply_human_inference(recovered, ctx)
        nat = detect_natural_intent(out)
        block = should_block_analysis_engines(ctx)
        print(
            f"[{msg}] intent={inf.intent} kind={inf.topic_kind} "
            f"nat={nat and nat.get('kind')} block_eng={block} "
            f"meant={inf.what_user_meant[:60]}"
        )
        if inf.intent != want:
            fail(f"expected {want}", inf.to_dict())
        if want == "match_analysis":
            if nat is not None:
                fail("natural must not claim match_analysis", nat)
            if block:
                fail("engines must NOT be blocked for match_analysis")
        if want == "general_team_talk":
            payload = await try_natural_conversation(out, ctx, {"emojis": "none"})
            text = str((payload or {}).get("executive_summary") or "")
            if not text or text.strip() == "?":
                fail(f"bare team returned empty/?: {msg}", text)

    dump = (
        "Clube de Regatas do Flamengo (CRF) é uma agremiação poliesportiva "
        "brasileira com sede na cidade do Rio de Janeiro."
    )
    assert looks_like_encyclopedia_dump(dump)
    fixed = repair_unintelligent_reply(
        dump, {"deep_thinking": {"topic_team": "Flamengo", "topic_kind": "opinion"}}
    )
    if "agremiação" in fixed.lower():
        fail("thinking delay did not repair encyclopedia dump", fixed)
    print("ThinkingDelay OK:", fixed[:100])
    print("\n======== HUMAN UNDERSTANDING SMOKE OK ========")


if __name__ == "__main__":
    asyncio.run(main())
