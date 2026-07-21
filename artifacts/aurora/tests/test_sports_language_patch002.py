"""AURORA-PATCH-002 — Sports language understanding tests."""

from __future__ import annotations

from src.conversation.context_recovery import fuzzy_resolve_team, recover_context
from src.conversation.sports_language import expand_sports_language, resolve_nickname


def test_nick_mengao_verdao():
    assert resolve_nickname("mengão") == "Flamengo"
    assert resolve_nickname("verdão") == "Palmeiras"
    out, notes = expand_sports_language("mengão ou verdão")
    assert "Flamengo" in out and "Palmeiras" in out
    assert notes


def test_recover_slang_compare():
    r = recover_context("mengão ou verdão")
    joined = " ".join(r.teams).lower()
    assert "flamengo" in joined
    assert "palmeiras" in joined
    assert "x" in r.recovered.lower() or "flamengo" in r.recovered.lower()


def test_recover_timao_fogao():
    r = recover_context("timão ou fogão")
    joined = " ".join(r.teams).lower()
    assert "corinthians" in joined
    assert "botafogo" in joined


def test_recover_flu_fla():
    r = recover_context("Flu ou Fla")
    joined = " ".join(r.teams).lower()
    assert "fluminense" in joined
    assert "flamengo" in joined


def test_eu_city_united():
    r = recover_context("City ou United?")
    joined = " ".join(r.teams).lower()
    assert "manchester city" in joined
    assert "manchester united" in joined


def test_eu_real_barca():
    r = recover_context("Real ou Barça?")
    joined = " ".join(r.teams).lower()
    assert "real madrid" in joined
    assert "barcelona" in joined


def test_inter_br_vs_eu():
    assert resolve_nickname("inter", "inter ou gremio") == "Internacional"
    assert resolve_nickname("inter", "Inter ou Milan") == "Inter Milan"
    r = recover_context("inter ou gremio")
    assert any("internacional" in t.lower() for t in r.teams)
    r2 = recover_context("Inter ou Milan")
    joined = " ".join(r2.teams).lower()
    assert "inter milan" in joined or "milan" in joined


def test_chance_still_blocked():
    assert fuzzy_resolve_team("chance") is None


def test_mais_chance_real_barca():
    r = recover_context("quem tem mais chance real ou barca")
    joined = " ".join(r.teams).lower()
    assert "real madrid" in joined
    assert "barcelona" in joined
