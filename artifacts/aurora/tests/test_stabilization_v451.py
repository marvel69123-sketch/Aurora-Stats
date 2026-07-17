"""Aurora v4.5.1 — stabilization tests (deep gaps, farewell, variation, memory TTL, E2E metadata)."""

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
from src.conversation.prediction_memory import purge_prediction_memory
from src.conversation.reflection_credibility import apply_credibility_to_payload
from src.conversation.response_variation_layer import scrub_banned
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
        "response_metadata": {"crl_mode": getattr(plan, "mode", None)},
    }
    payload = apply_credibility_to_payload(payload, refl, ctx)
    if ctx.get("deep_reflection"):
        meta = dict(payload.get("response_metadata") or {})
        meta["deep_reflection"] = ctx["deep_reflection"]
        payload["response_metadata"] = meta
    return refined, payload


def test_opinion_change_forced_deep():
    ctx = _seed()
    for msg in (
        "mudaria sua opiniao?",
        "o que faria voce mudar de ideia?",
        "o que invalidaria essa analise?",
        "o que te faria abandonar esse mercado?",
    ):
        reply, payload = _pipeline(msg, ctx)
        low = reply.lower()
        # Accept natural variants: "mudaria" / "mudar de ideia" / invalidation language
        assert (
            "mudaria" in low
            or "mudar" in low
            or "invalid" in low
            or "abandon" in low
            or "revisaria" in low
            or "caso" in low
            or "cenario" in low
            or "cenário" in low
        )
        assert "•" in reply or "-" in reply or "–" in reply or "\n" in reply
        assert any(x in low for x in ("truncad", "expuls", "intensidade", "odds", "valor"))
        deep = (payload.get("response_metadata") or {}).get("deep_reflection") or ctx.get("deep_reflection")
        assert deep
        assert deep.get("opinion_changers") or deep.get("what_would_change_my_opinion")
        cred = (payload.get("response_metadata") or {}).get("credibility") or {}
        assert cred.get("display_mode") in {"REASONING", "FOLLOW_UP"}
        assert "quadro" not in low


def test_aggressive_depth():
    ctx = _seed()
    reply, _ = _pipeline("algo mais agressivo?", ctx)
    low = reply.lower()
    assert "agressiv" in low or "risco" in low or "linha" in low or "stake" in low


def test_farewell_not_greeting():
    for msg in ("boa noite", "ate amanha", "falou aurora", "tenha uma boa noite", "obrigado"):
        ctx: dict = {}
        intent = understand(msg, ctx)
        social = intent.social_intents
        reply, payload = _pipeline(msg, ctx)
        low = reply.lower()
        cred = (payload.get("response_metadata") or {}).get("credibility") or {}
        assert cred.get("display_mode") == "SOCIAL"
        assert cred.get("show_badges") is False
        assert cred.get("show_confidence") is False
        if msg in {"boa noite", "ate amanha", "falou aurora", "tenha uma boa noite"}:
            assert "FAREWELL" in social or "THANKS" in social
            # Must not sound like a fresh hello opener for night/bye
            if "boa noite" in msg or "tenha uma boa noite" in msg:
                assert "boa noite" in low or "descans" in low or "ate" in low or "até" in low
            assert not (low.startswith("oi!") and "boa noite" in msg)


def test_banned_phrases_scrubbed():
    raw = "Na logica atual faz sentido continuar no mercado em foco."
    out = scrub_banned(raw).lower()
    assert "mercado em foco" not in out
    assert "na logica atual" not in out
    assert "faz sentido continuar" not in out


def test_memory_purge_limits(tmp_path, monkeypatch):
    db = tmp_path / "purge_test.db"
    monkeypatch.setattr(pred_mem, "DB_PATH", db)
    monkeypatch.setattr(pred_mem, "_INITIALIZED", False)
    pred_mem.init_prediction_memory()
    for i in range(12):
        pred_mem.save_prediction(
            fixture=f"Team{i} x Other",
            market="Over 2.5",
            recommendation="Over 2.5",
            reasoning_summary=f"r{i}",
        )
    stats = purge_prediction_memory(max_predictions=5, max_experience=1000, prediction_ttl_days=30)
    assert stats["trimmed"] >= 7
    hist = pred_mem.get_market_history("Over 2.5", limit=50)
    assert len(hist) <= 5


def test_e2e_metadata_contract_scenario1():
    """Layer E2E: State → Deep → Credibility → response_metadata (UI contract)."""
    ctx = _seed()
    script = [
        "vale a pena?",
        "por que?",
        "o que mais te preocupa?",
        "mudaria sua opiniao?",
        "o que invalidaria essa analise?",
        "algo mais conservador?",
        "algo mais agressivo?",
    ]
    for msg in script:
        reply, payload = _pipeline(msg, ctx)
        meta = payload.get("response_metadata") or {}
        cred = meta.get("credibility") or {}
        assert "display_mode" in cred
        assert cred.get("show_confidence") is False
        assert reply
        assert "sou a aurora" not in reply.lower()
        if "mudaria" in msg or "invalidaria" in msg:
            assert meta.get("deep_reflection") or ctx.get("deep_reflection")


def test_context_switch_four_teams():
    ctx = {}
    for home, away, label in (
        ("Flamengo", "Palmeiras", "Flamengo x Palmeiras"),
        ("Bahia", "Chapecoense", "Bahia x Chapecoense"),
        ("Santos", "Corinthians", "Santos x Corinthians"),
        ("Corinthians", "Sao Paulo", "Corinthians x Sao Paulo"),
    ):
        apply_after_analysis(
            ctx,
            home,
            away,
            label,
            {
                "best_markets": [{"market": "Mais de 2.5 Gols", "risk": "medium"}],
                "final_recommendation": "Mais de 2.5 Gols",
                "risk": {"level": "Medium"},
            },
        )
        reinforce_context(ctx, f"fale do {home}")
        assert get_state(ctx).get("active_fixture") == label
    # deixis keeps last
    reinforce_context(ctx, "e esse jogo?")
    assert "Corinthians" in str(get_state(ctx).get("active_fixture") or "")


def test_long_50_turns_stabilization():
    ctx = _seed()
    script = (
        ["oi", "vale a pena?", "por que?", "mudaria sua opiniao?", "o que invalidaria essa analise?"]
        + ["algo mais conservador?", "algo mais agressivo?", "o que mais te preocupa?", "oq acha?"]
        + ["obrigado", "tudo bem?", "boa noite", "oi", "vale a pena?", "por que?"]
        + ["nao gostei", "tem algo melhor?", "e gols?", "qual parece melhor?", "ate amanha"]
        + ["oi", "vale a pena?", "mudaria sua opiniao?", "algo mais conservador?", "falou aurora"]
        + ["tudo bem?", "por que?", "o que mais te preocupa?", "algo mais agressivo?", "obrigado"]
        + ["vale a pena?", "por que?", "mudaria sua opiniao?", "o que invalidaria essa analise?"]
        + ["algo mais conservador?", "boa noite", "oi", "vale a pena?", "por que?", "falou"]
        + ["oq acha?", "nao gostei", "tem algo melhor?", "ate amanha", "obrigado"]
        + ["vale a pena?", "por que?", "mudaria sua opiniao?", "algo mais agressivo?", "boa noite"]
    )
    assert len(script) >= 50
    replies = []
    brochure = 0
    social_bad = 0
    for msg in script:
        r, p = _pipeline(msg, ctx)
        replies.append(r)
        if "sou a" in r.lower() and "aurora" in r.lower():
            brochure += 1
        cred = (p.get("response_metadata") or {}).get("credibility") or {}
        if msg in {"oi", "tudo bem?", "obrigado", "boa noite", "ate amanha", "falou aurora", "falou"}:
            if cred.get("display_mode") != "SOCIAL":
                social_bad += 1
    assert brochure == 0
    assert social_bad == 0
    assert len(set(replies)) / len(replies) >= 0.3
    assert "Bahia" in str(get_state(ctx).get("active_fixture") or ctx.get("last_match") or "")
