"""AURORA-INTENT-001 — Semantic Sports Intent Layer tests."""

from __future__ import annotations

import os

from src.conversation.sport_intent_layer import (
    BET_VIABILITY,
    CALENDAR_QUERY,
    COMPARE_STRENGTH,
    HOME_AWAY_ANALYSIS,
    MARKET_QUESTION,
    RECENT_FORM,
    apply_sport_intent_layer,
    classify_sport_intent,
    note_sport_intent_on_payload,
    sport_intents_enabled,
)


def test_flag_default_on():
    os.environ.pop("ENABLE_SPORT_INTENTS", None)
    assert sport_intents_enabled() is True


def test_flag_off_noop():
    os.environ["ENABLE_SPORT_INTENTS"] = "0"
    try:
        r = apply_sport_intent_layer("quem está em melhor fase?")
        assert r.applied is False
        assert r.skipped_reason == "flag_disabled"
        assert r.routed_text == "quem está em melhor fase?"
    finally:
        os.environ["ENABLE_SPORT_INTENTS"] = "1"


def test_classify_all_intents():
    cases = [
        ("Flamengo ou Palmeiras quem ganha?", COMPARE_STRENGTH),
        ("vale a pena apostar?", BET_VIABILITY),
        ("quando joga o Flamengo amanhã?", CALENDAR_QUERY),
        ("como é o mando de campo?", HOME_AWAY_ANALYSIS),
        ("quem está em melhor fase?", RECENT_FORM),
        ("e os escanteios?", MARKET_QUESTION),
    ]
    for msg, expected in cases:
        intent, conf, _ = classify_sport_intent(msg)
        assert intent == expected, (msg, intent, expected)
        assert conf >= 0.70


def test_recent_form_skill_uses_csl_teams():
    os.environ["ENABLE_SPORT_INTENTS"] = "1"
    ctx = {
        "csl": {
            "teams": ["Flamengo", "Palmeiras"],
            "fixture": "Flamengo x Palmeiras",
            "topic": "comparison",
        }
    }
    r = apply_sport_intent_layer("Quem está melhor?", ctx)
    assert r.applied is True
    assert r.intent == RECENT_FORM
    assert r.skill == "skill_recent_form"
    assert "Flamengo" in (r.routed_text or "")
    assert "Palmeiras" in (r.routed_text or "")
    assert r.rewritten is True


def test_market_short_fu_not_rewritten():
    os.environ["ENABLE_SPORT_INTENTS"] = "1"
    ctx = {"csl": {"teams": ["Flamengo", "Palmeiras"], "fixture": "Flamengo x Palmeiras"}}
    r = apply_sport_intent_layer("e os gols?", ctx)
    assert r.intent == MARKET_QUESTION
    assert r.rewritten is False
    assert r.routed_text == "e os gols?"


def test_bet_viability_skill():
    os.environ["ENABLE_SPORT_INTENTS"] = "1"
    ctx = {"last_match": "Flamengo x Palmeiras", "csl": {"teams": ["Flamengo", "Palmeiras"]}}
    r = apply_sport_intent_layer("vale a pena?", ctx)
    assert r.intent == BET_VIABILITY
    assert "Flamengo" in (r.routed_text or "")


def test_home_away_skill():
    os.environ["ENABLE_SPORT_INTENTS"] = "1"
    ctx = {"csl": {"teams": ["Flamengo", "Palmeiras"], "fixture": "Flamengo x Palmeiras"}}
    r = apply_sport_intent_layer("e o mando de campo?", ctx)
    assert r.intent == HOME_AWAY_ANALYSIS
    assert "mando" in (r.routed_text or "").lower()


def test_calendar_skill_injects_team():
    os.environ["ENABLE_SPORT_INTENTS"] = "1"
    ctx = {"csl": {"teams": ["Flamengo", "Palmeiras"]}}
    r = apply_sport_intent_layer("quando joga?", ctx)
    assert r.intent == CALENDAR_QUERY
    assert "Flamengo" in (r.routed_text or "")


def test_payload_stamp():
    os.environ["ENABLE_SPORT_INTENTS"] = "1"
    ctx = {}
    apply_sport_intent_layer("quem está em melhor fase?", ctx)
    payload = {"intent": "follow_up", "entities": {}}
    out = note_sport_intent_on_payload(ctx, payload)
    assert out["entities"]["sport_intent"] == RECENT_FORM
    assert out["entities"]["sport_skill"] == "skill_recent_form"
