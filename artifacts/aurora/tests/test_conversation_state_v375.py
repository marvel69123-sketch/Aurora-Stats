"""Aurora v3.7.5 — Conversation State Engine foundation tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.communication.small_talk import try_small_talk
from src.conversation.conversation_state import (
    CONVERSATION_STATE_TTL_SECONDS,
    active_fixture,
    active_market,
    apply_after_analysis,
    detect_human_intent,
    expire_conversation_state_if_needed,
    get_state,
    hydrate_from_legacy,
    is_state_expired,
    note_small_talk,
)
from src.conversation.message_intelligence import process_inbound_message


def _seed_botafogo_santos(ctx: dict | None = None) -> dict:
    ctx = dict(ctx or {})
    apply_after_analysis(
        ctx,
        "Botafogo",
        "Santos",
        "Botafogo x Santos",
        {
            "best_markets": [
                {"market": "Mais de 8.5 Escanteios", "risk": "high", "rank": 1}
            ],
            "risk": {"level": "High"},
            "final_recommendation": "Mais de 8.5 Escanteios com stake reduzida",
        },
    )
    # Mirror legacy keys used by FollowUp / CI hydrate
    ctx["last_home"] = "Botafogo"
    ctx["last_away"] = "Santos"
    ctx["last_match"] = "Botafogo x Santos"
    ctx["last_fixture"] = "Botafogo x Santos"
    ctx["last_market"] = [{"market": "Mais de 8.5 Escanteios", "risk": "high"}]
    ctx["last_recommendation"] = "Mais de 8.5 Escanteios com stake reduzida"
    ctx["last_analysis"] = {
        "best_markets": [{"market": "Mais de 8.5 Escanteios", "risk": "high"}],
        "risk": {"level": "High"},
    }
    return ctx


# ── Unit: intents ──────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "msg,intent",
    [
        ("tem algo melhor?", "ASK_BETTER_OPTION"),
        ("algo mais conservador?", "ASK_CONSERVATIVE_OPTION"),
        ("algo mais agressivo?", "ASK_AGGRESSIVE_OPTION"),
        ("não gostei disso", "REJECT_MARKET"),
        ("não gostei desse mercado", "REJECT_MARKET"),
        ("explique melhor", "ASK_EXPLANATION"),
        ("por que?", "ASK_EXPLANATION"),
        ("compare", "ASK_COMPARISON"),
        ("detalhe mais", "ASK_MORE_DETAILS"),
        ("e escanteios?", "ASK_MARKET_DETAILS"),
        ("e gols?", "ASK_MARKET_DETAILS"),
    ],
)
def test_detect_human_intents(msg, intent):
    assert detect_human_intent(msg) == intent


# ── Scenario 1: market chain reuses active_fixture ─────────────────────────

def test_scenario1_market_chain_reuses_fixture():
    ctx = _seed_botafogo_santos()
    r1 = process_inbound_message("e escanteios?", ctx)
    assert r1.needs_clarification is False
    assert r1.metadata["ctx"].get("pass_through_followup") is True
    assert r1.metadata["ctx"].get("fixture") == "Botafogo x Santos"
    assert "escanteio" in r1.message_for_pipeline.lower()
    assert "botafogo" not in r1.message_for_pipeline.lower()

    r2 = process_inbound_message("e gols?", ctx)
    assert r2.metadata["ctx"].get("pass_through_followup") is True
    assert r2.metadata["ctx"].get("fixture") == "Botafogo x Santos"
    assert active_fixture(ctx) == "Botafogo x Santos"


# ── Scenario 2: reject → conservative → better (no echo) ───────────────────

def test_scenario2_reject_then_conservative_then_better_no_repeat():
    ctx = _seed_botafogo_santos()
    r1 = process_inbound_message("não gostei desse mercado", ctx)
    assert r1.conversational_reply
    assert "Mais de 8.5 Escanteios" in r1.conversational_reply
    assert "conservador" in r1.conversational_reply.lower()
    assert get_state(ctx).get("last_reply_kind") == "REJECT_MARKET"

    r2 = process_inbound_message("algo mais conservador?", ctx)
    assert r2.conversational_reply
    assert "conservador" in r2.conversational_reply.lower()
    # Must not be the same REJECT menu script
    assert r2.conversational_reply != r1.conversational_reply
    assert "Posso procurar:" not in r2.conversational_reply
    assert "Botafogo" in r2.conversational_reply

    r3 = process_inbound_message("tem algo melhor?", ctx)
    assert r3.conversational_reply
    assert r3.conversational_reply != r2.conversational_reply
    assert "Mais de 8.5 Escanteios" in r3.conversational_reply or "mercado" in r3.conversational_reply.lower()


# ── Scenario 3: switch fixture then market follow-up ───────────────────────

def test_scenario3_switch_to_vitoria_vasco_then_corners():
    ctx = _seed_botafogo_santos()
    apply_after_analysis(
        ctx,
        "Vitoria",
        "Vasco",
        "Vitoria x Vasco",
        {
            "best_markets": [{"market": "Over 2.5 Goals", "risk": "medium"}],
            "risk": {"level": "Medium"},
            "final_recommendation": "Over 2.5",
        },
    )
    ctx["last_home"] = "Vitoria"
    ctx["last_away"] = "Vasco"
    ctx["last_match"] = "Vitoria x Vasco"
    ctx["last_fixture"] = "Vitoria x Vasco"

    assert active_fixture(ctx) == "Vitoria x Vasco"
    r = process_inbound_message("e escanteios?", ctx)
    assert r.metadata["ctx"].get("fixture") == "Vitoria x Vasco"
    assert "Botafogo" not in (r.metadata["ctx"].get("fixture") or "")


# ── Scenario 4: fala do fla — never invent opponent ────────────────────────

def test_scenario4_fala_do_fla_clarifies_no_invent():
    r = process_inbound_message("fala do fla", {})
    assert r.needs_clarification is True
    assert r.clarification_prompt
    prompt = r.clarification_prompt.lower()
    assert "flamengo" in prompt
    assert " x " not in prompt or "adversário" in prompt or "adversario" in prompt
    # Must not invent a concrete opponent club as fact
    assert "palmeiras" not in prompt
    assert "vasco" not in prompt


# ── Scenario 5: small talk still works ─────────────────────────────────────

def test_scenario5_small_talk():
    assert try_small_talk("boa noite", {}) is not None
    who = try_small_talk("quem é você?", {})
    assert who is not None
    assert who.get("intent") == "small_talk"


# ── Scenario 6: sports context survives small talk ─────────────────────────

def test_scenario6_sports_survives_small_talk():
    ctx = _seed_botafogo_santos()
    social = try_small_talk("boa noite", {})
    assert social is not None
    note_small_talk(ctx)
    assert active_fixture(ctx) == "Botafogo x Santos"
    assert active_market(ctx) == "Mais de 8.5 Escanteios"

    r = process_inbound_message("e escanteios?", ctx)
    assert r.metadata["ctx"].get("pass_through_followup") is True
    assert r.metadata["ctx"].get("fixture") == "Botafogo x Santos"


# ── Scenario 7: second analyze replaces active fixture ─────────────────────

def test_scenario7_second_analyze_replaces_active_for_goals():
    ctx = _seed_botafogo_santos()
    apply_after_analysis(
        ctx,
        "Vitoria",
        "Vasco",
        "Vitoria x Vasco",
        {
            "best_markets": [{"market": "BTTS", "risk": "medium"}],
            "final_recommendation": "BTTS",
        },
    )
    ctx["last_home"] = "Vitoria"
    ctx["last_away"] = "Vasco"
    ctx["last_match"] = "Vitoria x Vasco"
    ctx["last_fixture"] = "Vitoria x Vasco"

    r = process_inbound_message("e gols?", ctx)
    assert r.metadata["ctx"].get("fixture") == "Vitoria x Vasco"
    assert active_fixture(ctx) == "Vitoria x Vasco"


# ── TTL: expire conversational only ────────────────────────────────────────

def test_conversation_state_ttl_clears_active_keeps_prev():
    ctx = _seed_botafogo_santos()
    ctx["prev_home"] = "Flamengo"
    ctx["prev_away"] = "Palmeiras"
    ctx["prev_match"] = "Flamengo x Palmeiras"
    old = (datetime.now(timezone.utc) - timedelta(minutes=11)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    ctx["conversation_state"]["last_message_time"] = old
    ctx["conversation_state"]["updated_at"] = old
    assert is_state_expired(ctx, ttl=CONVERSATION_STATE_TTL_SECONDS) is True
    assert expire_conversation_state_if_needed(ctx) is True
    st = get_state(ctx)
    assert st.get("active_fixture") is None
    assert st.get("active_market") is None
    # Historical prev_* kept
    assert ctx["prev_match"] == "Flamengo x Palmeiras"
    assert ctx["last_match"] == "Botafogo x Santos"


def test_hydrate_from_legacy_when_state_empty():
    ctx = {
        "last_home": "Botafogo",
        "last_away": "Santos",
        "last_match": "Botafogo x Santos",
        "last_market": [{"market": "BTTS"}],
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    st = hydrate_from_legacy(ctx)
    assert st["active_fixture"] == "Botafogo x Santos"
    assert st["active_market"] == "BTTS"
