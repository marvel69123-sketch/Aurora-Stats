"""Aurora v3.3.0-beta — match_card presentation builder tests."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.communication.match_card import (
    AURORA_MATCH_VERSION,
    attach_match_card,
    build_match_card_from_analyze,
    build_match_card_from_live_fixture,
    build_predictability,
)


def _analyze_fixture() -> dict:
    return {
        "fixture": {
            "id": 1,
            "venue": {"name": "Stade de France", "city": "Saint-Denis"},
            "status": {"long": "First Half", "short": "1H", "minute": 32},
        },
        "league": {
            "name": "UEFA Nations League",
            "logo": "https://example.com/league.png",
            "country": "World",
            "round": "Final",
        },
        "teams": {
            "home": {"name": "France", "logo": "https://example.com/fr.png"},
            "away": {"name": "Spain", "logo": "https://example.com/es.png"},
        },
        "score": {"current": {"home": 1, "away": 0}},
    }


def test_build_from_analyze_live():
    card = build_match_card_from_analyze(
        _analyze_fixture(),
        is_live=True,
        minute=32,
        status_label="First Half",
        confidence={"score": 6.5, "label": "moderate"},
    )
    assert card is not None
    assert card["home"]["name"] == "France"
    assert card["home"]["logo"]
    assert card["away"]["name"] == "Spain"
    assert card["score"] == {"home": 1, "away": 0}
    assert card["competition"]["name"] == "UEFA Nations League"
    assert card["venue"]["name"] == "Stade de France"
    assert card["is_live"] is True
    assert card["minute"] == 32
    assert card["momentum"]["side"] == "away"  # home leading → away pressing
    assert card["predictability"]["label"]


def test_build_from_analyze_prematch_no_score_noise():
    data = _analyze_fixture()
    data["score"] = {"current": {"home": 0, "away": 0}}
    card = build_match_card_from_analyze(
        data,
        is_live=False,
        minute=None,
        status_label="Not Started",
        confidence={"score": 4.0, "label": "adequate"},
    )
    assert card is not None
    assert card["score"] is None  # 0-0 prematch hidden
    assert card["momentum"] is None
    assert card["venue"]["city"] == "Saint-Denis"


def test_build_from_live_fixture():
    fx = {
        "status": {"long": "Second Half", "short": "2H", "minute": 67},
        "league": {"name": "Premier League", "logo": "https://l.png", "country": "England", "round": "R30"},
        "home": {"name": "Arsenal", "logo": "https://a.png", "score": 2},
        "away": {"name": "Chelsea", "logo": "https://c.png", "score": 2},
    }
    card = build_match_card_from_live_fixture(
        fx,
        confidence={"score": 5.0, "label": "adequate"},
    )
    assert card is not None
    assert card["is_live"] is True
    assert card["score"] == {"home": 2, "away": 2}
    assert card["momentum"]["label"] == "Equilíbrio"
    assert card["venue"] is None


def test_attach_match_card_sets_version():
    payload = {"intent": "analyze_match", "aurora_version": "Copilot v1.0"}
    card = build_match_card_from_analyze(
        _analyze_fixture(),
        is_live=True,
        minute=10,
        status_label="1H",
        confidence={"score": 7.0, "label": "moderate"},
    )
    out = attach_match_card(payload, card)
    assert out["match_card"]["home"]["name"] == "France"
    assert out["aurora_version"] == AURORA_MATCH_VERSION


def test_predictability_labels():
    p = build_predictability({"score": 8.2, "label": "strong"}, is_live=False)
    assert p is not None
    assert "firme" in p["summary"].lower() or "Alta" in p["label"]


def test_round_int_coerced_for_pydantic():
    """API-Football sometimes returns round as int — must not drop match_card."""
    from src.routers.copilot_unified_router import MatchCard

    data = _analyze_fixture()
    data["league"]["round"] = 30
    card = build_match_card_from_analyze(
        data,
        is_live=True,
        minute=32,
        status_label="First Half",
        confidence={"score": 6.5, "label": "moderate"},
    )
    assert card is not None
    assert card["competition"]["round"] == "30"
    mc = MatchCard(**card)
    assert mc.competition is not None
    assert mc.competition.round == "30"


def test_normalize_match_card_repairs_bad_types():
    from src.communication.match_card import normalize_match_card
    from src.routers.copilot_unified_router import MatchCard

    raw = {
        "home": {"name": "England", "logo": 123},
        "away": {"name": "Argentina", "logo": None},
        "competition": {"name": "Friendly", "round": 1, "country": "World"},
        "venue": {"name": "Wembley", "city": "London"},
        "is_live": False,
        "minute": "12",
        "predictability": {"score": "7", "label": "Alta", "summary": "ok"},
    }
    cleaned = normalize_match_card(raw)
    assert cleaned is not None
    assert cleaned["home"]["logo"] is None  # non-string logos dropped
    assert cleaned["competition"]["round"] == "1"
    assert cleaned["minute"] == 12
    MatchCard(**cleaned)


def test_followup_reuses_match_card():
    from src.core.follow_up_engine import resolve

    la = {
        "match": "France x Spain",
        "status": "First Half",
        "is_live": True,
        "minute": 32,
        "best_markets": [],
        "confidence": {"score": 6.0, "label": "moderate", "explanation": "", "data_sources": []},
        "risk": {"level": "Medium", "flags": [], "invalidation_conditions": []},
        "bankroll_recommendation": {
            "recommended_stake_pct": 1.0,
            "method": "quarter-Kelly",
            "examples": {},
            "no_bet": False,
            "reasoning": "ok",
        },
        "positive_factors": ["Pressão"],
        "negative_factors": [],
        "historical_references": [],
        "knowledge_notes": [],
        "match_card": {
            "home": {"name": "France", "logo": "https://fr.png"},
            "away": {"name": "Spain", "logo": "https://es.png"},
            "score": {"home": 1, "away": 0},
            "competition": {"name": "Nations League"},
            "venue": {"name": "Stade de France", "city": "Saint-Denis"},
            "status_label": "First Half",
            "minute": 32,
            "is_live": True,
            "momentum": {"label": "Pressão do visitante", "side": "away"},
            "predictability": {"score": 6.0, "label": "Previsibilidade moderada", "summary": "x"},
        },
    }
    ctx = {
        "last_home": "France",
        "last_away": "Spain",
        "last_match": "France x Spain",
        "last_analysis": la,
        "last_is_live": True,
    }
    out = resolve("atualizar partida", ctx, {"version": "test"})
    assert out is not None
    assert out["intent"] == "follow_up"
    assert out["match_card"]["home"]["name"] == "France"
    assert out["match_card"]["home"]["logo"] == "https://fr.png"
    assert out["aurora_version"] == AURORA_MATCH_VERSION


def test_timbuense_agora_not_false_followup():
    """Regression: team names ending in 'e' must not match 'e agora'."""
    from src.core.follow_up_engine import _detect_followup_type, is_followup

    msg = "como está Sportivo Las Parejas x Timbuense agora?"
    assert _detect_followup_type(msg) is None
    assert is_followup(msg) is False


def test_fixtures_equivalent_helper():
    from src.routers.copilot_unified_router import _fixtures_equivalent

    assert _fixtures_equivalent(
        "England",
        "Argentina",
        last_match="England x Argentina",
        last_home="England",
        last_away="Argentina",
    )
    assert not _fixtures_equivalent(
        "Sportivo Las Parejas",
        "Timbuense",
        last_match="England x Argentina",
        last_home="England",
        last_away="Argentina",
    )