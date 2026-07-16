"""v3.5.4 — additive aliases + live markets fixture isolation."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.entity_resolver import clear_fuzzy_cache
from src.core.entity_validator import clear_known_teams_cache
from src.core.fixture_integrity import assess_analyze_result, assess_named_fixture
from src.core.live_intelligence_engine import build_live_payload, score_fixture
from src.core.team_aliases import TEAM_ALIASES

clear_fuzzy_cache()
clear_known_teams_cache()


def test_aliases_strongest_oriente():
    r = assess_named_fixture("The Strongest", "Oriente Petrolero")
    assert r.is_blocked is False, r.reasons


def test_aliases_hercilio_juventus_sc():
    r = assess_named_fixture("Hercílio Luz", "Juventus SC")
    assert r.is_blocked is False, r.reasons
    # Must not resolve as Italy Juventus via fuzzy-only path
    assert TEAM_ALIASES["juventus sc"] == "Juventus SC"


def test_aliases_barcelona_sc_guayaquil():
    r = assess_named_fixture("Barcelona SC", "Guayaquil City")
    assert r.is_blocked is False, r.reasons
    assert TEAM_ALIASES["barcelona sc"] == "Barcelona SC"


def test_aliases_catolica_ldu():
    r = assess_named_fixture("Católica", "LDU")
    assert r.is_blocked is False, r.reasons


def test_aliases_knoxville_fort_wayne():
    r = assess_named_fixture("One Knoxville", "Fort Wayne")
    assert r.is_blocked is False, r.reasons


def test_flamengo_palmeiras_still_ok():
    r = assess_named_fixture("Flamengo", "Palmeiras")
    assert r.is_blocked is False


def test_goku_naruto_still_invalid():
    r = assess_named_fixture("Goku", "Naruto")
    assert r.is_blocked is True
    assert r.quality == "INVALID"


def test_api_rescue_when_fixture_found():
    """Unknown typed names + real fixture_id → not INVALID."""
    r = assess_analyze_result(
        "Unknown Club Alpha",
        "Unknown Club Beta",
        fixture_id=999001,
        is_partial=False,
    )
    assert r.is_blocked is False
    assert r.status == "FOUND"
    assert "fixture_found_api_rescue" in r.reasons


def test_fiction_not_rescued_by_fake_fixture_id():
    r = assess_analyze_result("Goku", "Vegeta", fixture_id=999001)
    assert r.is_blocked is True
    assert r.quality == "INVALID"


def _fx(home: str, away: str, *, minute=70, sh=1, sa=0, fid=1):
    return {
        "fixture_id": fid,
        "home": {"name": home, "score": sh},
        "away": {"name": away, "score": sa},
        "status": {"minute": minute, "short": "2H"},
        "league": {"name": "Test League"},
    }


def test_live_payload_markets_only_from_top_fixture():
    fixtures = [
        _fx("Chattanooga", "Alta", fid=10, minute=72, sh=1, sa=0),
        _fx("Orlando Pride", "Other", fid=20, minute=80, sh=0, sa=1),
        _fx("Fort Wayne", "Someone", fid=30, minute=75, sh=2, sa=1),
        _fx("New England II", "Rival", fid=40, minute=68, sh=0, sa=0),
    ]
    payload = build_live_payload(fixtures, brain_meta={"v": "test"})
    markets = payload.get("best_markets") or []
    assert markets, "expected markets for top fixture"
    top = payload["entities"]["top_opportunity"]
    top_home, _, top_away = top.partition(" x ")
    foreign = {"orlando pride", "fort wayne", "new england ii", "chattanooga", "alta"}
    foreign.discard(top_home.lower())
    foreign.discard(top_away.lower())
    blob = " | ".join(m["market"] for m in markets).lower()
    for name in foreign:
        assert name not in blob, f"foreign team {name!r} leaked into markets for {top}"
    assert "analisar" not in blob
    assert "análise completa" not in blob
    # All market rows share the same fixture context (no multi-fixture pack)
    assert len(markets) <= 5
    assert all(m.get("rationale") == markets[0].get("rationale") for m in markets)


def test_score_fixture_labels_have_no_foreign_team_injection():
    s = score_fixture(_fx("Chattanooga", "Alta", minute=70, sh=1, sa=0))
    for m in s.suggested_markets:
        assert "Orlando" not in m
        assert "(" not in m or "pressionando" not in m
    assert "Analisar" not in s.best_market
    assert "Análise completa" not in s.best_market


def test_live_summary_is_conversational():
    payload = build_live_payload(
        [_fx("Chattanooga", "Alta", minute=70, sh=1, sa=0)],
        brain_meta={},
    )
    summary = payload["executive_summary"]
    assert "Cenário atual" in summary
    assert "partida" in summary.lower() or "confronto" in summary.lower()
    assert "≥6,5/10" not in summary
    assert "Melhor oportunidade agora" not in summary
