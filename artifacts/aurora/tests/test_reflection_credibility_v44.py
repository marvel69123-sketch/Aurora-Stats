"""Aurora v4.4 — Reflection + Credibility Layer tests."""

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
from src.conversation.reflection_credibility import (
    apply_credibility_to_payload,
    humanize_jargon,
    reflect_and_apply,
    run_reflection,
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


def _pipeline_reply(msg: str, ctx: dict) -> tuple[str, dict]:
    cue = understand(msg, ctx)
    if is_social_presence_turn(cue.to_dict()):
        r = build_social_presence_reply(msg, cue.to_dict(), ctx) or ""
        payload = build_presence_payload(r, {})
        payload = reflect_and_apply(msg, payload, ctx, r)
        return str(payload.get("executive_summary") or r), payload

    thought = reason(msg, ctx)
    attach_reasoning(ctx, thought)
    run_intelligence(msg, ctx)
    plan = plan_response(msg, ctx)
    refined = refine_crl_reply(plan.reply_text, ctx) or plan.reply_text or ""
    refl = run_reflection(msg, ctx, refined)
    if refl.chosen_answer:
        refined = refl.chosen_answer
    payload = {
        "intent": "conversation_assist",
        "entities": {"cil": True, "show_header": False},
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
        "response_metadata": {"crl_mode": plan.mode, "show_header": False},
    }
    payload = apply_credibility_to_payload(payload, refl, ctx)
    return str(payload.get("executive_summary") or ""), payload


# ── Test 1: vale a pena? — assume position ─────────────────────────────────

def test_1_vale_a_pena_takes_position():
    ctx = _seed()
    reply, payload = _pipeline_reply("vale a pena?", ctx)
    low = reply.lower()
    assert any(
        x in low
        for x in ("cautela", "sincera", "não me daria", "nao me daria", "confiança", "confianca")
    ), reply
    # Must take a clear yes/no-ish stance — not only "eu sairia"
    assert "cautela" in low or "sincera" in low
    cred = (payload.get("response_metadata") or {}).get("credibility") or {}
    assert cred.get("display_mode") in {"REASONING", "FOLLOW_UP"}
    assert cred.get("show_confidence") is False


# ── Test 2: por que? — explain factors / risks / scenarios ─────────────────

def test_2_por_que_explains():
    ctx = _seed()
    _pipeline_reply("vale a pena?", ctx)
    reply, _ = _pipeline_reply("por que?", ctx)
    low = reply.lower()
    assert any(x in low for x in ("fator", "risco", "cenário", "cenario", "pensa"))
    assert "quadro" not in low or "cenário" in low or "cenario" in low


# ── Test 3: algo mais conservador? — concrete suggestion ───────────────────

def test_3_conservative_concrete():
    ctx = _seed()
    reply, _ = _pipeline_reply("algo mais conservador?", ctx)
    low = reply.lower()
    assert "bahia" in low or "empate" in low or "under" in low or "linha" in low or "stake" in low
    assert "reduzir risco" in low or "conservador" in low or "tranquila" in low or "seguro" in low


# ── Test 4: o que mais te preocupa? — reasoning ────────────────────────────

def test_4_worry_reasoning():
    ctx = _seed()
    reply, payload = _pipeline_reply("o que mais te preocupa?", ctx)
    low = reply.lower()
    assert "ritmo" in low or "preocup" in low
    assert "travad" in low or "valor" in low or "olh" in low
    refl = (payload.get("response_metadata") or {}).get("reflection") or {}
    assert refl.get("user_real_intent") == "worry" or "ritmo" in low


# ── Test 5: oi tudo bem? — no analysis badges / SOCIAL mode ────────────────

def test_5_greeting_no_badges():
    ctx: dict = {}
    reply, payload = _pipeline_reply("oi tudo bem?", ctx)
    low = reply.lower()
    assert "sou a aurora" not in low
    cred = (payload.get("response_metadata") or {}).get("credibility") or {}
    assert cred.get("display_mode") == "SOCIAL"
    assert cred.get("show_confidence") is False
    assert cred.get("show_badges") is False
    assert cred.get("show_resumo_chrome") is False
    assert payload.get("best_markets") == []
    assert float((payload.get("confidence") or {}).get("score") or 0) == 0.0


# ── Test 6: obrigado — no confidence chrome ────────────────────────────────

def test_6_thanks_no_confidence():
    ctx: dict = {}
    reply, payload = _pipeline_reply("obrigado", ctx)
    assert reply
    cred = (payload.get("response_metadata") or {}).get("credibility") or {}
    assert cred.get("display_mode") == "SOCIAL"
    assert cred.get("show_confidence") is False
    assert "confiança moderada" not in reply.lower()


# ── Test 7: long conversation naturalness ──────────────────────────────────

def test_7_long_conversation_40_turns():
    ctx = _seed()
    script = [
        "oi tudo bem?",
        "vale a pena?",
        "por que?",
        "algo mais conservador?",
        "o que mais te preocupa?",
        "oq acha?",
        "e escanteios?",
        "qual parece melhor?",
        "não gostei",
        "algo mais agressivo?",
        "por que?",
        "vale a pena?",
        "obrigado",
        "e gols?",
        "oq acha?",
        "algo mais conservador?",
        "por que?",
        "o que mais te preocupa?",
        "boa noite",
        "oi",
        "vale a pena?",
        "por que?",
        "não gostei",
        "tem algo melhor?",
        "e cartões?",
        "oq acha?",
        "algo mais conservador?",
        "o que mais te preocupa?",
        "por que?",
        "vale a pena?",
        "obrigado",
        "e gols?",
        "qual parece melhor?",
        "não gostei",
        "algo mais agressivo?",
        "oq acha?",
        "por que?",
        "vale a pena?",
        "algo mais conservador?",
        "o que mais te preocupa?",
        "falou",
    ]
    assert len(script) >= 40
    replies: list[str] = []
    social_badges = 0
    brochure = 0
    positions = 0
    for msg in script:
        reply, payload = _pipeline_reply(msg, ctx)
        replies.append(reply)
        low = reply.lower()
        if "sou a" in low and "aurora" in low:
            brochure += 1
        cred = (payload.get("response_metadata") or {}).get("credibility") or {}
        if msg.strip().lower() in {"oi", "oi tudo bem?", "obrigado", "boa noite", "falou"}:
            if cred.get("display_mode") != "SOCIAL" or cred.get("show_badges") is not False:
                social_badges += 1
        if any(x in low for x in ("cautela", "sincera", "preocup", "reduzir risco")):
            positions += 1

    assert brochure == 0
    assert social_badges == 0
    assert positions >= 5
    assert len(replies) == len(script)
    # Repetition proxy: not all reflective replies identical
    reflective = [r for r in replies if "cautela" in r.lower() or "preocup" in r.lower()]
    if len(reflective) >= 3:
        assert len(set(reflective)) >= 2


def test_humanize_jargon_reduces_technical():
    raw = "Na minha leitura, o mercado em foco tem risco high no quadro."
    out = humanize_jargon(raw).lower()
    assert "na minha leitura" not in out
    assert "mercado em foco" not in out
    assert "risco high" not in out


def test_reflection_fail_open():
    # Empty ctx still returns a ReflectionResult
    r = run_reflection("vale a pena?", {}, None)
    assert r.user_real_intent
    assert r.display_mode in {"REASONING", "FOLLOW_UP", "SOCIAL", "FULL_ANALYSIS"}
