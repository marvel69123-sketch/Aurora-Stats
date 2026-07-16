"""Aurora v3.7 / v3.7.1 — Conversation Intelligence tests."""

from __future__ import annotations

import pytest

from src.conversation.message_intelligence import (
    build_clarification_payload,
    build_conversational_payload,
    process_inbound_message,
    shift_fixture_memory,
)


CTX_BOTA_SANTOS = {
    "last_home": "Botafogo",
    "last_away": "Santos",
    "last_match": "Botafogo x Santos",
    "last_fixture": "Botafogo x Santos",
    "last_market": [{"market": "Over 2.5 Goals", "rank": 1}],
    "last_recommendation": "Over 2.5 com stake reduzida",
}

CTX_TWO_FIXTURES = {
    **CTX_BOTA_SANTOS,
    "prev_home": "Flamengo",
    "prev_away": "Palmeiras",
    "prev_match": "Flamengo x Palmeiras",
    "prev_fixture": "Flamengo x Palmeiras",
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


def test_fala_do_fla_expands_and_confirms():
    r = process_inbound_message("fala do fla", {})
    assert r.needs_clarification is True
    assert r.clarification_prompt


def test_esse_jogo_ai_without_context_is_low_clarify():
    r = process_inbound_message("esse jogo ai", {})
    assert r.needs_clarification is True
    assert r.confidence_band == "low"


def test_esse_jogo_ai_with_context_rewrites_high():
    r = process_inbound_message("esse jogo ai", CTX_BOTA_SANTOS)
    assert r.needs_clarification is False
    assert r.confidence_band == "high"
    assert "Botafogo" in r.message_for_pipeline
    assert "Santos" in r.message_for_pipeline


def test_e_pra_gols_pass_through_keeps_fixture_context_meta():
    r = process_inbound_message("e pra gols?", CTX_BOTA_SANTOS)
    assert r.needs_clarification is False
    assert r.confidence_band == "high"
    # Must NOT become "Botafogo x Santos gols" (market as team)
    assert "Botafogo" not in r.message_for_pipeline
    assert "gol" in r.message_for_pipeline.lower()
    assert r.metadata["ctx"].get("fixture") == "Botafogo x Santos"
    assert r.metadata["ctx"].get("pass_through_followup") is True


def test_e_escanteios_does_not_treat_market_as_team():
    r = process_inbound_message("e escanteios?", CTX_BOTA_SANTOS)
    assert r.needs_clarification is False
    assert r.confidence_band == "high"
    pipe = r.message_for_pipeline.lower()
    assert "escanteio" in pipe
    assert "botafogo" not in pipe
    assert "santos" not in pipe
    assert " x " not in pipe
    assert r.metadata["ctx"].get("fixture") == "Botafogo x Santos"


def test_e_pra_gols_without_context_clarifies():
    r = process_inbound_message("e pra gols?", {})
    assert r.needs_clarification is True
    assert r.confidence_band == "low"


def test_algo_mais_conservador_conversational():
    r = process_inbound_message("algo mais conservador?", CTX_BOTA_SANTOS)
    assert r.needs_clarification is False
    assert r.conversational_reply
    assert "conservador" in r.conversational_reply.lower()
    assert "Botafogo" in r.conversational_reply


def test_esse_ta_melhor_q_o_outro_with_two_fixtures():
    r = process_inbound_message("esse ta melhor q o outro?", CTX_TWO_FIXTURES)
    assert r.needs_clarification is False
    assert r.conversational_reply
    assert "Botafogo" in r.conversational_reply
    assert "Flamengo" in r.conversational_reply


def test_esse_ta_melhor_q_o_outro_single_fixture_honest():
    r = process_inbound_message("esse ta melhor q o outro?", CTX_BOTA_SANTOS)
    assert r.needs_clarification is False
    assert r.conversational_reply
    assert "Botafogo" in r.conversational_reply
    # Must not invent a second fixture
    assert "Flamengo" not in r.conversational_reply


def test_nao_gostei_desse_mercado_conversational():
    r = process_inbound_message("não gostei desse mercado", CTX_BOTA_SANTOS)
    assert r.needs_clarification is False
    assert r.conversational_reply
    assert "alternativa" in r.conversational_reply.lower() or "conservador" in r.conversational_reply.lower()


def test_tem_algo_melhor_conversational():
    r = process_inbound_message("tem algo melhor?", CTX_BOTA_SANTOS)
    assert r.conversational_reply
    assert "alternativa" in r.conversational_reply.lower() or "conservador" in r.conversational_reply.lower()


def test_qual_dos_dois_mais_seguro_with_two_fixtures():
    r = process_inbound_message("qual dos dois é mais seguro?", CTX_TWO_FIXTURES)
    assert r.conversational_reply
    assert "Botafogo" in r.conversational_reply
    assert "Flamengo" in r.conversational_reply


def test_comparado_ao_anterior_with_two_fixtures():
    r = process_inbound_message("comparado ao anterior?", CTX_TWO_FIXTURES)
    assert r.conversational_reply
    assert "Anterior" in r.conversational_reply or "anterior" in r.conversational_reply.lower()


def test_never_invents_opponent_in_clarification_payload():
    r = process_inbound_message("oq acha do santos hj", {})
    assert r.needs_clarification
    p = build_clarification_payload(r.clarification_prompt or {}, {})
    assert p["best_markets"] == []
    assert p["match_card"] is None


def test_conversational_payload_has_no_markets():
    p = build_conversational_payload("Talvez um mercado mais conservador.", {})
    assert p["best_markets"] == []
    assert p["intent"] == "conversation_assist"


def test_shift_fixture_memory():
    ctx: dict = {
        "last_home": "Botafogo",
        "last_away": "Santos",
        "last_match": "Botafogo x Santos",
        "last_market": [{"market": "BTTS"}],
    }
    shift_fixture_memory(ctx, "Flamengo", "Palmeiras", "Flamengo x Palmeiras")
    assert ctx["prev_home"] == "Botafogo"
    assert ctx["prev_away"] == "Santos"
    assert ctx["prev_match"] == "Botafogo x Santos"


def test_fail_open_on_bad_ctx():
    r = process_inbound_message("oi", None)
    assert r.message_for_pipeline is not None
