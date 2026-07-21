"""AURORA-CSL-001 — Conversation State Layer tests."""

from __future__ import annotations

import os

from src.conversation.conversation_state_layer import (
    CSLState,
    apply_csl_resolve,
    contextualize_followup,
    csl_enabled,
    note_csl_after_response,
)
from src.conversation.sports_language import apply_sports_language_layer


def test_flag_default_on():
    os.environ.pop("ENABLE_CSL", None)
    assert csl_enabled() is True


def test_flag_off_noop():
    os.environ["ENABLE_CSL"] = "0"
    try:
        ctx = {"sll": {"applied": True, "clubs": ["Flamengo", "Palmeiras"], "is_compare": True}}
        out = apply_csl_resolve("Quem está melhor?", ctx)
        assert out == "Quem está melhor?"
        assert ctx["csl"]["skipped_reason"] == "flag_disabled"
    finally:
        os.environ["ENABLE_CSL"] = "1"


def test_state_contract_shape():
    st = CSLState(
        teams=["Flamengo", "Palmeiras"],
        topic="comparison",
        last_intent="fixture_compare",
        date_context=None,
    )
    contract = st.to_dict()["contract"]
    assert contract["teams"] == ["Flamengo", "Palmeiras"]
    assert contract["topic"] == "comparison"
    assert contract["last_intent"] == "fixture_compare"
    assert contract["date_context"] is None
    assert contract["episode_id"]


def test_followup_injection():
    os.environ["ENABLE_CSL"] = "1"
    ctx: dict = {
        "csl": {
            "teams": ["Flamengo", "Palmeiras"],
            "topic": "comparison",
            "last_intent": "fixture_compare",
            "episode_id": "test-ep",
            "phase": "SLOT_READY",
        }
    }
    out = apply_csl_resolve("Quem está melhor?", ctx)
    assert out.lower().startswith("entre flamengo e palmeiras")
    assert "quem está melhor" in out.lower()
    assert ctx["csl"]["injected"] is True
    assert ctx["csl"]["phase"] == "FOLLOWUP"


def test_sll_then_csl_compare_stores_teams():
    os.environ["ENABLE_CSL"] = "1"
    os.environ["ENABLE_SPORTS_LANGUAGE_LAYER"] = "1"
    ctx: dict = {}
    # Canonical compare — SLL may no-op (no aliases); CSL still stores sides
    msg = "Flamengo ou Palmeiras?"
    apply_sports_language_layer(msg, ctx)
    out = apply_csl_resolve(msg, ctx)
    assert ctx["csl"]["teams"][:2] == ["Flamengo", "Palmeiras"]
    assert ctx["csl"]["topic"] == "comparison"
    assert out


def test_two_turn_followup_flow():
    os.environ["ENABLE_CSL"] = "1"
    os.environ["ENABLE_SPORTS_LANGUAGE_LAYER"] = "1"
    ctx: dict = {}
    # Turn 1 — compare
    t1 = apply_sports_language_layer("Mengão ou Verdão?", ctx)
    apply_csl_resolve(t1.normalized_text if t1.applied else "Mengão ou Verdão?", ctx)
    note_csl_after_response(
        ctx,
        t1.normalized_text,
        {
            "intent": "analyze_match",
            "entities": {"home": "Flamengo", "away": "Palmeiras"},
            "match": "Flamengo x Palmeiras",
        },
    )
    assert ctx["csl"]["teams"][:2] == ["Flamengo", "Palmeiras"]

    # Turn 2 — bare follow-up
    t2 = apply_csl_resolve("Quem está melhor?", ctx)
    assert "Flamengo" in t2 and "Palmeiras" in t2
    assert t2.lower().startswith("entre")


def test_no_inject_without_teams():
    os.environ["ENABLE_CSL"] = "1"
    ctx: dict = {}
    out = apply_csl_resolve("Quem está melhor?", ctx)
    assert out == "Quem está melhor?"
    assert ctx["csl"].get("injected") is False


def test_no_inject_on_new_compare():
    os.environ["ENABLE_CSL"] = "1"
    ctx = {
        "csl": {
            "teams": ["Flamengo", "Palmeiras"],
            "episode_id": "ep",
            "phase": "SLOT_READY",
        }
    }
    out = apply_csl_resolve("City ou United?", ctx)
    assert not out.lower().startswith("entre flamengo")
    assert out == "City ou United?"


def test_contextualize_helper():
    st = CSLState(teams=["Flamengo", "Palmeiras"])
    got = contextualize_followup("Quem está em melhor fase?", st)
    assert got == "Entre Flamengo e Palmeiras, quem está em melhor fase?"


def test_note_stamps_payload_entities():
    os.environ["ENABLE_CSL"] = "1"
    ctx: dict = {"csl": {"teams": ["Flamengo", "Palmeiras"], "episode_id": "e1"}}
    payload = {"intent": "analyze_match", "entities": {"home": "Flamengo", "away": "Palmeiras"}}
    out = note_csl_after_response(ctx, "analisar Flamengo x Palmeiras", payload)
    assert out["entities"]["csl"]["teams"][:2] == ["Flamengo", "Palmeiras"]
    assert out["entities"]["csl"]["episode_id"] == "e1"
