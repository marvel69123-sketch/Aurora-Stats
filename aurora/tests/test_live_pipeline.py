"""
Copy of live pipeline tests for the deploy tree (artifacts/aurora).
Run: cd artifacts/aurora && python -m pytest tests/ -v
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from src.core.fixture_status import LIVE_STATUSES, fixture_is_live, parse_fixture_status
from src.core.nl_router import route
from src.core.intelligence_engine import _exec_summary


@pytest.mark.parametrize("short", ["1H", "2H", "HT", "ET", "BT", "P", "SUSP"])
def test_user_rule_live_statuses(short):
    assert fixture_is_live({"short": short}) is True


def test_sao_bernardo_cuiaba_ao_vivo_entities():
    r = route("analise sao bernardo x cuiaba ao vivo")
    assert r.intent == "analyze_match"
    assert "vivo" not in r.entities["away"].lower()
    assert r.entities.get("is_live") is True


def test_first_half_opening_not_prematch():
    text = _exec_summary(
        hn="São Bernardo", an="Cuiabá", league="Serie B",
        best_market_name="Over 1.5", probability=60.0, ev=3.0,
        overall_conf=6.0, mv1_score=6.0, risk="Medium",
        is_live=True, minute=37, h_score=1, a_score=0,
        has_xg=False, has_standings=True, dc_actionable=1, mv1_passed=True,
    )
    assert "pre-match" not in text.lower()
    assert "live" in text.lower()


def test_parse_1h():
    is_live, _, minute = parse_fixture_status(
        {"short": "1H", "long": "First Half", "minute": 37}
    )
    assert is_live and minute == 37
