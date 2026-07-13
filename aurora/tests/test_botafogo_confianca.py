"""NLP + entity resolution tests for smaller / international clubs + live routing."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.nl_router import route, normalize, fold_team_key
from src.core.copilot_engine import normalize_team_name
from src.routers.analyze import _name_match, _fold, _compact, _search_variants


def test_normalize_apostrophe_and_accent():
    assert normalize("O'Higgins") == "ohiggins"
    assert "nublense" in normalize("Ñublense x O'Higgins ao vivo")
    assert fold_team_key("O'Higgins") == "ohiggins"
    assert fold_team_key("Ñublense") == "nublense"
    assert _compact("O'Higgins") == "ohiggins"
    assert _compact("Ñublense") == "nublense"


def test_botafogo_pb_alias():
    assert normalize_team_name("botafogo-pb") == "Botafogo PB"
    assert normalize_team_name("botafogo pb") == "Botafogo PB"
    assert normalize_team_name("confiança") == "Confianca"


def test_chilean_aliases():
    assert normalize_team_name("nublense") == "Nublense"
    assert normalize_team_name("ñublense") == "Nublense"
    assert normalize_team_name("ohiggins") == "O'Higgins"
    assert normalize_team_name("o'higgins") == "O'Higgins"
    assert normalize_team_name("o higgins") == "O'Higgins"


def test_analyze_botafogo_pb_x_confianca():
    r = route("analise botafogo-pb x confiança")
    assert r.intent == "analyze_match"
    assert r.entities["home"] == "Botafogo PB"
    assert r.entities["away"] == "Confianca"
    assert r.entities.get("is_live") is not True


def test_botafogo_pb_ao_vivo_not_live_opportunities():
    r = route("botafogo pb x confiança ao vivo")
    assert r.intent == "analyze_match"
    assert r.entities["home"] == "Botafogo PB"
    assert r.entities["away"] == "Confianca"
    assert r.entities.get("is_live") is True


def test_como_esta_agora():
    r = route("como está botafogo pb x confiança agora")
    assert r.intent == "analyze_match"
    assert r.entities["home"] == "Botafogo PB"
    assert r.entities["away"] == "Confianca"
    assert r.entities.get("is_live") is True


def test_nublense_ohiggins_ao_vivo():
    r = route("nublense x o'higgins ao vivo")
    assert r.intent == "analyze_match"
    assert r.entities["home"] == "Nublense"
    assert r.entities["away"] == "O'Higgins"
    assert r.entities.get("is_live") is True


def test_analise_nublense_ohiggins():
    r = route("analise nublense x o'higgins")
    assert r.intent == "analyze_match"
    assert r.entities["home"] == "Nublense"
    assert r.entities["away"] == "O'Higgins"


def test_sao_bernardo_cuiaba_ao_vivo():
    r = route("analise sao bernardo x cuiaba ao vivo")
    assert r.intent == "analyze_match"
    assert "vivo" not in r.entities["away"].lower()
    assert r.entities.get("is_live") is True


def test_sao_bernardo_cuiaba_ao_vivo_bare():
    """Mandatory: no command prefix, still analyze_match (never live_opportunities)."""
    r = route("sao bernardo x cuiaba ao vivo")
    assert r.intent == "analyze_match"
    assert r.entities.get("is_live") is True
    assert "vivo" not in r.entities["away"].lower()


def test_name_match_fuzzy_international():
    assert _name_match("Botafogo PB", "botafogo-pb")
    assert _name_match("Confianca", "confiança")
    assert _name_match("Ñublense", "nublense")
    assert _name_match("O'Higgins", "ohiggins")
    assert _name_match("O'Higgins", "o higgins")
    assert _name_match("O Higgins", "O'Higgins")
    assert _fold("Botafogo-PB") == "botafogo pb"
    assert _fold("O'Higgins") == "ohiggins"


def test_search_variants_apostrophe_safe():
    vs = _search_variants("O'Higgins")
    assert "ohiggins" in vs
    assert any("'" not in v for v in vs)
    vs2 = _search_variants("Botafogo PB")
    assert "botafogo pb" in vs2 or "Botafogo PB" in vs2 or "botafogo" in vs2
