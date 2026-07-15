"""Aurora — Fixture Integrity Guard (PARTIAL keeps card + markets)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.entity_resolver import clear_fuzzy_cache
from src.core.entity_validator import clear_known_teams_cache
from src.core.fixture_integrity import (
    INTEGRITY_NOT_FOUND_MESSAGE,
    apply_integrity_to_payload,
    assess_analyze_result,
    assess_named_fixture,
    blocked_integrity_payload,
    partial_integrity_payload,
)
from src.core.team_branding import enrich_analyze_teams, logo_url_for_team
from src.communication.match_card import build_match_card_from_analyze

clear_fuzzy_cache()
clear_known_teams_cache()


def _assert_invalid(home: str, away: str, *, expect_status: str | None = None):
    result = assess_named_fixture(home, away)
    assert result.is_blocked, f"{home} x {away} should be INVALID, got {result.status}"
    assert result.quality == "INVALID"
    assert result.markets_blocked is True
    assert result.header_blocked is True
    if expect_status:
        assert result.status == expect_status
    payload = blocked_integrity_payload(result, brain={"v": "test"})
    assert payload["fixture_quality"] == "INVALID"
    assert payload["match_card"] is None
    assert payload["best_markets"] == []
    assert payload["executive_summary"] == INTEGRITY_NOT_FOUND_MESSAGE


def test_goku_x_vegeta_invalid():
    _assert_invalid("Goku", "Vegeta", expect_status="FICTIONAL")


def test_brasil_x_marte_fc_invalid():
    _assert_invalid("Brasil", "Marte FC", expect_status="FICTIONAL")


def test_dragon_ball_vs_naruto_invalid():
    _assert_invalid("Dragon Ball", "Naruto", expect_status="FICTIONAL")


def test_arsenal_chelsea_partial_with_logos():
    named = assess_named_fixture("Arsenal", "Chelsea")
    assert named.is_blocked is False
    assert named.quality == "VALID"

    result = assess_analyze_result(
        "Arsenal",
        "Chelsea",
        fixture_id=0,
        is_partial=True,
    )
    assert result.status == "PARTIAL"
    assert result.quality == "PARTIAL"
    assert result.markets_blocked is False
    assert result.header_blocked is False
    assert result.market_generation_enabled is True

    data = {
        "teams": {
            "home": {"name": "Arsenal", "logo": None},
            "away": {"name": "Chelsea", "logo": None},
        },
        "league": {"name": "Unknown"},
        "fixture": {"venue": {}},
        "score": {"current": {}},
        "_partial": True,
    }
    enrich_analyze_teams(data, home="Arsenal", away="Chelsea")
    assert data["teams"]["home"]["logo"]
    assert data["teams"]["away"]["logo"]
    assert "media.api-sports.io" in data["teams"]["home"]["logo"]
    assert data["league"]["name"] == "Premier League"

    card = build_match_card_from_analyze(
        data,
        is_live=False,
        minute=None,
        status_label="Pré-jogo",
        confidence={"score": 4.5, "label": "adequate"},
    )
    assert card is not None
    assert card["home"]["logo"]
    assert card["away"]["logo"]
    assert card["home"]["name"] == "Arsenal"
    assert card["away"]["name"] == "Chelsea"

    # apply_integrity must KEEP card + markets for PARTIAL
    payload = {
        "intent": "analyze_match",
        "entities": {"home": "Arsenal", "away": "Chelsea"},
        "best_markets": [
            {
                "rank": 1,
                "market": "Over 2.5",
                "probability": 55.0,
                "expected_value": 2.0,
                "confidence": 4.0,
                "risk": "Medium",
                "rationale": "estimate",
            }
        ],
        "match_card": card,
        "executive_summary": "Análise estimada Arsenal x Chelsea.",
        "confidence": {"score": 5.0, "label": "adequate", "explanation": "ok", "data_sources": []},
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0,
            "method": "quarter-Kelly",
            "examples": {},
            "no_bet": True,
            "reasoning": "partial",
        },
    }
    out = apply_integrity_to_payload(payload, result)
    assert out["fixture_quality"] == "PARTIAL"
    assert out["best_markets"]
    assert out["match_card"] is not None
    assert out["match_card"]["home"]["logo"]
    assert out["entities"]["markets_blocked"] is False


def test_argentina_inglaterra_partial():
    named = assess_named_fixture("Argentina", "Inglaterra")
    assert named.is_blocked is False

    result = assess_analyze_result(
        "Argentina",
        "England",
        fixture_id=0,
        is_partial=True,
    )
    assert result.status == "PARTIAL"
    assert result.quality == "PARTIAL"
    assert logo_url_for_team("Argentina")
    assert logo_url_for_team("England")

    payload = partial_integrity_payload(result, brain={"v": "test"})
    assert payload["fixture_quality"] == "PARTIAL"
    assert payload["match_card"] is not None
    assert payload["match_card"]["home"]["logo"]
    assert payload["match_card"]["away"]["logo"]
    assert payload["entities"]["entity_invalid"] is False


def test_flamengo_palmeiras_precheck_ok():
    result = assess_named_fixture("Flamengo", "Palmeiras")
    assert result.status == "FOUND"
    assert result.quality == "VALID"


def _assert_precheck_ok(home: str, away: str):
    result = assess_named_fixture(home, away)
    assert result.is_blocked is False, (
        f"{home} x {away} should pass precheck, got {result.status} {result.reasons}"
    )
    assert result.quality == "VALID"
    assert result.markets_blocked is False
    assert result.header_blocked is False


def test_libertad_universitario_precheck_ok():
    _assert_precheck_ok("Libertad", "Universitario")


def test_libertad_fc_tecnico_universitario_precheck_ok():
    _assert_precheck_ok("Libertad FC", "Tecnico Universitario")
    _assert_precheck_ok("Libertad FC", "Técnico Universitario")


def test_universidad_catolica_not_mapped_to_universitario():
    """Exact Católica aliases must win — never fuzzy into Universitario de Deportes."""
    from src.core.entity_resolver import normalize_team_name

    home = normalize_team_name("Universidad Católica")
    away = normalize_team_name("LDU Quito")
    assert "universitario de deportes" not in home.lower()
    assert "catolica" in home.lower() or "católica" in home.lower()
    assert "universitario de deportes" not in away.lower()
    _assert_precheck_ok("Universidad Católica", "LDU Quito")


def test_leones_cuenca_precheck_ok():
    _assert_precheck_ok("Leones del Norte", "Deportivo Cuenca")


def test_required_big_clubs_precheck_ok():
    _assert_precheck_ok("Arsenal", "Chelsea")
    _assert_precheck_ok("Argentina", "Inglaterra")
    _assert_precheck_ok("Flamengo", "Santos")
    _assert_precheck_ok("Real Madrid", "Barcelona")
    _assert_precheck_ok("Man City", "Liverpool")
    _assert_precheck_ok("Manchester City", "Liverpool")


def test_required_fiction_still_invalid():
    _assert_invalid("Goku", "Vegeta", expect_status="FICTIONAL")
    _assert_invalid("Brasil", "Marte FC", expect_status="FICTIONAL")
    _assert_invalid("Naruto", "Dragon Ball", expect_status="FICTIONAL")
