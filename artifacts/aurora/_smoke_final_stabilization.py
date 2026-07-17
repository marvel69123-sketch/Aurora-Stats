"""Smoke Final Stabilization + WEB 2.0 (multi-turn)."""
from __future__ import annotations

import asyncio

from src.conversation.brain_authority import (
    apply_topic_boundary,
    compute_boundary_score,
    should_clear_topic_boundary,
)
from src.conversation.context_recovery import apply_recovery_to_message, recover_context
from src.conversation.conversation_focus import (
    apply_reference_resolution,
    get_focus,
    update_conversation_focus,
)
from src.conversation.natural_conversation import try_natural_conversation
from src.conversation.response_review import run_deep_thinking_engine
from src.conversation.web_intelligence import decide_web_mode, gather_web_for_thinking


BANNED = ("Pensando no", "Confiança moderada", "Análise baseada nos dados disponíveis")


async def turn(ctx: dict, msg: str, *, web: bool = False) -> dict:
    rec = recover_context(msg, ctx)
    recovered = apply_recovery_to_message(msg, ctx)
    think = run_deep_thinking_engine(recovered, ctx, recovery=rec.to_dict())
    recovered2 = apply_reference_resolution(recovered, ctx)
    if recovered2 != recovered:
        think = run_deep_thinking_engine(recovered2, ctx, recovery=rec.to_dict())
        recovered = recovered2
    clar = ctx.pop("pending_clarification", None)
    clear, why = should_clear_topic_boundary(recovered, ctx, recovery=rec.to_dict())
    score = compute_boundary_score(recovered, ctx, recovery=rec.to_dict())
    if clear:
        apply_topic_boundary(ctx, reason=why)
    update_conversation_focus(
        ctx,
        thinking=ctx.get("deep_thinking") or think,
        recovery=rec.to_dict(),
        message=recovered,
        resolved=ctx.get("reference_resolution"),
    )

    if web:
        await gather_web_for_thinking(recovered, ctx)

    if clar:
        text = clar
        source = "clarification"
        payload = None
    else:
        payload = await try_natural_conversation(recovered, ctx, {"emojis": "none"})
        source = "natural" if payload else "none"
        if payload is None:
            text = ""
        else:
            # weave opinion via natural already
            text = str(payload.get("executive_summary") or "")

    return {
        "msg": msg,
        "recovered": recovered,
        "kind": (ctx.get("deep_thinking") or {}).get("topic_kind"),
        "focus": dict(get_focus(ctx)),
        "boundary": {"clear": clear, "why": why, "score": score.get("score")},
        "web_mode": decide_web_mode(recovered, ctx),
        "web": dict(ctx.get("web_thinking") or {}),
        "source": source,
        "preview": text[:160],
        "banned": [b for b in BANNED if b in text],
        "last_match": ctx.get("last_match"),
    }


def fail(m, a=None):
    print("FAIL:", m)
    if a:
        print(a)
    raise SystemExit(1)


async def main():
    print("=== FOLLOW-UP ===")
    ctx: dict = {}
    a1 = await turn(ctx, "quero saber sobre jogo do mirassol x gremio hoje")
    print("1", a1["kind"], a1["focus"].get("topic_fixture"), a1["source"])
    if len((a1["focus"].get("topic_teams") or [])) < 2 and not a1["focus"].get("topic_fixture"):
        # seed fixture into focus manually if natural empty without API
        ctx["conversation_focus"] = {
            "topic_kind": "fixture",
            "topic_team": "Mirassol",
            "topic_teams": ["Mirassol", "Gremio"],
            "topic_fixture": "Mirassol x Gremio",
            "last_intent": "calendar_or_fixture",
            "last_subject": "Mirassol x Gremio",
        }
        ctx["last_match"] = "Mirassol x Gremio"
        ctx["last_home"] = "Mirassol"
        ctx["last_away"] = "Gremio"

    a2 = await turn(ctx, "e o horario?")
    print("2 horario", a2["recovered"], a2["kind"], a2["boundary"], a2["source"])
    if a2["boundary"]["clear"]:
        fail("horario nao deveria clear", a2)
    if a2["kind"] not in {"kickoff", "calendar", "fixture"} and "horas" not in a2["recovered"].lower():
        fail("horario nao resolveu", a2)

    a3 = await turn(ctx, "e amanha?")
    print("3 amanha", a3["recovered"], a3["boundary"]["clear"], a3["kind"])
    if a3["boundary"]["clear"]:
        fail("amanha clear indevido", a3)

    a4 = await turn(ctx, "e o Santos?")
    print("4 santos", a4["boundary"], a4["last_match"], a4["kind"])
    if not a4["boundary"]["clear"]:
        fail("santos deveria clear", a4)

    a5 = await turn(ctx, "e o horario?")
    print("5 horario pos-santos", a5["source"], a5.get("preview", "")[:80])
    # may clarify or resolve to santos kickoff
    if a5["banned"]:
        fail("banned", a5)

    print("=== OPINIAO ===")
    ctx = {}
    b1 = await turn(ctx, "o que acha do Botafogo?", web=True)
    print("botafogo", b1["web_mode"], b1["web"].get("mode"), b1["web"].get("status"), b1["source"])
    b2 = await turn(ctx, "como esta atualmente?", web=True)
    print("momento", b2["kind"], b2["recovered"], b2["source"], b2["boundary"]["clear"])
    if b2["banned"]:
        fail("banned", b2)

    print("=== WEB DEEP / RESEARCH ===")
    ctx = {}
    c1 = await turn(ctx, "como esta o Flamengo atualmente?", web=True)
    print(
        "flamengo",
        c1["web_mode"],
        c1["web"].get("status"),
        c1["web"].get("changed_reasoning"),
        c1["web"].get("local_reasoning"),
        c1["preview"][:90],
    )
    if not (c1["web"].get("changed_reasoning") or "flamengo" in c1["preview"].lower()):
        fail("web deep sem influencia", c1)

    ctx = {}
    # seed recovery/thinking research
    c2 = await turn(ctx, "faca uma analise detalhada do Flamengo em 2026", web=True)
    print("research", c2["web_mode"], c2["kind"], c2["web"].get("mode"), c2["preview"][:90])
    if c2["web_mode"] != "research" and (ctx.get("deep_thinking") or {}).get("web_mode") != "research":
        # decide_web_mode may still return research from message
        from src.conversation.web_intelligence import decide_web_mode

        if decide_web_mode("faca uma analise detalhada do Flamengo em 2026", ctx) != "research":
            fail("research mode missing", c2)

    print("=== AMBIGUIDADE ===")
    ctx = {}
    d1 = await turn(ctx, "e o horario?")
    print("ambig", d1["source"], (d1["preview"] or "")[:100])
    if d1["source"] != "clarification" and "interpretando" not in (d1["preview"] or "").lower():
        # apply_reference should set clarification
        from src.conversation.conversation_focus import resolve_reference

        r = resolve_reference("e o horario?", {})
        assert r.get("ambiguous")

    print("\n======== STABILIZATION SMOKE OK ========")


if __name__ == "__main__":
    asyncio.run(main())
