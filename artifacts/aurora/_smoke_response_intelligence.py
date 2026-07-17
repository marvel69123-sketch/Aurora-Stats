"""Smoke HUMANO — Response Intelligence (Gemini-like usefulness)."""
from __future__ import annotations

import asyncio

from src.conversation.context_recovery import apply_recovery_to_message, recover_context
from src.conversation.human_inference import apply_human_inference
from src.conversation.natural_conversation import try_natural_conversation
from src.conversation.response_intelligence import compose_intelligent_reply
from src.conversation.response_reflection import reflect_response
from src.conversation.response_review import run_deep_thinking_engine

CASES = [
    "Botafogo",
    "Flamengo",
    "Como está o Flamengo?",
    "Arsenal x Chelsea",
    "Analisar Arsenal x Chelsea",
    "fale sobre o Fluminense",
    "e o Londrina?",
]

BANNED = (
    "evitaria opinião engessada",
    "olharia menos o hype",
    "é uma agremiação",
    "Clube de Regatas do",
)


def fail(m, d=None):
    print("FAIL:", m)
    if d:
        print(" ", d[:400] if isinstance(d, str) else d)
    raise SystemExit(1)


async def turn(msg: str) -> dict:
    ctx: dict = {"raw_user_message": msg}
    rec = recover_context(msg, ctx)
    recovered = apply_recovery_to_message(msg, ctx)
    run_deep_thinking_engine(recovered, ctx, recovery=rec.to_dict())
    out, inf = apply_human_inference(recovered, ctx)

    text = ""
    source = "none"
    if inf.intent == "match_analysis":
        # Engines own full analysis; show soft briefing quality from RI
        text = await compose_intelligent_reply(
            out,
            ctx,
            force_type="match_analysis",
            team=inf.team,
        ) or ""
        source = "match_briefing"
    else:
        payload = await try_natural_conversation(out, ctx, {"emojis": "none"})
        if payload:
            text = str(payload.get("executive_summary") or "")
            source = "natural"
        if not text:
            text = await compose_intelligent_reply(out, ctx) or ""
            source = "compose"

    ref = reflect_response(text, question=msg)
    banned = [b for b in BANNED if b.lower() in text.lower()]
    return {
        "msg": msg,
        "intent": inf.intent,
        "source": source,
        "ok": ref.ok and not banned,
        "ref": ref.to_dict(),
        "banned": banned,
        "preview": text[:280],
        "full": text,
    }


async def main() -> None:
    print("=== RESPONSE INTELLIGENCE — HUMAN SMOKE ===\n")
    fails = 0
    for msg in CASES:
        r = await turn(msg)
        status = "OK" if r["ok"] else "WEAK"
        if not r["ok"]:
            fails += 1
        print(f"[{status}] {msg}")
        print(f"  intent={r['intent']} source={r['source']} ref_ok={r['ref']['ok']}")
        print(f"  {r['preview'].replace(chr(10), ' | ')}")
        if r["banned"]:
            print(f"  BANNED={r['banned']}")
        print()
        # Perception checklist
        text = r["full"]
        print(
            "  parece_inteligente?",
            "📊" in text or "⚔" in text,
            "| útil?",
            r["ref"]["feels_useful"],
            "| pensou?",
            r["ref"]["answers_question"],
        )
        print()

    if fails:
        fail(f"{fails}/{len(CASES)} cases failed usefulness bar")
    print("======== RESPONSE INTELLIGENCE SMOKE OK ========")


if __name__ == "__main__":
    asyncio.run(main())
