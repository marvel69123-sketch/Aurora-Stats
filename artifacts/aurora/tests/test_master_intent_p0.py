"""P0 Communication & Intent Recovery — mandatory smoke tests."""

from __future__ import annotations

import re

from src.conversation.general_assistant import try_general_assistant
from src.conversation.human_inference import _resolve_team, infer_human_intent
from src.conversation.master_intent_router import (
    apply_master_intent,
    classify_master_intent,
    sport_pipeline_allowed,
)
from src.conversation.natural_response_filter import (
    looks_artificial_sport_voice,
    score_perceived_intelligence,
)


SPORT_LEAK = re.compile(
    r"(Corinthians|Santos|Flamengo|Botafogo|panorama|Momento atual|mercado)",
    re.I,
)


def test_small_talk_not_sport():
    r = classify_master_intent("oi aurora tudo bem?")
    assert r.intent == "SMALL_TALK"
    assert r.allow_sport_pipeline is False
    ctx: dict = {"conversation_focus": {"topic_team": "Corinthians"}}
    apply_master_intent("oi aurora tudo bem?", ctx)
    assert sport_pipeline_allowed(ctx) is False
    p = try_general_assistant("oi aurora tudo bem?", "SMALL_TALK", ctx)
    assert p is not None
    text = p["executive_summary"]
    assert not SPORT_LEAK.search(text)
    assert "Aurora" in text or "bem" in text.lower()


def test_math_is_four():
    r = classify_master_intent("quanto é 2+2?")
    assert r.intent == "MATH_QUERY"
    assert r.allow_sport_pipeline is False
    p = try_general_assistant("quanto é 2+2?", "MATH_QUERY", {})
    assert p is not None
    assert p["executive_summary"].strip() == "4"
    assert not SPORT_LEAK.search(p["executive_summary"])


def test_name_is_aurora():
    r = classify_master_intent("qual seu nome?")
    assert r.intent == "SYSTEM_QUERY"
    p = try_general_assistant("qual seu nome?", "SYSTEM_QUERY", {})
    assert p is not None
    assert "Aurora" in p["executive_summary"]
    assert not SPORT_LEAK.search(p["executive_summary"])


def test_live_match_allows_sport():
    r = classify_master_intent("São Bernardo x Ivaí ao vivo")
    assert r.intent == "LIVE_MATCH"
    assert r.allow_sport_pipeline is True
    ctx: dict = {}
    apply_master_intent("São Bernardo x Ivaí ao vivo", ctx)
    assert sport_pipeline_allowed(ctx) is True


def test_resolve_team_no_greeting_invent():
    assert _resolve_team("Oi Aurora Tudo Bem") is None
    assert _resolve_team("Qual Seu Nome") is None
    assert _resolve_team("quanto é 2+2") is None


def test_hie_soft_keep_blocked_on_nonsport():
    ctx = {
        "sport_pipeline_blocked": True,
        "master_intent": {"allow_sport_pipeline": False, "intent": "SMALL_TALK"},
        "conversation_focus": {"topic_team": "Santos", "topic_kind": "opinion"},
    }
    inf = infer_human_intent("oi", ctx)
    assert inf.team is None or inf.intent == "general_chat"


def test_artificial_phrases_blocked():
    bad = "Com o contexto atual, o útil é olhar o Santos."
    assert looks_artificial_sport_voice(bad)
    score = score_perceived_intelligence(bad, master_intent="SMALL_TALK")
    assert score.ok is False


def test_mixed_50_zero_contamination():
    """50 turns mixing small talk / math / memory / sport — intent gate only."""
    turns = (
        ["oi", "tudo bem?", "qual seu nome?", "quanto é 2+2?", "quem te criou?"]
        + ["Flamengo", "analisar Arsenal x Chelsea", "São Bernardo x Ivaí ao vivo"]
        * 5
        + ["boa noite", "10/2", "o que você faz?", "blz", "hey aurora"]
        + ["como está o Botafogo?", "Santos x Corinthians"] * 5
        + ["obrigado", "tchau"]
    )
    turns = (turns * 3)[:50]
    ctx: dict = {}
    leaks = 0
    for msg in turns:
        r = apply_master_intent(msg, ctx)
        if not r.allow_sport_pipeline:
            assert sport_pipeline_allowed(ctx) is False
            p = try_general_assistant(msg, r.intent, ctx)
            if p:
                if SPORT_LEAK.search(str(p.get("executive_summary") or "")):
                    leaks += 1
            # Must not keep sticky sport focus active for pipeline
            assert ctx.get("sport_pipeline_blocked") is True
        else:
            assert r.intent in {"SPORT_QUERY", "LIVE_MATCH"}
    assert leaks == 0
