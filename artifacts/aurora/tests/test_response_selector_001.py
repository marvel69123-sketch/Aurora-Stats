"""AURORA-RESPONSE-SELECTOR-001 — deterministic candidate selection tests."""

from __future__ import annotations

import os

from src.conversation.response_selector import (
    OWNER_OWNERSHIP,
    OWNER_SPORT_INTENT_SKILL,
    PRIORITY_SOFT_HOLD,
    PRIORITY_SPORT_INTENT_SKILL,
    ResponseCandidate,
    collect_early_candidates,
    generate_sport_intent_skill,
    payload_from_candidate,
    response_selector_enabled,
    select_response,
    try_select_early_response,
)
from src.conversation.sport_intent_layer import RECENT_FORM, apply_sport_intent_layer


def test_flag_default_on():
    os.environ.pop("ENABLE_RESPONSE_SELECTOR", None)
    assert response_selector_enabled() is True


def test_flag_off():
    os.environ["ENABLE_RESPONSE_SELECTOR"] = "0"
    try:
        assert response_selector_enabled() is False
        assert try_select_early_response("quem está melhor?", {}) is None
    finally:
        os.environ["ENABLE_RESPONSE_SELECTOR"] = "1"


def test_select_priority_beats_soft_hold():
    soft = ResponseCandidate(
        owner=OWNER_OWNERSHIP,
        text="Continuando sobre Flamengo x Palmeiras.",
        priority=PRIORITY_SOFT_HOLD,
        confidence=0.99,
        fallback=True,
    )
    skill = ResponseCandidate(
        owner=OWNER_SPORT_INTENT_SKILL,
        text="Comparando a fase recente de Flamengo e Palmeiras.",
        priority=PRIORITY_SPORT_INTENT_SKILL,
        confidence=0.80,
        fallback=False,
    )
    winner = select_response([soft, skill])
    assert winner is not None
    assert winner.owner == OWNER_SPORT_INTENT_SKILL


def test_select_skips_crumb_when_alternative():
    crumb = ResponseCandidate(
        owner="x", text="?", priority=99, confidence=1.0
    )
    ok = ResponseCandidate(
        owner="y", text="Resposta útil sobre o jogo.", priority=40, confidence=0.5
    )
    winner = select_response([crumb, ok])
    assert winner is not None
    assert winner.owner == "y"


def test_sport_intent_skill_authors_recent_form():
    os.environ["ENABLE_SPORT_INTENTS"] = "1"
    os.environ["ENABLE_RESPONSE_SELECTOR"] = "1"
    ctx = {
        "csl": {
            "teams": ["Flamengo", "Palmeiras"],
            "fixture": "Flamengo x Palmeiras",
            "topic": "comparison",
            "injected": True,
        },
        "last_match": "Flamengo x Palmeiras",
        "raw_user_message": "Quem está melhor?",
        "conversation_continuity": {
            "active": True,
            "turns_left": 3,
            "last_team": "Flamengo",
            "last_fixture": "Flamengo x Palmeiras",
        },
    }
    apply_sport_intent_layer("Quem está melhor?", ctx)
    cand = generate_sport_intent_skill("forma recente de Flamengo e Palmeiras", ctx)
    assert cand is not None
    assert cand.owner == OWNER_SPORT_INTENT_SKILL
    assert cand.priority == PRIORITY_SPORT_INTENT_SKILL
    assert "fase recente" in cand.text.lower() or "Flamengo" in cand.text
    payload = payload_from_candidate(cand)
    assert payload is not None
    assert payload["entities"]["sport_intent_authored"] is True
    assert payload["entities"]["response_selector_skip_honesty"] is True
    assert "Mantendo foco" not in payload["executive_summary"]


def test_skill_skips_fresh_fixture_opener():
    os.environ["ENABLE_SPORT_INTENTS"] = "1"
    ctx = {
        "csl": {
            "teams": ["Flamengo", "Palmeiras"],
            "fixture": "Flamengo x Palmeiras",
        },
        "raw_user_message": "Flamengo x Palmeiras",
    }
    apply_sport_intent_layer("Flamengo x Palmeiras", ctx)
    cand = generate_sport_intent_skill(
        "analisar Flamengo x Palmeiras (comparativo de forca)", ctx
    )
    assert cand is None


def test_try_select_prefers_skill_over_hold_pool():
    os.environ["ENABLE_SPORT_INTENTS"] = "1"
    os.environ["ENABLE_RESPONSE_SELECTOR"] = "1"
    ctx = {
        "csl": {
            "teams": ["Flamengo", "Palmeiras"],
            "fixture": "Flamengo x Palmeiras",
        },
        "last_match": "Flamengo x Palmeiras",
        "raw_user_message": "Quem está melhor?",
        "conversation_continuity": {
            "active": True,
            "turns_left": 3,
            "mode": "partial_analysis",
            "last_team": "Flamengo",
            "last_fixture": "Flamengo x Palmeiras",
        },
    }
    apply_sport_intent_layer("Quem está melhor?", ctx)
    pool = collect_early_candidates(
        "forma recente de Flamengo e Palmeiras", ctx, brain={}
    )
    owners = {c.owner for c in pool}
    assert OWNER_SPORT_INTENT_SKILL in owners
    winner = select_response(pool)
    assert winner is not None
    assert winner.owner == OWNER_SPORT_INTENT_SKILL

    selected = try_select_early_response(
        "forma recente de Flamengo e Palmeiras", ctx, brain={}
    )
    assert selected is not None
    ents = selected.get("entities") or {}
    assert ents.get("response_owner") == OWNER_SPORT_INTENT_SKILL
    assert "fase recente" in (selected.get("executive_summary") or "").lower() or (
        "Flamengo" in (selected.get("executive_summary") or "")
    )


def test_calendar_intent_not_authored_by_skill_generator():
    os.environ["ENABLE_SPORT_INTENTS"] = "1"
    ctx = {
        "csl": {"teams": ["Flamengo"], "fixture": None},
        "sport_intents": {
            "intent": "calendar_query",
            "skill": "skill_calendar_query",
            "confidence": 0.9,
            "applied": True,
        },
    }
    cand = generate_sport_intent_skill("quando joga Flamengo?", ctx)
    assert cand is None
