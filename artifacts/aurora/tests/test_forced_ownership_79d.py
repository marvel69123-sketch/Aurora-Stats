"""Phase 7.9-D P1-1 — forced path ownership finalize."""

from __future__ import annotations

from src.conversation.turn_ownership import (
    finalize_forced_ownership,
    get_owner,
    is_rewrite_locked,
)


def test_forced_incomplete_gets_ga_lock():
    payload = {
        "intent": "general_chat",
        "entities": {
            "general_assistant": True,
            "assistant_kind": "general",
            "fallback": True,
            "fallback_source": "forced_general_incomplete",
        },
        "executive_summary": "Entendi. Posso te ajudar com isso de forma direta.",
        "final_recommendation": "Entendi. Posso te ajudar com isso de forma direta.",
        "best_markets": [],
        # intentionally no confidence — ownership must still lock
    }
    out = finalize_forced_ownership(payload)
    assert get_owner(out) == "GA"
    assert is_rewrite_locked(out)
    assert (out.get("entities") or {}).get("forced_nonsport") is True
    assert (out.get("entities") or {}).get("ownership_finalize_pass") == "forced"


def test_forced_bare_shell_gets_owner():
    payload = {
        "intent": "general_chat",
        "entities": {},
        "executive_summary": "x",
        "final_recommendation": "x",
        "best_markets": [],
    }
    out = finalize_forced_ownership(payload)
    assert get_owner(out) == "GA"
    assert is_rewrite_locked(out)


def test_forced_hce_keeps_hce_owner():
    payload = {
        "intent": "conversation_assist",
        "entities": {
            "hce_kind": "soft_followup",
            "human_conversation": True,
        },
        "executive_summary": "continua o fio",
    }
    out = finalize_forced_ownership(payload)
    assert get_owner(out) == "HCE"
    assert is_rewrite_locked(out)
