"""Unit tests for EntityResolver (Phase 5A) — no API calls."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.entity_resolver import (
    EntityResolver,
    compact,
    fold,
    has_alias,
    match_team_in_fixture_names,
    name_match,
    normalize_team_name,
    resolve_team,
    search_variants,
)
from src.core.copilot_engine import normalize_team_name as ce_normalize, _TEAM_ALIASES
from src.core.team_aliases import TEAM_ALIASES


def test_aliases_shared_sot():
    assert _TEAM_ALIASES is TEAM_ALIASES
    assert TEAM_ALIASES["fla"] == "Flamengo"
    assert TEAM_ALIASES["nublense"] == "Nublense"


def test_fold_compact():
    assert fold("O'Higgins") == "ohiggins" or "ohiggins" in compact("O'Higgins")
    assert compact("O'Higgins") == "ohiggins"
    assert compact("Ñublense") == "nublense"
    assert fold("São Paulo") == "sao paulo"


def test_normalize_aliases():
    assert normalize_team_name("botafogo-pb") == "Botafogo PB"
    assert normalize_team_name("confiança") == "Confianca"
    assert normalize_team_name("ñublense") == "Nublense"
    assert normalize_team_name("o'higgins") == "O'Higgins"
    # Compat path still works
    assert ce_normalize("fla") == "Flamengo"


def test_resolve_team_shape():
    r = resolve_team("psg")
    assert set(r.keys()) >= {"canonical", "team_id", "candidates", "ambiguity", "confidence"}
    assert r["canonical"] == "Paris Saint-Germain"
    assert r["team_id"] is None  # sync path has no API
    assert r["alias_hit"] is True
    assert r["confidence"] >= 0.9
    assert r["ambiguity"] is False


def test_resolve_team_unknown():
    r = resolve_team("Clube Inventado XYZ")
    assert r["canonical"]
    assert r["alias_hit"] is False
    assert r["confidence"] < 0.9


def test_has_alias():
    assert has_alias("botafogo pb")
    assert has_alias("Ñublense")
    assert not has_alias("Clube Inventado XYZ")


def test_name_match_and_live():
    assert name_match("O'Higgins", "ohiggins")
    assert name_match("Ñublense", "nublense")
    assert match_team_in_fixture_names("Flamengo", "Flamengo", "Palmeiras")
    assert match_team_in_fixture_names("palmeiras", "Flamengo", "Sociedade Esportiva Palmeiras")
    assert not match_team_in_fixture_names("Vasco", "Flamengo", "Palmeiras")


def test_search_variants_ohiggins():
    variants = search_variants("O'Higgins")
    assert "ohiggins" in variants
    assert all(len(v) >= 3 for v in variants)


def test_cache():
    er = EntityResolver()
    a = er.resolve_team("psg")
    b = er.resolve_team("psg")
    assert a is b  # same cached object
    er.clear_cache()
    c = er.resolve_team("psg")
    assert c is not a
    assert c.canonical == a.canonical
