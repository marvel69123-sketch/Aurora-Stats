"""
Runtime smoke — Brain Authority multi-turn (no server required).
Simulates router-critical layers with persistent ctx.
"""
from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from src.conversation.brain_authority import (
    apply_topic_boundary,
    crl_may_continue_fixture,
    hydrate_allowed,
    should_clear_topic_boundary,
)
from src.conversation.context_recovery import apply_recovery_to_message, recover_context
from src.conversation.conversation_reasoner import attach_reasoning, reason
from src.conversation.conversation_response_layer import plan_response
from src.conversation.intelligence_fallback import (
    ensure_non_empty_payload,
    try_intelligence_fallback,
)
from src.conversation.natural_conversation import try_natural_conversation
from src.conversation.response_review import run_deep_thinking_engine
from src.conversation.web_intelligence import decide_need_web, gather_web_for_thinking


BANNED = ("Pensando no", "Confiança moderada", "Análise baseada nos dados disponíveis")


def _seed_fixture(ctx: dict, home: str, away: str) -> None:
    ctx["last_home"] = home
    ctx["last_away"] = away
    ctx["last_match"] = f"{home} x {away}"
    ctx["last_fixture"] = ctx["last_match"]
    ctx["conversation_state"] = {
        "active_fixture": ctx["last_match"],
        "active_market": None,
    }


async def turn(ctx: dict, message: str, *, fetch_web: bool = False) -> dict[str, Any]:
    audit: dict[str, Any] = {"message": message}
    rec = recover_context(message, ctx)
    recovered = apply_recovery_to_message(message, ctx)
    audit["recovery"] = {
        "recovered": recovered,
        "teams": rec.teams,
        "goal": rec.inferred_goal,
        "conf": round(rec.confidence, 2),
        "notes": rec.notes,
    }
    think = run_deep_thinking_engine(recovered, ctx, recovery=rec.to_dict())
    audit["deep_thinking"] = {
        "topic_kind": think.get("topic_kind"),
        "want": think.get("user_real_want"),
        "web_need": think.get("web_need"),
        "team": think.get("topic_team"),
        "teams": think.get("topic_teams"),
    }

    clear, why = should_clear_topic_boundary(recovered, ctx, recovery=rec.to_dict())
    audit["topic_boundary"] = {"clear": clear, "reason": why}
    if clear:
        apply_topic_boundary(ctx, reason=why)

    if fetch_web:
        await gather_web_for_thinking(recovered, ctx)
        web = ctx.get("web_thinking") or {}
        audit["need_web"] = {
            "need": web.get("need") or decide_need_web(recovered, ctx=ctx).need,
            "status": web.get("status"),
            "result_count": web.get("result_count"),
            "summary": (web.get("summary") or "")[:80] or None,
            "changed_reasoning": web.get("changed_reasoning"),
            "local_reasoning": web.get("local_reasoning"),
        }
    else:
        d = decide_need_web(recovered, ctx=ctx)
        audit["need_web"] = {"need": d.need, "reason": d.reason}

    payload = await try_natural_conversation(recovered, ctx, {"emojis": "none"})
    source = "natural" if payload else None
    if payload is None:
        payload = try_intelligence_fallback(recovered, ctx, {"emojis": "none"})
        source = "fallback" if payload else None

    # Reasoner + CRL (contamination vector)
    rr = reason(recovered, ctx)
    attach_reasoning(ctx, rr)
    plan = plan_response(recovered, ctx)
    audit["reasoner"] = {
        "type": rr.reasoning_type,
        "action": rr.next_action,
        "fixture": getattr(rr, "active_fixture", None) or (ctx.get("last_match")),
    }
    audit["crl"] = {
        "mode": plan.mode,
        "short_circuit": plan.should_short_circuit,
        "action": plan.used_next_action,
        "reply_preview": (plan.reply_text or "")[:100] or None,
        "may_continue": crl_may_continue_fixture(ctx),
    }

    if payload is None and plan.should_short_circuit and plan.reply_text:
        payload = {
            "executive_summary": plan.reply_text,
            "final_recommendation": plan.reply_text,
            "entities": {"crl": True},
            "intent": "conversation_assist",
            "response_metadata": {},
        }
        source = "crl"

    if payload is None:
        payload = {
            "executive_summary": "?",
            "final_recommendation": "?",
            "entities": {},
            "intent": "unknown",
            "response_metadata": {},
        }
        source = "empty"
        payload = ensure_non_empty_payload(
            payload, message=recovered, ctx=ctx, prefs=None
        )
        source = "ensure_non_empty"

    # If natural/fallback won but CRL would have wrongly continued — flag
    text = str(payload.get("executive_summary") or "")
    audit["final"] = {
        "source": source,
        "preview": text[:180],
        "len": len(text),
        "last_match_after": ctx.get("last_match"),
        "hydrate_allowed": hydrate_allowed(ctx),
    }
    audit["banned_hits"] = [b for b in BANNED if b in text]
    # Mark local reasoning for opinion when web empty
    web = ctx.get("web_thinking") or {}
    if web.get("local_reasoning") and source == "natural":
        audit.setdefault("need_web", {})["local_reasoning"] = True
        audit["need_web"]["changed_reasoning"] = web.get("changed_reasoning")
    return audit


def fail(msg: str, audit: dict | None = None) -> None:
    print(f"\nFAIL: {msg}")
    if audit:
        print(json.dumps(audit, ensure_ascii=False, indent=2)[:1200])
    raise SystemExit(1)


async def test1_state_contamination() -> None:
    print("\n===== TESTE 1 — STATE CONTAMINATION =====")
    ctx: dict = {}
    a1 = await turn(ctx, "quero saber sobre jogo do mirassol x gremio hoje")
    print("T1.1", a1["recovery"]["teams"], a1["deep_thinking"]["topic_kind"], a1["final"]["source"])
    if len(a1["recovery"]["teams"]) < 2:
        fail("Recovery perdeu pair Mirassol/Gremio", a1)
    if a1["deep_thinking"]["topic_kind"] not in {"fixture", "calendar"}:
        fail("DT não é fixture/calendar", a1)
    if a1["banned_hits"]:
        fail(f"template banido: {a1['banned_hits']}", a1)
    # Simulate analysis saved fixture (as engines would)
    _seed_fixture(ctx, "Mirassol", "Gremio")

    a2 = await turn(ctx, "e o horário?")
    print("T1.2 follow-up horário", a2["topic_boundary"], a2["deep_thinking"]["topic_kind"], a2["final"]["source"])
    # Legitimate follow-up may keep or clear — must NOT invent Santos; must not Pensando
    if a2["banned_hits"]:
        fail("template em follow-up horário", a2)

    a3 = await turn(ctx, "e o anterior?")
    print("T1.3 anterior", a3["final"]["source"], a3["crl"]["short_circuit"], "match=", ctx.get("last_match"))

    a4 = await turn(ctx, "e o santos?")
    print("T1.4 santos", a4["topic_boundary"], a4["recovery"]["teams"], "match=", ctx.get("last_match"))
    if a4["topic_boundary"]["clear"] and ctx.get("last_match"):
        fail("Boundary deveria ter limpo last_match", a4)
    # Santos must not get CRL continue on Mirassol x Gremio
    if a4["crl"]["short_circuit"] and a4["final"]["source"] == "crl":
        preview = (a4["crl"]["reply_preview"] or "").lower()
        if "mirassol" in preview or "gremio" in preview or "grêmio" in preview:
            fail("CRL continuou confronto antigo no Santos", a4)

    a5 = await turn(ctx, "e o horário?")
    print("T1.5 horário pós-santos", a5["final"]["source"], a5["banned_hits"], "match=", ctx.get("last_match"))
    if a5["banned_hits"]:
        fail("template banido", a5)
    print("TESTE 1 OK")


async def test2_topic_shifts() -> None:
    print("\n===== TESTE 2 — TROCA DE ASSUNTO =====")
    ctx: dict = {}
    a0 = await turn(ctx, "o que acha do Botafogo?", fetch_web=True)
    print(
        f"  Botafogo -> kind={a0['deep_thinking']['topic_kind']} "
        f"src={a0['final']['source']} banned={a0['banned_hits']}"
    )
    if a0["banned_hits"]:
        fail("banned", a0)
    _seed_fixture(ctx, "Botafogo", "Santos")

    a1 = await turn(ctx, "como ele esta atualmente?", fetch_web=True)
    print(
        f"  follow-up momento -> kind={a1['deep_thinking']['topic_kind']} "
        f"src={a1['final']['source']} crl_sc={a1['crl']['short_circuit']}"
    )
    if a1["final"]["source"] == "crl" and "continuar nesse confronto" in (
        a1["final"]["preview"] or ""
    ):
        fail("momento caiu em CRL continue-fixture", a1)
    if a1["banned_hits"]:
        fail("banned", a1)

    a2 = await turn(ctx, "e o Flamengo?", fetch_web=True)
    print(
        f"  Flamengo -> kind={a2['deep_thinking']['topic_kind']} "
        f"boundary={a2['topic_boundary']} src={a2['final']['source']}"
    )
    if a2["banned_hits"]:
        fail("banned", a2)
    if "flamengo" not in a2["final"]["preview"].lower() and "Flamengo" not in str(
        a2["recovery"]["teams"]
    ):
        fail("Flamengo perdido", a2)

    a3 = await turn(ctx, "tem jogo hoje?")
    print(
        f"  tem jogo hoje -> kind={a3['deep_thinking']['topic_kind']} "
        f"src={a3['final']['source']}"
    )
    if a3["banned_hits"]:
        fail("banned", a3)

    a4 = await turn(ctx, "e o horario?")
    print(
        f"  horario -> kind={a4['deep_thinking']['topic_kind']} "
        f"src={a4['final']['source']} banned={a4['banned_hits']}"
    )
    if a4["banned_hits"]:
        fail("banned", a4)
    print("TESTE 2 OK")


async def test3_calendar_followup() -> None:
    print("\n===== TESTE 3 — CALENDAR =====")
    ctx: dict = {}
    a1 = await turn(ctx, "juventus joga hoje?")
    print("T3.1", a1["recovery"], a1["deep_thinking"]["topic_kind"], a1["final"]["source"])
    if a1["banned_hits"]:
        fail("banned", a1)
    # Keep juventus as soft focus without full fixture lock from wrong club
    if a1["recovery"]["teams"] and "Juventus" in a1["recovery"]["teams"]:
        ctx["last_home"] = "Juventus"
        # don't set full foreign fixture

    a2 = await turn(ctx, "e amanha?")
    print("T3.2 amanha", a2["topic_boundary"], a2["deep_thinking"]["topic_kind"], a2["final"]["source"])
    if a2["banned_hits"]:
        fail("banned", a2)

    a3 = await turn(ctx, "e o horario?")
    print("T3.3 horario", a3["final"]["source"], a3["crl"]["short_circuit"])
    if a3["banned_hits"]:
        fail("banned", a3)
    print("TESTE 3 OK")


async def test4_small_clubs() -> None:
    print("\n===== TESTE 4 — TIMES PEQUENOS =====")
    ctx: dict = {}
    for msg in (
        "XV de Piracicaba joga hoje?",
        "Juventus da Mooca joga hoje?",
        "Alta joga hoje?",
    ):
        a = await turn(ctx, msg)
        text = a["final"]["preview"]
        print(f"  {msg!r} -> src={a['final']['source']} q={text.strip()=='?'} banned={a['banned_hits']}")
        if text.strip() == "?":
            fail("retornou ?", a)
        if a["banned_hits"]:
            fail("template", a)
        if len(text) < 20:
            fail("resposta curta demais / robótica", a)
    print("TESTE 4 OK")


async def test5_mixed() -> None:
    print("\n===== TESTE 5 — MISTURA =====")
    ctx: dict = {}
    a1 = await turn(ctx, "o que achou da Copa?")
    print("T5.1 Copa", a1["deep_thinking"]["topic_kind"], a1["final"]["source"])
    _seed_fixture(ctx, "Brasil", "Argentina")

    a2 = await turn(ctx, "e do Flamengo?")
    print("T5.2 Flamengo", a2["topic_boundary"], a2["recovery"]["teams"], "match", ctx.get("last_match"))
    if a2["banned_hits"]:
        fail("banned", a2)

    a3 = await turn(ctx, "tem jogo hoje?")
    print("T5.3 jogo hoje", a3["deep_thinking"]["topic_kind"], a3["final"]["source"])

    a4 = await turn(ctx, "juventus joga que horas?")
    print("T5.4 juventus", a4["topic_boundary"], "match", ctx.get("last_match"), a4["crl"]["may_continue"])
    if ctx.get("last_match") and a4["topic_boundary"]["clear"]:
        fail("boundary clear mas last_match permanece", a4)
    if a4["final"]["source"] == "crl" and "brasil" in (a4["final"]["preview"] or "").lower():
        fail("CRL contaminou Juventus com Copa/Brasil", a4)

    a5 = await turn(ctx, "e o anterior?")
    print("T5.5 anterior", a5["final"]["source"], a5["crl"]["short_circuit"])
    print("TESTE 5 OK")


async def test6_web() -> None:
    print("\n===== TESTE 6 — WEB =====")
    results = []
    for i in range(3):
        ctx: dict = {}
        a = await turn(ctx, "o que acha do Botafogo?", fetch_web=True)
        results.append(a)
        print(
            f"  Botafogo#{i+1} status={a.get('need_web',{}).get('status')} "
            f"changed={a.get('need_web',{}).get('changed_reasoning')} "
            f"local={a.get('need_web',{}).get('local_reasoning')} "
            f"preview={a['final']['preview'][:70]!r}"
        )
        if a["banned_hits"]:
            fail("banned", a)
    ctx = {}
    b = await turn(ctx, "como está o Flamengo atualmente?", fetch_web=True)
    print(
        f"  Flamengo status={b.get('need_web',{}).get('status')} "
        f"changed={b.get('need_web',{}).get('changed_reasoning')} "
        f"local={b.get('need_web',{}).get('local_reasoning')}"
    )
    # Must have either web change OR local reasoning fail-open
    nw = b.get("need_web") or {}
    if not (nw.get("changed_reasoning") or nw.get("local_reasoning") or "mesmo sem" in b["final"]["preview"].lower() or "flamengo" in b["final"]["preview"].lower()):
        # natural should still speak flamengo
        if "flamengo" not in b["final"]["preview"].lower():
            fail("Flamengo sem WEB nem local reasoning", b)
    print("TESTE 6 OK")


async def test7_stress() -> None:
    print("\n===== TESTE 7 — STRESS =====")
    ctx: dict = {}
    msgs = [
        "o que acha do Botafogo?",
        "como está o Flamengo atualmente?",
        "tem jogo do santos hoje?",
        "quero saber sobre jogo do mirassol x gremio hoje",
        "juventus joga que horas?",
        "o que achou da Copa de 2026?",
        "bahia ganha hoje?",
        "e o horário?",
        "e o anterior?",
        "jogos de hoje",
        "jogos de amanhã",
    ]
    contaminations = 0
    prev_match = None
    for msg in msgs:
        before = ctx.get("last_match")
        a = await turn(ctx, msg)
        after = ctx.get("last_match")
        # After Juventus, must not still hold Mirassol x Gremio if clear fired
        if "juventus" in msg.lower() and after and "mirassol" in after.lower():
            contaminations += 1
            fail("stress: Juventus ainda com Mirassol", a)
        if a["banned_hits"]:
            fail(f"stress banned on {msg}", a)
        if a["final"]["preview"].strip() == "?":
            fail(f"stress ? on {msg}", a)
        # Seed after fixture talk
        if "mirassol" in msg.lower() and "gremio" in msg.lower():
            _seed_fixture(ctx, "Mirassol", "Gremio")
            prev_match = ctx.get("last_match")
        print(f"  ok {msg!r} kind={a['deep_thinking']['topic_kind']} src={a['final']['source']}")
    print(f"contaminations={contaminations}")
    print("TESTE 7 OK")


async def main() -> None:
    await test1_state_contamination()
    await test2_topic_shifts()
    await test3_calendar_followup()
    await test4_small_clubs()
    await test5_mixed()
    await test6_web()
    await test7_stress()
    print("\n======== ALL RUNTIME SMOKE PASSED ========")


if __name__ == "__main__":
    asyncio.run(main())
