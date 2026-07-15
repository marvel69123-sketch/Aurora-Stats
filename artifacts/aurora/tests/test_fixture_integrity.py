"""Aurora v3.3.1-beta — Fixture Integrity Guard tests."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.fixture_integrity import (
    INTEGRITY_NOT_FOUND_MESSAGE,
    assess_named_fixture,
    blocked_integrity_payload,
)


def _assert_sports_fail(home: str, away: str, *, expect_status: str | None = None):
    result = assess_named_fixture(home, away)
    assert result.is_blocked, f"{home} x {away} should be blocked, got {result.status}"
    assert result.markets_blocked is True
    assert result.header_blocked is True
    assert result.confidence_label in ("unavailable", "insufficient")
    assert result.confidence_score <= 1.5
    assert result.status in ("NOT_FOUND", "FICTIONAL")
    if expect_status:
        assert result.status == expect_status
    payload = blocked_integrity_payload(result, brain={"v": "test"})
    assert payload["best_markets"] == []
    assert payload["match_card"] is None
    assert payload["executive_summary"] == INTEGRITY_NOT_FOUND_MESSAGE
    assert payload["final_recommendation"] == INTEGRITY_NOT_FOUND_MESSAGE
    assert payload["confidence"]["label"] in ("unavailable", "insufficient")
    assert payload["bankroll_recommendation"]["no_bet"] is True


def test_dragon_ball_vs_naruto_fails():
    _assert_sports_fail("Dragon Ball", "Naruto", expect_status="FICTIONAL")


def test_brasil_vs_goku_fails():
    _assert_sports_fail("Brasil", "Goku", expect_status="FICTIONAL")


def test_messi_vs_cristiano_fails():
    _assert_sports_fail("Messi", "Cristiano", expect_status="FICTIONAL")


def test_teste123_x_abc456_fails():
    _assert_sports_fail("teste123", "abc456", expect_status="NOT_FOUND")


def test_real_clubs_pass_precheck():
    result = assess_named_fixture("Flamengo", "Palmeiras")
    assert result.status == "FOUND"
    assert result.markets_blocked is False
    assert result.is_blocked is False
