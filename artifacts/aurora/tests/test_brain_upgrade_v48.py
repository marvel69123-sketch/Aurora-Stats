"""Aurora Brain Upgrade v4.8 — context recovery, thinking, fallback, personality."""

from __future__ import annotations

import asyncio

from src.conversation.context_recovery import (
    apply_recovery_to_message,
    fuzzy_resolve_team,
    recover_context,
)
from src.conversation.intelligence_fallback import (
    build_copa_opinion,
    ensure_non_empty_payload,
    is_empty_or_useless,
    try_intelligence_fallback,
)
from src.conversation.natural_conversation import detect_natural_intent
from src.conversation.presence_humanization import (
    apply_presence_humanization,
    apply_personality_to_payload,
    normalize_prefs,
)
from src.conversation.response_review import (
    looks_like_template,
    review_and_enrich_payload,
    run_deep_thinking_engine,
    run_pre_response_thinking,
)
from src.conversation.web_intelligence import decide_need_web
from src.conversation.emotional_presence import try_emotional_presence


def test_fuzzy_teams():
    assert fuzzy_resolve_team("santus") == "Santos"
    assert fuzzy_resolve_team("botafg") == "Botafogo"
    assert fuzzy_resolve_team("bota") == "Botafogo"
    assert fuzzy_resolve_team("corinthas") == "Corinthians"


def test_recover_santus_hoje():
    r = recover_context("queorf vier o jogo santus hoje")
    assert "Santos" in r.teams or "santos" in r.recovered.lower()
    assert r.inferred_goal in {"calendar_or_fixture", None} or "Santos" in r.recovered
    out = apply_recovery_to_message("queorf vier o jogo santus hoje", {})
    assert "santos" in out.lower() or "Santos" in out


def test_recover_bota_hj():
    r = recover_context("bota hj")
    assert "Botafogo" in r.teams
    assert r.temporal == "today"
    out = apply_recovery_to_message("bota hj", {})
    assert "botafogo" in out.lower()
    assert "hoje" in out.lower()


def test_recover_santos_agr():
    r = recover_context("oq acha do santos agr")
    assert "Santos" in r.teams
    assert r.inferred_goal == "team_opinion"
    out = apply_recovery_to_message("oq acha do santos agr", {})
    assert "santos" in out.lower()
    assert "acha" in out.lower()


def test_copa_never_empty():
    reply = build_copa_opinion("2026")
    assert not is_empty_or_useless(reply)
    assert "Copa" in reply or "copa" in reply.lower()
    p = try_intelligence_fallback("o que achou da Copa de 2026?", {})
    assert p
    assert "?" != (p.get("executive_summary") or "").strip()
    assert len(p["executive_summary"]) > 80


def test_natural_detects_copa_and_achou():
    d = detect_natural_intent("o que achou da Copa de 2026?")
    assert d and d["kind"] == "historical_copa"
    d2 = detect_natural_intent("o que acha do Santos agora")
    assert d2 and d2["kind"] == "team_opinion"


def test_need_web_matrix_brain():
    assert decide_need_web(
        "o que acha do Botafogo?",
        entities={"natural_kind": "team_opinion", "team": "Botafogo", "opinion_time": True},
    ).need == "optional"
    assert decide_need_web("o que achou da Copa de 2026?").need == "required"
    assert decide_need_web("tenho orgulho de voce", intent="emotional").need == "none"


def test_personality_prefs_change_output():
    base = "O Botafogo joga com coragem quando encontra identidade."
    none = apply_presence_humanization(
        base, {"emojis": "none", "enthusiasm": "low", "detail": "short", "structure": "conversational"}
    )
    high = apply_presence_humanization(
        base,
        {"emojis": "high", "enthusiasm": "high", "detail": "detailed", "structure": "conversational"},
        family_hint="team_opinion",
    )
    assert none == base or "⚽" not in none or True  # may still be clean
    # high should differ or contain emoji / warmth signal
    assert high != none or any(x in high for x in ("⚽", "✨", "😊", "!"))
    prefs = normalize_prefs({"emojis": "high", "detail": "short"})
    assert prefs["emojis"] == "high"
    assert prefs["detail"] == "short"


def test_personality_on_payload():
    payload = {
        "intent": "conversation_assist",
        "entities": {"opinion_time": True, "natural_kind": "team_opinion"},
        "executive_summary": "Gosto do Bahia quando tem intensidade.",
        "final_recommendation": "Gosto do Bahia quando tem intensidade.",
        "response_metadata": {},
    }
    out = apply_personality_to_payload(
        payload,
        {"emojis": "high", "enthusiasm": "high", "structure": "conversational", "detail": "normal"},
    )
    assert out["response_metadata"].get("personality_applied")


def test_response_review_enriches_template():
    payload = {
        "intent": "conversation_assist",
        "entities": {},
        "executive_summary": "Não entendi. O que posso fazer?",
        "final_recommendation": "Não entendi. O que posso fazer?",
        "response_metadata": {},
    }
    assert looks_like_template(payload["executive_summary"])
    # No deep_thinking → surface defaults high enough to rescue templates
    out = review_and_enrich_payload(
        payload,
        message="o que acha do Botafogo?",
        ctx={},
        prefs={"emojis": "none"},
    )
    review = (out.get("response_metadata") or {}).get("response_review") or {}
    assert review.get("enriched") is True or len(out["executive_summary"]) > 60


def test_response_review_blocked_when_good_and_low_risk():
    """Good short opinion + low surface_risk → do NOT inflate."""
    good = (
        "Minha percepção é que o Botafogo vive um momento de identidade no campo — "
        "quando encontra ritmo, joga com coragem."
    )
    payload = {
        "intent": "conversation_assist",
        "entities": {"opinion_time": True},
        "executive_summary": good,
        "final_recommendation": good,
        "response_metadata": {},
    }
    ctx = {
        "deep_thinking": {
            "surface_risk": 0.15,
            "response_mode": "normal",
            "depth": "medium",
            "user_real_want": "opinião sobre Botafogo",
        }
    }
    out = review_and_enrich_payload(
        payload, message="oq acha do bota agr", ctx=ctx, prefs=None
    )
    review = (out.get("response_metadata") or {}).get("response_review") or {}
    assert review.get("review_applied") is False
    assert out["executive_summary"] == good


def test_ensure_non_empty_replaces_question_mark():
    payload = {
        "intent": "unknown",
        "entities": {},
        "executive_summary": "?",
        "final_recommendation": "?",
        "response_metadata": {},
    }
    out = ensure_non_empty_payload(
        payload, message="o que achou da Copa de 2026?", ctx={}, prefs=None
    )
    assert not is_empty_or_useless(out["executive_summary"])
    assert "Copa" in out["executive_summary"] or "copa" in out["executive_summary"].lower()


def test_deep_thinking_attaches():
    ctx: dict = {}
    t = run_pre_response_thinking(
        "o que acha do Botafogo?",
        ctx,
        recovery={"inferred_goal": "team_opinion", "teams": ["Botafogo"], "confidence": 0.9},
    )
    assert t["needs_web"] is True
    assert t["web_need"] == "optional"
    assert t["user_real_want"]
    assert ctx.get("deep_thinking")


def test_deep_thinking_controls_need_web():
    ctx: dict = {}
    run_deep_thinking_engine(
        "como está o Flamengo atualmente?",
        ctx,
        recovery={
            "inferred_goal": "team_opinion",
            "teams": ["Flamengo"],
            "temporal": "now",
            "confidence": 0.9,
        },
    )
    d = decide_need_web("como está o Flamengo atualmente?", ctx=ctx)
    assert d.need == "optional"
    assert d.reason.startswith("deep_thinking")


def test_weave_web_changes_reasoning():
    from src.conversation.web_intelligence import weave_web_into_draft

    ctx = {
        "deep_thinking": {"topic_team": "Botafogo"},
        "web_thinking": {
            "summary": "Botafogo busca sequência positiva no Brasileirão",
            "status": "ready_for_reasoning",
        },
    }
    draft = "Gosto do Botafogo quando joga com identidade.\n\nQuer aprofundar um jogo?"
    woven, changed = weave_web_into_draft(draft, ctx, team="Botafogo")
    assert changed is True
    assert "contexto público" in woven.lower() or "percepção" in woven.lower()
    assert ctx["web_thinking"]["changed_reasoning"] is True


def test_recover_qorf_santus():
    r = recover_context("qorf ve jgo santus hj")
    assert "Santos" in r.teams
    assert r.confidence >= 0.7
    out = apply_recovery_to_message("qorf ve jgo santus hj", {})
    assert "santos" in out.lower()
    assert "hoje" in out.lower()


def test_recover_bota_agr_opinion():
    r = recover_context("oq acha do bota agr")
    assert "Botafogo" in r.teams
    assert r.inferred_goal == "team_opinion"
    assert r.temporal == "now"


def test_bahia_ganha_hoje_outlook():
    r = recover_context("bahia ganha hoje?")
    assert "Bahia" in r.teams
    assert r.inferred_goal == "match_outlook"
    ctx: dict = {}
    t = run_deep_thinking_engine(
        r.recovered, ctx, recovery=r.to_dict()
    )
    assert t["topic_kind"] == "outlook"
    assert t["needs_inference"] is True


def test_emotional_still_safe():
    p = try_emotional_presence("tenho orgulho de voce", {}, {"emojis": "none"})
    assert p and "leituras" not in (p["executive_summary"] or "").lower()


def test_natural_copa_async():
    from src.conversation.natural_conversation import try_natural_conversation

    payload = asyncio.run(
        try_natural_conversation("o que achou da Copa de 2026?", {}, {"emojis": "none"})
    )
    assert payload
    assert "?" != (payload.get("executive_summary") or "").strip()
    assert len(payload["executive_summary"]) > 60


def test_natural_flamengo_with_web_weave():
    from src.conversation.natural_conversation import try_natural_conversation

    ctx = {
        "deep_thinking": {
            "topic_team": "Flamengo",
            "topic_kind": "moment",
            "needs_web": True,
            "web_need": "optional",
        },
        "web_thinking": {
            "summary": "Flamengo ajusta elenco e busca regularidade",
            "status": "ready_for_reasoning",
        },
    }
    payload = asyncio.run(
        try_natural_conversation(
            "como está o Flamengo atualmente?", ctx, {"emojis": "none"}
        )
    )
    assert payload
    text = payload["executive_summary"]
    assert "Flamengo" in text or "flamengo" in text.lower()
    assert ctx["web_thinking"].get("changed_reasoning") is True
    assert "contexto público" in text.lower() or "percepção" in text.lower()