"""Aurora v3.3.1-beta — fixture input cleaner + entity stabilization tests."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.entity_resolver import normalize_team_name
from src.core.fixture_input_cleaner import clean_fixture_input, extract_fixture_teams
from src.core.nl_router import route


def test_clean_argentina_vs_inglaterra_amanha():
    raw = "aurora quero saber sobre argentina vs inglaterra amanhã"
    cleaned = clean_fixture_input(raw)
    assert cleaned.home_team == "argentina"
    assert cleaned.away_team == "inglaterra"
    assert cleaned.clean_input == "argentina vs inglaterra"
    assert "aurora" not in cleaned.clean_input
    assert "amanha" not in cleaned.clean_input


def test_clean_accepts_x_vs_contra():
    cases = [
        ("analise brasil x argentina hoje", "brasil", "argentina", "x"),
        ("quero saber sobre psg vs bayern", "psg", "bayern", "vs"),
        ("me diga flamengo contra palmeiras por favor", "flamengo", "palmeiras", "contra"),
    ]
    for raw, home, away, sep in cases:
        cleaned = clean_fixture_input(raw)
        assert cleaned.home_team == home, raw
        assert cleaned.away_team == away, raw
        assert cleaned.separator == sep, raw


def test_extract_fixture_teams_helper():
    home, away, _is_live = extract_fixture_teams(
        "como está Sportivo Las Parejas x Timbuense agora?"
    )
    assert home == "sportivo las parejas"
    assert away == "timbuense"


def test_nl_route_no_longer_glues_stop_words():
    result = route("aurora quero saber sobre argentina vs inglaterra amanhã")
    assert result.intent == "analyze_match"
    home = (result.entities.get("home") or "").lower()
    away = (result.entities.get("away") or "").lower()
    assert "aurora" not in home
    assert "quero" not in home
    assert "saber" not in home
    assert "argentina" in home
    assert "inglaterra" in away or "england" in away
    assert "amanha" not in away
    assert home != "auroraquerosabersobreargentina"
    assert away != "inglaterraamanha"


def test_normalize_team_name_keeps_spaces():
    """Regression: keys[1] used to be the compact key when spaced forms de-dupe."""
    out = normalize_team_name("sportivo las parejas")
    assert " " in out
    assert out.lower() == "sportivo las parejas"


def test_clean_empty_without_separator():
    cleaned = clean_fixture_input("aurora como vai voce")
    assert cleaned.home_team is None
    assert cleaned.away_team is None
    assert cleaned.clean_input == ""
