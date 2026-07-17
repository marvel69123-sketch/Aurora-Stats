"""Aurora v4.3 — CUE + Human Presence tests."""

from __future__ import annotations

from src.conversation.conversation_intelligence_layer import refine_crl_reply, run_intelligence
from src.conversation.conversation_reasoner import attach_reasoning, reason
from src.conversation.conversation_response_layer import plan_response
from src.conversation.conversation_state import apply_after_analysis
from src.conversation.conversational_understanding import understand
from src.conversation.human_presence import (
    build_presence_payload,
    build_social_presence_reply,
    is_social_presence_turn,
)


def _seed():
    ctx = {}
    apply_after_analysis(
        ctx,
        "Bahia",
        "Chapecoense",
        "Bahia x Chapecoense",
        {
            "best_markets": [{"market": "Mais de 8.5 Escanteios", "risk": "medium"}],
            "final_recommendation": "Mais de 8.5 Escanteios",
        },
    )
    ctx["last_match"] = "Bahia x Chapecoense"
    return ctx


# ── Scenario 1: oi aurora tudo bem? ────────────────────────────────────────

def test_scenario1_greeting_wellbeing_human():
    ctx: dict = {}
    intent = understand("oi aurora tudo bem?", ctx)
    assert intent.explicit_goal == "SOCIAL"
    assert "GREETING" in intent.social_intents
    assert "WELL_BEING_CHECK" in intent.social_intents
    assert is_social_presence_turn(intent.to_dict())
    reply = build_social_presence_reply("oi aurora tudo bem?", intent.to_dict(), ctx)
    assert reply
    low = reply.lower()
    assert "sou a aurora" not in low
    assert "tudo" in low or "certo" in low or "oi" in low
    payload = build_presence_payload(reply, {})
    assert payload["best_markets"] == []
    assert payload.get("entities", {}).get("show_header") is False
    assert payload.get("entities", {}).get("human_presence") is True


# ── Scenario 2: fale sobre bahia e chapecoense amanhã ──────────────────────

def test_scenario2_future_analysis_understanding():
    ctx: dict = {}
    msg = "fale sobre o jogo da bahia e chapecoense de amanhã"
    intent = understand(msg, ctx)
    assert intent.explicit_goal == "ASK_FUTURE_ANALYSIS"
    assert intent.temporal_context == "tomorrow"
    assert intent.entities.get("home") == "Bahia"
    assert intent.entities.get("away") == "Chapecoense"
    assert intent.rewrite_for_pipeline
    assert intent.rewrite_for_pipeline.lower().startswith("analise")
    assert "bahia" in intent.rewrite_for_pipeline.lower()
    assert "chapecoense" in intent.rewrite_for_pipeline.lower()
    assert " x " in intent.rewrite_for_pipeline.lower()
    # Must not collapse to empty clarify goal
    assert intent.confidence >= 0.8


# ── Scenario 3: opinion / risk / why feel more reflective ──────────────────

def test_scenario3_opinion_risk_why_have_thought_fields():
    ctx = _seed()
    for msg in ("oq acha desse jogo?", "vale a pena?", "por que?"):
        cue = understand(msg, ctx)
        thought = reason(msg, ctx)
        attach_reasoning(ctx, thought)
        cil = run_intelligence(msg, ctx)
        plan = plan_response(msg, ctx)
        refined = refine_crl_reply(plan.reply_text, ctx)
        assert cue.understood_intent
        assert cue.implicit_meaning
        assert cil.understood_intent or cue.understood_intent
        assert cil.implicit_meaning or cue.implicit_meaning
        assert plan.should_short_circuit is True
        assert refined
        # Less brochure / more presence-ish
        assert "Sou a **Aurora**" not in refined


# ── Scenario 4: long conversation naturalness proxy ────────────────────────

def test_scenario4_long_conversation_presence_and_memory():
    ctx = _seed()
    script = [
        "oi tudo bem?",
        "e escanteios?",
        "e gols?",
        "qual parece melhor?",
        "por que?",
        "vale a pena?",
        "não gostei",
        "algo mais conservador?",
        "e esse?",
        "oq acha?",
        "tem algo melhor?",
        "por que?",
        "e gols?",
        "qual parece melhor?",
        "não gostei",
        "algo mais agressivo?",
        "e escanteios?",
        "vale a pena?",
        "e esse?",
        "oq acha?",
        "boa noite",
        "e gols?",
        "qual parece melhor?",
        "por que?",
        "não gostei",
        "tem algo melhor?",
        "e cartões?",
        "e esse?",
        "oq acha?",
        "por que?",
        "fale sobre o jogo da bahia e chapecoense de amanhã",
    ]
    replies: list[str] = []
    brochure = 0
    for msg in script:
        cue = understand(msg, ctx)
        if is_social_presence_turn(cue.to_dict()):
            r = build_social_presence_reply(msg, cue.to_dict(), ctx) or ""
            replies.append(r)
            if "sou a" in r.lower() and "aurora" in r.lower():
                brochure += 1
            continue
        if cue.rewrite_for_pipeline:
            msg = cue.rewrite_for_pipeline
        thought = reason(msg, ctx)
        attach_reasoning(ctx, thought)
        run_intelligence(msg, ctx)
        plan = plan_response(msg, ctx)
        refined = refine_crl_reply(plan.reply_text, ctx) or plan.reply_text or ""
        replies.append(refined)
        if refined.lower().startswith("olá!") or "sou a **aurora**" in refined.lower():
            brochure += 1

    assert len(script) >= 30
    assert len(replies) >= 30
    assert brochure == 0
    # Memory still on Bahia for sports turns
    assert (ctx.get("conversation_state") or {}).get("active_fixture") == "Bahia x Chapecoense"
    openers = [r[:30].lower() for r in replies if r]
    assert len(set(openers)) >= 10
