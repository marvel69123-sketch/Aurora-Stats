"""Aurora v4.5 — Deep Reasoning + Memory Foundation tests."""

from __future__ import annotations

from src.conversation.context_reinforcement import reinforce_context
from src.conversation.conversation_intelligence_layer import refine_crl_reply, run_intelligence
from src.conversation.conversation_reasoner import attach_reasoning, reason
from src.conversation.conversation_response_layer import plan_response
from src.conversation.conversation_state import apply_after_analysis, get_state
from src.conversation.conversational_understanding import understand
from src.conversation.deep_reasoning import run_deep_reasoning
from src.conversation.human_presence import (
    build_presence_payload,
    build_social_presence_reply,
    is_social_presence_turn,
)
from src.conversation.prediction_memory import (
    get_experience,
    get_market_history,
    get_team_history,
    init_prediction_memory,
    maybe_store_from_turn,
    resolve_prediction,
    save_prediction,
    save_reasoning,
)
from src.conversation.reflection_credibility import apply_credibility_to_payload
import src.conversation.prediction_memory as pred_mem


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
            "risk": {"level": "Medium"},
        },
    )
    ctx["last_match"] = "Bahia x Chapecoense"
    return ctx


def _pipeline(msg: str, ctx: dict) -> tuple[str, dict]:
    reinforce_context(ctx, msg)
    cue = understand(msg, ctx)
    if is_social_presence_turn(cue.to_dict()):
        r = build_social_presence_reply(msg, cue.to_dict(), ctx) or ""
        payload = build_presence_payload(r, {})
        refl = run_deep_reasoning(msg, ctx, r)
        payload = apply_credibility_to_payload(payload, refl, ctx)
        return str(payload.get("executive_summary") or r), payload

    thought = reason(msg, ctx)
    attach_reasoning(ctx, thought)
    run_intelligence(msg, ctx)
    plan = plan_response(msg, ctx)
    refined = refine_crl_reply(plan.reply_text, ctx) or plan.reply_text or ""
    refl = run_deep_reasoning(msg, ctx, refined)
    if refl.chosen_answer:
        refined = refl.chosen_answer
    payload = {
        "intent": "conversation_assist",
        "entities": {"cil": True},
        "best_markets": [],
        "match_card": None,
        "executive_summary": refined,
        "final_recommendation": refined,
        "confidence": {
            "score": 0.0,
            "label": "insufficient",
            "explanation": "",
            "data_sources": [],
        },
        "risk": {"level": "Unknown", "flags": [], "invalidation_conditions": []},
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0,
            "method": "quarter-Kelly",
            "examples": {},
            "no_bet": True,
            "reasoning": "",
        },
        "positive_factors": [],
        "negative_factors": [],
        "historical_references": [],
        "knowledge_notes": [],
        "response_metadata": {"crl_mode": plan.mode},
    }
    payload = apply_credibility_to_payload(payload, refl, ctx)
    maybe_store_from_turn(
        message=msg,
        payload=payload,
        ctx=ctx,
        session_id="test-v45",
        reflection=ctx.get("conversation_reflection")
        if isinstance(ctx.get("conversation_reflection"), dict)
        else None,
    )
    return refined, payload


def test_vale_a_pena_has_depth_sections():
    ctx = _seed()
    reply, payload = _pipeline("vale a pena?", ctx)
    low = reply.lower()
    assert (
        "positiva" in low
        or "positivo" in low
        or "cautel" in low
        or "inclina" in low
        or "meio-termo" in low
        or "meio termo" in low
    )
    assert "favorece" in low or "chama" in low or "pontos a favor" in low or "pesa" in low or "sustenta" in low or "positivo" in low
    assert "receio" in low or "preocup" in low or "incomoda" in low or "cautela" in low or "desconfort" in low
    assert "se " in low  # scenarios
    assert "risco" in low or "conservador" in low or "reduzir" in low or "empate anula" in low
    deep = ctx.get("deep_reflection") or {}
    assert deep.get("final_position")
    assert deep.get("risk_scenarios")
    assert deep.get("what_would_change_my_opinion")
    assert "mercado em foco" not in low
    assert "na logica atual" not in low and "na lógica atual" not in low


def test_scenarios_mention_conditional_paths():
    ctx = _seed()
    reply, _ = _pipeline("vale a pena?", ctx)
    low = reply.lower()
    assert "marcar cedo" in low or "truncad" in low or "expuls" in low


def test_context_reinforcement_keeps_fixture():
    ctx = _seed()
    out = reinforce_context(ctx, "vale a pena?")
    assert out["active_fixture"] == "Bahia x Chapecoense"
    assert out["fixture_score"] >= 0.45
    assert ctx.get("last_match") == "Bahia x Chapecoense"
    # deixis boost
    out2 = reinforce_context(ctx, "e esse jogo?")
    assert out2["fixture_score"] >= out["fixture_score"]


def test_prediction_memory_passive_roundtrip(tmp_path, monkeypatch):
    db = tmp_path / "pred_exp_test.db"
    monkeypatch.setattr(pred_mem, "DB_PATH", db)
    monkeypatch.setattr(pred_mem, "_INITIALIZED", False)
    init_prediction_memory()
    pid = save_prediction(
        fixture="Bahia x Chapecoense",
        market="Mais de 8.5 Escanteios",
        recommendation="Mais de 8.5 Escanteios",
        confidence=6.5,
        reasoning_summary="teste profundo",
        home="Bahia",
        away="Chapecoense",
        session_id="s1",
    )
    assert pid
    hist = get_market_history("Mais de 8.5 Escanteios")
    assert any(h.get("prediction_id") == pid for h in hist)
    teams = get_team_history("Bahia")
    assert teams
    exp = get_experience("Bahia", "team")
    assert exp and int(exp["times_seen"]) >= 1
    assert resolve_prediction(pid, result="win", status="resolved")
    rid = save_reasoning(
        fixture="Bahia x Chapecoense",
        market="Mais de 8.5 Escanteios",
        reasoning_summary="só raciocínio",
    )
    assert rid


def test_social_still_clean():
    ctx = {}
    reply, payload = _pipeline("oi tudo bem?", ctx)
    cred = (payload.get("response_metadata") or {}).get("credibility") or {}
    assert cred.get("display_mode") == "SOCIAL"
    assert "favorece:" not in reply.lower()


def test_long_conversation_depth_and_memory():
    ctx = _seed()
    script = [
        "vale a pena?",
        "por que?",
        "algo mais conservador?",
        "o que mais te preocupa?",
        "oq acha?",
        "vale a pena?",
        "por que?",
        "algo mais conservador?",
        "o que mais te preocupa?",
        "oq acha?",
    ]
    depth_hits = 0
    for msg in script:
        reply, _ = _pipeline(msg, ctx)
        low = reply.lower()
        if "favorece" in low or "receio" in low or "cenário" in low or "cenario" in low or "se " in low:
            depth_hits += 1
    assert depth_hits >= 6
    # Context still anchored
    st = get_state(ctx)
    assert "Bahia" in str(st.get("active_fixture") or ctx.get("last_match") or "")
