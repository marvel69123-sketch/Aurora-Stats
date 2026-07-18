"""Phase 7.9-E — misroute classifier fixes."""

from __future__ import annotations

from src.conversation.emotional_presence import detect_emotional_intent
from src.conversation.master_intent_router import classify_master_intent


def test_live_listing():
    for msg in (
        "quais jogos estão ao vivo?",
        "quais partidas estão acontecendo agora?",
    ):
        r = classify_master_intent(msg)
        assert r.intent == "LIVE_MATCH", msg
        assert r.allow_sport_pipeline is True


def test_utility_time():
    for msg in ("que horas são?", "horário atual"):
        r = classify_master_intent(msg)
        assert r.intent == "UTILITY_QUERY", msg
        assert r.allow_sport_pipeline is False


def test_emotional_routes():
    cases = {
        "estou triste": "sadness",
        "me sinto sozinho": "loneliness",
        "não vou desistir de você": "support",
        "aurora é minha maior criação": "pride",
    }
    for msg, kind in cases.items():
        assert detect_emotional_intent(msg) == kind, msg
        r = classify_master_intent(msg)
        assert r.intent == "EMOTIONAL_QUERY", msg
        assert r.allow_sport_pipeline is False


def test_sport_schedule_still_sport():
    r = classify_master_intent("juventus joga que horas?")
    assert r.allow_sport_pipeline is True
    assert r.intent in {"SPORT_QUERY", "LIVE_MATCH"}
