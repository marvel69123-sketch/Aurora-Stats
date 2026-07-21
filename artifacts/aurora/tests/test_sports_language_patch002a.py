"""AURORA-PATCH-002A — Sports Language Layer tests."""

from __future__ import annotations

import os

from src.conversation.sports_language import (
    MIN_APPLY_CONFIDENCE,
    apply_sports_language_layer,
    resolve_nickname,
    sll_enabled,
)


def test_flag_default_on():
    os.environ.pop("ENABLE_SPORTS_LANGUAGE_LAYER", None)
    assert sll_enabled() is True


def test_flag_off_noop():
    os.environ["ENABLE_SPORTS_LANGUAGE_LAYER"] = "0"
    try:
        r = apply_sports_language_layer("Mengão ou Verdão?")
        assert r.applied is False
        assert r.normalized_text == "Mengão ou Verdão?"
        assert r.skipped_reason == "flag_disabled"
    finally:
        os.environ["ENABLE_SPORTS_LANGUAGE_LAYER"] = "1"


def test_mengao_verdao():
    os.environ["ENABLE_SPORTS_LANGUAGE_LAYER"] = "1"
    r = apply_sports_language_layer("Mengão ou Verdão?")
    assert r.applied is True
    assert r.confidence >= MIN_APPLY_CONFIDENCE
    assert "Flamengo" in r.normalized_text or "analisar" in r.normalized_text.lower()
    assert "Palmeiras" in r.normalized_text or "Flamengo" in str(r.clubs)
    assert "Flamengo" in r.clubs and "Palmeiras" in r.clubs
    assert r.raw_text == "Mengão ou Verdão?"
    assert any("Flamengo" in a for a in r.resolved_aliases)
    assert r.is_compare is True


def test_flu_fla():
    r = apply_sports_language_layer("Flu ou Fla?")
    assert r.applied is True
    assert "Fluminense" in r.clubs and "Flamengo" in r.clubs
    assert "analisar" in r.normalized_text.lower()


def test_city_united():
    r = apply_sports_language_layer("City ou United?")
    assert r.applied is True
    assert "Manchester City" in r.clubs
    assert "Manchester United" in r.clubs
    # HI-safe compact tokens (no spaces that break pair extractors)
    assert " " not in r.normalized_text.split(" x ")[0].replace("analisar ", "")
    assert "ManCity" in r.normalized_text or "mancity" in r.normalized_text.lower()
    assert "ManUtd" in r.normalized_text or "manutd" in r.normalized_text.lower()


def test_galo_bahia():
    r = apply_sports_language_layer("Galo ou Bahia?")
    assert r.applied is True
    assert "Atletico Mineiro" in r.clubs
    assert any("bahia" in c.lower() for c in r.clubs) or "Bahia" in r.normalized_text


def test_raposa():
    assert resolve_nickname("raposa") == "Cruzeiro"
    r = apply_sports_language_layer("Raposa ou Galo?")
    assert r.applied is True
    assert "Cruzeiro" in r.clubs
    assert "Atletico Mineiro" in r.clubs


def test_low_confidence_bare_real_noop():
    r = apply_sports_language_layer("isso é real?")
    assert r.applied is False
    assert r.normalized_text == "isso é real?"


def test_form_question_metadata():
    r = apply_sports_language_layer("Quem está em melhor fase?")
    # No aliases → do nothing (no force)
    assert r.applied is False
    assert r.ask_kind in {"form", None} or r.ask_kind == "form"


def test_preserves_raw_on_ctx():
    ctx: dict = {}
    r = apply_sports_language_layer("timão ou fogão", ctx)
    assert r.applied is True
    assert ctx.get("sll", {}).get("raw_text") == "timão ou fogão"
    assert "Corinthians" in ctx["sll"]["clubs"]
    assert "Botafogo" in ctx["sll"]["clubs"]
