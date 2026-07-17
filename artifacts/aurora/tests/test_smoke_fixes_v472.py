"""Aurora v4.7.2 — smoke fixes: emotional hard-guard, greeting once, profile SoT."""

from __future__ import annotations

from src.conversation.emotional_presence import (
    detect_emotional_intent,
    enforce_emotional_hard_guard,
    is_banned_pitch,
    try_emotional_presence,
)
from src.conversation.user_profile_memory import (
    GREETING_SENT_KEY,
    PROFILE_KEY,
    consume_greeting_prefix,
    detect_profile_query,
    get_profile,
    save_profile,
    try_profile_commands,
)
from src.conversation.natural_conversation import build_team_opinion_reply
from src.conversation.web_intelligence import decide_need_web
from src.core.conversation_llm import needs_llm


_PITCH = "Posso ajudar com leituras de partidas e mercados.\nQual confronto você gostaria de observar?"


def test_emotional_phrases_detect_including_maior():
    assert detect_emotional_intent("tenho orgulho de você") == "pride"
    assert detect_emotional_intent("você é minha maior criação") == "pride"
    assert detect_emotional_intent("você é minha melhor criação") == "pride"
    assert detect_emotional_intent("obrigado aurora") == "thanks_named"


def test_emotional_never_returns_leituras_pitch():
    for msg in (
        "tenho orgulho de você",
        "você é minha maior criação",
        "obrigado aurora",
    ):
        p = try_emotional_presence(msg, {}, {"emojis": "none"})
        assert p is not None
        text = p.get("executive_summary") or ""
        assert not is_banned_pitch(text)
        assert "leituras" not in text.lower()
        assert "posso ajudar com" not in text.lower()
        assert p["entities"].get("skip_llm") is True


def test_emotional_hard_guard_restores_after_llm_pitch():
    poisoned = {
        "intent": "emotional",
        "entities": {"emotional": True, "emotional_kind": "pride"},
        "executive_summary": _PITCH,
        "final_recommendation": _PITCH,
        "best_markets": [{"market": "x"}],
    }
    out = enforce_emotional_hard_guard(
        poisoned,
        message="tenho orgulho de você",
        ctx={},
    )
    assert not is_banned_pitch(out["executive_summary"])
    assert "leituras" not in (out["executive_summary"] or "").lower()
    assert out["best_markets"] == []
    assert out["intent"] == "emotional"


def test_needs_llm_false_for_emotional_and_small_talk():
    assert needs_llm("emotional", "tenho orgulho de voce", {}) is False
    assert needs_llm("small_talk", "oi", {}) is False
    assert needs_llm("capabilities", "o que voce faz", {}) is False


def test_greeting_once_per_session():
    ctx = {PROFILE_KEY: {"name": "Achiro", "role": "", "favorite_team": "Botafogo", "project": "Aurora"}}
    g1 = consume_greeting_prefix(ctx, social_intents=["GREETING"])
    assert g1 and "Achiro" in g1
    assert ctx.get(GREETING_SENT_KEY) is True
    g2 = consume_greeting_prefix(ctx, social_intents=["GREETING"])
    assert g2 is None
    # wellbeing / farewell must not greet even on fresh ctx flag cleared wrongly
    ctx2 = {PROFILE_KEY: dict(ctx[PROFILE_KEY])}
    assert consume_greeting_prefix(ctx2, social_intents=["FAREWELL"]) is None
    assert consume_greeting_prefix(ctx2, social_intents=["WELLBEING"]) is None
    # greeting still available once
    g3 = consume_greeting_prefix(ctx2, social_intents=["GREETING"])
    assert g3 and "Achiro" in g3


def test_profile_query_name_and_team_from_sot():
    ctx = {}
    save_profile(ctx, {"name": "Achiro", "favorite_team": "Botafogo", "project": "Aurora"})
    assert detect_profile_query("qual meu nome?") == "name"
    # Accent-safe: folded form of "torço" is "torco"
    assert detect_profile_query("para qual time eu torco?") == "team"
    assert detect_profile_query("para qual time eu tor\u00e7o?") == "team"
    p_name = try_profile_commands("qual meu nome?", ctx)
    assert p_name and "Achiro" in (p_name.get("executive_summary") or "")
    p_team = try_profile_commands("para qual time eu tor\u00e7o?", ctx)
    assert p_team and "Botafogo" in (p_team.get("executive_summary") or "")
    assert get_profile(ctx)["project"] == "Aurora"


def test_football_opinion_more_complete():
    reply = build_team_opinion_reply("Botafogo")
    assert len(reply) > 280
    assert "Botafogo" in reply or "Fogão" in reply
    assert reply.count("\n\n") >= 1
    assert "probabilidade" not in reply.lower()


def test_need_web_still_decides_for_opinions():
    d = decide_need_web(
        "o que acha do Botafogo?",
        entities={"natural_kind": "team_opinion", "team": "Botafogo", "opinion_time": True},
    )
    assert d.need == "optional"
    d2 = decide_need_web("analise Bahia x Flamengo", intent="analyze_match")
    assert d2.need == "none"
    d3 = decide_need_web("o que achou da Copa de 2026?")
    assert d3.need == "required"
