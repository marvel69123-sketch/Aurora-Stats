"""Phase 7.9-C P0-3 — deferred GA general + presence lock."""

from __future__ import annotations

from src.conversation.turn_ownership import (
    can_presence_claim,
    finalize_early_ownership,
    finalize_presence_ownership,
    get_owner,
    is_rewrite_locked,
)


def _ga_general() -> dict:
    return {
        "intent": "general_chat",
        "entities": {
            "general_assistant": True,
            "assistant_kind": "general",
        },
        "executive_summary": "Entendi. Posso te ajudar com isso de forma direta.",
    }


def test_defer_ga_general_first_pass():
    p = finalize_early_ownership(_ga_general())
    assert get_owner(p) is None
    assert not is_rewrite_locked(p)
    assert can_presence_claim(p)


def test_presence_pass_locks_ga_general():
    p = finalize_early_ownership(_ga_general())
    p = finalize_presence_ownership(p)
    assert get_owner(p) == "GA"
    assert is_rewrite_locked(p)


def test_emotional_upgrades_deferred_ga():
    p = finalize_early_ownership(_ga_general())
    assert can_presence_claim(p)
    emo = {
        "intent": "emotional",
        "entities": {"emotional": True, "emotional_kind": "pride"},
        "executive_summary": "Isso significa muito 😊",
    }
    out = finalize_presence_ownership(emo)
    assert get_owner(out) == "EMOTIONAL"
    assert is_rewrite_locked(out)


def test_meta_still_locks_immediately():
    p = {
        "intent": "conversation_assist",
        "entities": {"hce_kind": "meta_question", "human_conversation": True},
        "executive_summary": "meta",
    }
    out = finalize_early_ownership(p)
    assert get_owner(out) == "META"
    assert is_rewrite_locked(out)
    assert not can_presence_claim(out)
