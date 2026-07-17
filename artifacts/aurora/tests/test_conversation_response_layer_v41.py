"""Aurora v4.1 Sprint 2 — Conversational Response Layer tests."""

from __future__ import annotations

from src.communication.small_talk import try_small_talk
from src.conversation.conversation_reasoner import attach_reasoning, reason
from src.conversation.conversation_response_layer import (
    apply_crl_payload,
    decide_response_mode,
    plan_response,
)
from src.conversation.conversation_state import apply_after_analysis, note_pending_team, note_small_talk


def _seed(ctx: dict | None = None) -> dict:
    ctx = dict(ctx or {})
    apply_after_analysis(
        ctx,
        "Botafogo",
        "Santos",
        "Botafogo x Santos",
        {
            "best_markets": [
                {"market": "Mais de 8.5 Escanteios", "risk": "high", "rank": 1}
            ],
            "risk": {"level": "High"},
            "final_recommendation": "Mais de 8.5 Escanteios com stake reduzida",
        },
    )
    ctx["last_home"] = "Botafogo"
    ctx["last_away"] = "Santos"
    ctx["last_match"] = "Botafogo x Santos"
    ctx["last_recommendation"] = "Mais de 8.5 Escanteios com stake reduzida"
    return ctx


def _reason_and_plan(message: str, ctx: dict):
    thought = reason(message, ctx)
    attach_reasoning(ctx, thought)
    plan = plan_response(message, ctx)
    return thought, plan


def _assert_not_full_report(payload: dict):
    assert payload["best_markets"] == []
    assert payload.get("match_card") is None
    assert payload.get("entities", {}).get("show_header") is False
    text = (payload.get("executive_summary") or "") + (payload.get("final_recommendation") or "")
    # Must not look like a regenerated multi-section report dump
    assert "best_markets" not in text.lower()
    assert len(text) < 900


# ── Scenario 1: e escanteios? → conversational, no full report ─────────────

def test_scenario1_corners_followup_not_full_report():
    ctx = _seed()
    thought, plan = _reason_and_plan("e escanteios?", ctx)
    assert thought.reasoning_type == "FOLLOWUP_MARKET"
    assert plan.mode == "CONVERSATIONAL_REPLY"
    assert plan.should_short_circuit is True
    assert plan.show_header is False
    assert plan.reply_text
    assert "escanteio" in plan.reply_text.lower() or "canto" in plan.reply_text.lower()
    payload = apply_crl_payload(plan, {})
    assert payload is not None
    _assert_not_full_report(payload)


# ── Scenario 2: não gostei → alternative ───────────────────────────────────

def test_scenario2_nao_gostei_alternative():
    ctx = _seed()
    _, plan = _reason_and_plan("não gostei", ctx)
    assert plan.mode == "ALTERNATIVE_REPLY"
    assert plan.should_short_circuit is True
    assert "Entendi" in (plan.reply_text or "")
    assert "•" in (plan.reply_text or "")
    payload = apply_crl_payload(plan, {})
    _assert_not_full_report(payload)


# ── Scenario 3: qual parece melhor? → comparison from memory ───────────────

def test_scenario3_comparison_uses_memory():
    ctx = _seed()
    apply_after_analysis(
        ctx,
        "Vitoria",
        "Vasco",
        "Vitoria x Vasco",
        {
            "best_markets": [{"market": "Over 2.5 Goals", "risk": "medium"}],
            "final_recommendation": "Over 2.5",
        },
    )
    _, plan = _reason_and_plan("qual parece melhor?", ctx)
    assert plan.mode == "COMPARISON_REPLY"
    assert plan.should_short_circuit is True
    text = plan.reply_text or ""
    assert "Vitoria x Vasco" in text or "Vitória" in text or "Vitoria" in text
    assert "Botafogo" in text
    payload = apply_crl_payload(plan, {})
    _assert_not_full_report(payload)


# ── Scenario 4: por que? → explanation ─────────────────────────────────────

def test_scenario4_por_que_explanation():
    ctx = _seed()
    _, plan = _reason_and_plan("por que?", ctx)
    assert plan.mode == "EXPLANATION_REPLY"
    assert plan.should_short_circuit is True
    assert "Porque" in (plan.reply_text or "") or "porque" in (plan.reply_text or "").lower()
    payload = apply_crl_payload(plan, {})
    _assert_not_full_report(payload)


# ── Scenario 5: boa noite then e gols? keeps sports context ────────────────

def test_scenario5_small_talk_then_goals_remembers():
    ctx = _seed()
    social = try_small_talk("boa noite", {})
    assert social is not None
    note_small_talk(ctx)
    assert ctx.get("conversation_state", {}).get("active_fixture") == "Botafogo x Santos"

    _, plan = _reason_and_plan("e gols?", ctx)
    assert plan.mode == "CONVERSATIONAL_REPLY"
    assert plan.should_short_circuit is True
    assert "gol" in (plan.reply_text or "").lower() or "Botafogo" in (plan.reply_text or "")
    payload = apply_crl_payload(plan, {})
    _assert_not_full_report(payload)


# ── Scenario 6: fala do fla → oq acha desse jogo? never invent ─────────────

def test_scenario6_fla_chain_keeps_asking_opponent():
    ctx: dict = {}
    t1, p1 = _reason_and_plan("fala do fla", ctx)
    assert t1.next_action == "ASK_OPPONENT"
    assert p1.mode == "CONVERSATIONAL_REPLY"
    assert "adversário" in (p1.reply_text or "").lower() or "adversario" in (p1.reply_text or "").lower()
    assert " x " not in (p1.reply_text or "").split("ex.:")[0] or "invent" in (p1.reply_text or "").lower()

    note_pending_team(ctx, "Flamengo")
    t2, p2 = _reason_and_plan("oq acha desse jogo?", ctx)
    assert t2.next_action == "ASK_OPPONENT"
    assert p2.should_short_circuit is True
    assert "Flamengo" in (p2.reply_text or "") or "adversário" in (p2.reply_text or "").lower()
    # Must not invent a concrete Flamengo x Opponent fixture as fact
    assert "Flamengo x Palmeiras" not in (p2.reply_text or "")
    assert "Flamengo x Vasco" not in (p2.reply_text or "")


def test_full_analysis_for_explicit_analyze():
    ctx = {}
    thought = reason("analise Botafogo x Santos", ctx)
    attach_reasoning(ctx, thought)
    plan = plan_response("analise Botafogo x Santos", ctx)
    assert plan.mode == "FULL_ANALYSIS"
    assert plan.should_short_circuit is False
    assert plan.show_header is True


def test_decide_mode_consumes_last_reasoning_only():
    ctx = _seed()
    thought = reason("vale a pena?", ctx)
    attach_reasoning(ctx, thought)
    mode = decide_response_mode("vale a pena?", ctx)
    assert mode == "ALTERNATIVE_REPLY"
