"""Aurora v3.3.1-beta — follow-up hijacking guard tests."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.followup_guard import (
    decide_followup_reuse,
    fixtures_equivalent,
    start_new_fixture_context,
)


def test_different_fixture_discards_reuse():
    ctx = {
        "last_match": "England x Argentina",
        "last_home": "England",
        "last_away": "Argentina",
        "last_analysis": {"match": "England x Argentina", "best_markets": [{"m": 1}]},
    }
    decision = decide_followup_reuse("Las Parejas vs Timbuense", ctx)
    assert decision.previous_fixture == "England x Argentina"
    assert decision.new_fixture is not None
    assert "Parejas" in (decision.new_fixture or "") or "parejas" in (decision.new_fixture or "").lower()
    assert decision.reuse is False
    assert decision.home
    assert decision.away


def test_same_fixture_allows_reuse():
    ctx = {
        "last_match": "England x Argentina",
        "last_home": "England",
        "last_away": "Argentina",
        "last_analysis": {"match": "England x Argentina"},
    }
    decision = decide_followup_reuse("como está agora?", ctx)
    assert decision.previous_fixture == "England x Argentina"
    assert decision.new_fixture is None
    assert decision.reuse is True


def test_same_teams_named_still_reuse():
    ctx = {
        "last_match": "England x Argentina",
        "last_home": "England",
        "last_away": "Argentina",
    }
    decision = decide_followup_reuse("England vs Argentina", ctx)
    assert decision.reuse is True
    assert decision.new_fixture is not None


def test_start_new_fixture_context_clears_analysis():
    ctx = {
        "last_match": "England x Argentina",
        "last_home": "England",
        "last_away": "Argentina",
        "last_analysis": {"match": "England x Argentina", "best_markets": [1]},
        "last_market": [1],
        "last_response_metadata": {"x": 1},
    }
    start_new_fixture_context(ctx, "Las Parejas", "Timbuense")
    assert ctx["last_match"] == "Las Parejas x Timbuense"
    assert ctx["last_home"] == "Las Parejas"
    assert ctx["last_away"] == "Timbuense"
    assert ctx["last_analysis"] is None
    assert ctx["last_market"] is None
    assert "last_response_metadata" not in ctx


def test_fixtures_equivalent_helper():
    assert fixtures_equivalent(
        "England",
        "Argentina",
        last_match="England x Argentina",
        last_home="England",
        last_away="Argentina",
    )
    assert not fixtures_equivalent(
        "Las Parejas",
        "Timbuense",
        last_match="England x Argentina",
        last_home="England",
        last_away="Argentina",
    )
