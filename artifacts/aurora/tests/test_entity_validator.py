"""Aurora v3.3.1-beta — entity validation tests."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.entity_validator import (
    INVALID_FIXTURE_MESSAGE,
    invalid_fixture_payload,
    validate_fixture_entities,
    validate_team_entity,
)


def test_rejects_too_long():
    name = "A" * 36
    assert len(name) > 35
    v = validate_team_entity(name)
    assert v.valid is False
    assert "too_long" in v.reasons


def test_rejects_too_many_words():
    v = validate_team_entity("um dois tres quatro cinco")
    assert v.valid is False
    assert "too_many_words" in v.reasons


def test_rejects_stop_words():
    v = validate_team_entity("quero argentina")
    assert v.valid is False
    assert any(r.startswith("stop_words") for r in v.reasons)


def test_rejects_glued_stop_suffix():
    v = validate_team_entity("Inglaterraamanha")
    assert v.valid is False
    assert any(r.startswith("stop_words") for r in v.reasons)


def test_rejects_low_similarity_garbage():
    v = validate_team_entity("XyzqwertyFooBar")
    assert v.valid is False
    assert any(r.startswith("low_similarity") for r in v.reasons)


def test_accepts_known_teams():
    ok, hv, av = validate_fixture_entities("Argentina", "England")
    assert ok is True
    assert hv.valid and av.valid


def test_accepts_flamengo_palmeiras():
    ok, hv, av = validate_fixture_entities("Flamengo", "Palmeiras")
    assert ok is True


def test_invalid_payload_has_no_markets():
    payload = invalid_fixture_payload(
        home="Auroraquerosabersobreargentina",
        away="Inglaterraamanha",
        brain={"v": "test"},
    )
    assert payload["best_markets"] == []
    assert payload["bankroll_recommendation"]["no_bet"] is True
    assert payload["executive_summary"] == INVALID_FIXTURE_MESSAGE
    assert payload["final_recommendation"] == INVALID_FIXTURE_MESSAGE
    assert payload["entities"].get("entity_invalid") is True
