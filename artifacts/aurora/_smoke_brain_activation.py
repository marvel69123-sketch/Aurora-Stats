"""Local smoke — Brain Activation (no server). Fail-open checks."""
from __future__ import annotations

import asyncio
import logging

logging.basicConfig(level=logging.WARNING)

from src.conversation.context_recovery import apply_recovery_to_message, recover_context
from src.conversation.intelligence_fallback import try_intelligence_fallback
from src.conversation.natural_conversation import try_natural_conversation
from src.conversation.response_review import (
    review_and_enrich_payload,
    run_deep_thinking_engine,
)
from src.conversation.web_intelligence import (
    decide_need_web,
    gather_web_for_thinking,
    weave_web_into_draft,
)


def _print(title: str, **kv):
    print(f"\n=== {title} ===")
    for k, v in kv.items():
        print(f"  {k}: {v}")


async def main():
    # TEST 1
    msg = "oq acha do bota agr"
    ctx: dict = {}
    rec = recover_context(msg, ctx)
    recovered = apply_recovery_to_message(msg, ctx)
    think = run_deep_thinking_engine(recovered, ctx, recovery=rec.to_dict())
    await gather_web_for_thinking(recovered, ctx)
    payload = await try_natural_conversation(recovered, ctx, {"emojis": "none"})
    if not payload:
        payload = try_intelligence_fallback(recovered, ctx, {"emojis": "none"})
    web = ctx.get("web_thinking") or {}
    _print(
        "TEST1 oq acha do bota agr",
        recovered=recovered,
        goal=rec.inferred_goal,
        teams=rec.teams,
        conf=rec.confidence,
        real_want=think.get("user_real_want"),
        needs_web=think.get("needs_web"),
        depth=think.get("depth"),
        web_status=web.get("status"),
        changed=web.get("changed_reasoning"),
        reply_preview=(payload or {}).get("executive_summary", "")[:180],
    )

    # TEST 2
    msg = "qorf ve jgo santus hj"
    ctx = {}
    rec = recover_context(msg, ctx)
    recovered = apply_recovery_to_message(msg, ctx)
    think = run_deep_thinking_engine(recovered, ctx, recovery=rec.to_dict())
    _print(
        "TEST2 qorf ve jgo santus hj",
        recovered=recovered,
        teams=rec.teams,
        conf=rec.confidence,
        goal=rec.inferred_goal,
        real_want=think.get("user_real_want"),
    )

    # TEST 3
    msg = "o que achou da Copa de 2026?"
    ctx = {}
    rec = recover_context(msg, ctx)
    think = run_deep_thinking_engine(msg, ctx, recovery=rec.to_dict())
    await gather_web_for_thinking(msg, ctx)
    payload = await try_natural_conversation(msg, ctx, {"emojis": "none"})
    summary = (payload or {}).get("executive_summary", "")
    _print(
        "TEST3 Copa 2026",
        needs_web=think.get("needs_web"),
        web_need=think.get("web_need"),
        empty_q=summary.strip() == "?",
        reply_len=len(summary),
        preview=summary[:160],
    )

    # TEST 4
    msg = "como está o Flamengo atualmente?"
    ctx = {}
    rec = recover_context(msg, ctx)
    recovered = apply_recovery_to_message(msg, ctx)
    think = run_deep_thinking_engine(recovered, ctx, recovery=rec.to_dict())
    # Force a summary so weave is deterministic offline
    ctx["web_thinking"] = {
        "summary": "Flamengo busca regularidade no Brasileirão",
        "status": "ready_for_reasoning",
        "need": "optional",
    }
    d = decide_need_web(recovered, ctx=ctx)
    payload = await try_natural_conversation(recovered, ctx, {"emojis": "none"})
    _print(
        "TEST4 Flamengo atualmente",
        decision_need=d.need,
        decision_reason=d.reason,
        changed=ctx.get("web_thinking", {}).get("changed_reasoning"),
        preview=(payload or {}).get("executive_summary", "")[:200],
    )

    # TEST 5
    msg = "bahia ganha hoje?"
    ctx = {}
    rec = recover_context(msg, ctx)
    recovered = apply_recovery_to_message(msg, ctx)
    think = run_deep_thinking_engine(recovered, ctx, recovery=rec.to_dict())
    _print(
        "TEST5 bahia ganha hoje",
        recovered=recovered,
        goal=rec.inferred_goal,
        kind=think.get("topic_kind"),
        inference=think.get("needs_inference"),
        real_want=think.get("user_real_want"),
    )

    # TEST 6 — follow-up signal (recovery/thinking only; full FU needs session)
    msg = "e o anterior?"
    ctx = {"deep_thinking": {}, "context_recovery": {}}
    think = run_deep_thinking_engine(msg, ctx, recovery={"confidence": 0.4})
    _print(
        "TEST6 e o anterior?",
        real_want=think.get("user_real_want"),
        surface=think.get("surface_risk"),
        note="follow-up path uses frozen FollowUpEngine at router; thinking marks ambiguity",
    )

    # Review blocked case
    good = (
        "Minha percepção é que o Botafogo vive um momento de identidade no campo — "
        "quando encontra ritmo, joga com coragem."
    )
    out = review_and_enrich_payload(
        {
            "intent": "conversation_assist",
            "entities": {"opinion_time": True},
            "executive_summary": good,
            "final_recommendation": good,
            "response_metadata": {},
        },
        message="oq acha do bota agr",
        ctx={"deep_thinking": {"surface_risk": 0.15, "response_mode": "normal"}},
    )
    rev = (out.get("response_metadata") or {}).get("response_review") or {}
    _print(
        "REVIEW blocked on good answer",
        applied=rev.get("review_applied"),
        blocked=rev.get("blocked_reason"),
        verdict=rev.get("thinking_verdict"),
    )

    # Weave demo
    woven, changed = weave_web_into_draft(
        "Gosto do time quando tem identidade.\n\nQuer aprofundar?",
        {
            "deep_thinking": {"topic_team": "Botafogo"},
            "web_thinking": {
                "summary": "Botafogo em sequência positiva",
                "status": "ready_for_reasoning",
            },
        },
        team="Botafogo",
    )
    _print("WEAVE demo", changed=changed, preview=woven[:220])


if __name__ == "__main__":
    asyncio.run(main())
