"""Aurora v3.3.2-beta — fuzzy entity resolver (difflib) tests."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.entity_resolver import (
    fuzzy_correct_team,
    normalize_team_name,
    resolve_team,
)


def test_fuzzy_argentin_to_argentina():
    canon, score = fuzzy_correct_team("argentin")
    assert canon == "Argentina"
    assert score >= 0.78


def test_fuzzy_inglater_to_england():
    # Alias maps inglaterra → England
    canon, score = fuzzy_correct_team("inglater")
    assert canon == "England"
    assert score >= 0.78


def test_fuzzy_flamngo_to_flamengo():
    canon, score = fuzzy_correct_team("flamngo")
    assert canon == "Flamengo"
    assert score >= 0.78


def test_fuzzy_sants_to_santos():
    canon, score = fuzzy_correct_team("sants")
    assert canon == "Santos"
    assert score >= 0.78


def test_normalize_applies_fuzzy():
    assert normalize_team_name("flamngo") == "Flamengo"
    assert normalize_team_name("argentin") == "Argentina"
    assert normalize_team_name("sants") == "Santos"


def test_resolve_team_fuzzy_confidence():
    result = resolve_team("flamngo")
    assert result["canonical"] == "Flamengo"
    assert result["confidence"] >= 0.78
    assert result["alias_hit"] is True


def test_fuzzy_rejects_fiction():
    canon, _score = fuzzy_correct_team("goku")
    assert canon is None
    canon2, _ = fuzzy_correct_team("marte")
    assert canon2 is None
