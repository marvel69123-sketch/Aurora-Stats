"""Aurora v3.7 — Conversation Intelligence foundation tests (14 mandatory cases)."""

from __future__ import annotations

import pytest

from src.conversation.message_intelligence import (
    build_clarification_payload,
    process_inbound_message,
)


CTX_BOTA_SANTOS = {
    "last_home": "Botafogo",
    "last_away": "Santos",
    "last_match": "Botafogo x Santos",
    "last_fixture": "Botafogo x Santos",
}


@pytest.mark.parametrize(
    "message,expect_substr",
    [
        ("sanots", "santos"),
        ("botafog", "botafogo"),
        ("flamnegp", "flamengo"),
    ],
)
def test_typo_normalization_rewrites(message, expect_substr):
    r = process_inbound_message(message, {})
    assert expect_substr in r.message_for_pipeline.lower()
    assert r.needs_clarification is False
    assert r.confidence_band in {"high", "medium"}


def test_slang_oq_acha_santos_hj_asks_confirm_no_invent():
    r = process_inbound_message("oq acha do santos hj", {})
    assert r.needs_clarification is True
    assert r.clarification_prompt
    assert "Santos" in r.clarification_prompt or "santos" in r.clarification_prompt.lower()
    # Must NOT invent an opponent fixture
    assert " x " not in (r.message_for_pipeline if not r.needs_clarification else "")


def test_fala_do_fla_expands_and_confirms():
    r = process_inbound_message("fala do fla", {})
    assert r.needs_clarification is True
    assert r.clarification_prompt
    assert "Flamengo" in r.clarification_prompt or "flamengo" in r.metadata.get("norm", {}).get(
        "normalized", ""
    )


def test_esse_jogo_ai_without_context_is_low_clarify():
    r = process_inbound_message("esse jogo ai", {})
    assert r.needs_clarification is True
    assert r.confidence_band == "low"
    assert "jogo" in (r.clarification_prompt or "").lower() or "times" in (
        r.clarification_prompt or ""
    ).lower()


def test_esse_jogo_ai_with_context_rewrites_high():
    r = process_inbound_message("esse jogo ai", CTX_BOTA_SANTOS)
    assert r.needs_clarification is False
    assert r.confidence_band == "high"
    assert "Botafogo" in r.message_for_pipeline
    assert "Santos" in r.message_for_pipeline


def test_e_pra_gols_with_context():
    r = process_inbound_message("e pra gols?", CTX_BOTA_SANTOS)
    assert r.needs_clarification is False
    assert r.confidence_band == "high"
    assert "Botafogo" in r.message_for_pipeline
    assert "Santos" in r.message_for_pipeline
    assert "gol" in r.message_for_pipeline.lower()


def test_e_escanteios_with_context():
    r = process_inbound_message("e escanteios?", CTX_BOTA_SANTOS)
    assert r.needs_clarification is False
    assert r.confidence_band == "high"
    assert "escanteio" in r.message_for_pipeline.lower()


def test_e_pra_gols_without_context_clarifies():
    r = process_inbound_message("e pra gols?", {})
    assert r.needs_clarification is True
    assert r.confidence_band == "low"


def test_algo_mais_conservador_with_context():
    r = process_inbound_message("algo mais conservador?", CTX_BOTA_SANTOS)
    assert r.needs_clarification is False
    assert r.confidence_band == "high"
    assert "Botafogo" in r.message_for_pipeline
    assert "conservador" in r.message_for_pipeline.lower() or "risco" in r.message_for_pipeline.lower()


def test_esse_ta_melhor_with_context():
    r = process_inbound_message("esse ta melhor?", CTX_BOTA_SANTOS)
    assert r.needs_clarification is False
    assert r.confidence_band == "high"
    assert "Botafogo" in r.message_for_pipeline


def test_o_anterior_parecia_melhor_with_context():
    r = process_inbound_message("o anterior parecia melhor", CTX_BOTA_SANTOS)
    assert r.needs_clarification is False
    assert r.confidence_band == "high"


def test_nao_gostei_desse_mercado_with_context():
    r = process_inbound_message("não gostei desse mercado", CTX_BOTA_SANTOS)
    assert r.needs_clarification is False
    assert r.confidence_band == "high"


def test_qual_dos_dois_mais_seguro_with_context():
    r = process_inbound_message("qual dos dois é mais seguro?", CTX_BOTA_SANTOS)
    assert r.needs_clarification is False
    assert r.confidence_band == "high"


def test_comparado_ao_anterior_with_context():
    r = process_inbound_message("comparado ao anterior?", CTX_BOTA_SANTOS)
    assert r.needs_clarification is False
    assert r.confidence_band == "high"


def test_never_invents_opponent_in_clarification_payload():
    r = process_inbound_message("oq acha do santos hj", {})
    assert r.needs_clarification
    p = build_clarification_payload(r.clarification_prompt or "", {})
    assert p["best_markets"] == []
    assert p["match_card"] is None
    assert p["entities"].get("clarification") is True


def test_fail_open_on_bad_ctx():
    # Should not raise
    r = process_inbound_message("oi", None)
    assert r.message_for_pipeline is not None
