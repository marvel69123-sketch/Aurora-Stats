"""Phase 7.4 — ownership + PIE loop / late-rewrite guards."""

from __future__ import annotations

from src.conversation.perceived_intelligence_engine import apply_perceived_intelligence
from src.conversation.turn_ownership import (
    finalize_early_ownership,
    is_rewrite_locked,
    mark_owner,
    pie_allowed,
    should_skip_competing_social,
)


def test_nre_social_locked():
    p = {
        "executive_summary": "Show.",
        "entities": {"natural_response_v2": "ack", "general_assistant": True},
    }
    p = finalize_early_ownership(p)
    assert p["entities"]["turn_owner"] == "NRE"
    assert is_rewrite_locked(p)
    assert should_skip_competing_social(p)
    assert pie_allowed(p) is False


def test_hce_continuity_locked():
    p = {
        "executive_summary": "Quer placar ou mercados?",
        "entities": {"hce_kind": "soft_followup", "human_conversation": True},
    }
    p = finalize_early_ownership(p)
    assert p["entities"]["turn_owner"] == "HCE"
    assert is_rewrite_locked(p)
    assert pie_allowed(p) is False


def test_pie_no_thin_loop():
    ctx: dict = {
        "human_conversation_state": {
            "last_entity": "Fluminense",
            "is_live": True,
        }
    }
    sport = mark_owner(
        {
            "executive_summary": "Leitura ao vivo.",
            "entities": {"has_analysis": False},
            "is_live": True,
            "match": {"home": "Fluminense"},
            "best_markets": [],
            "positive_factors": [],
            "confidence": {"label": "insufficient", "score": 0},
        },
        "SPORT",
        rewrite_locked=False,
    )
    r1 = apply_perceived_intelligence("Fluminense ao vivo", sport, ctx)
    assert r1 is not None
    t1 = r1.get("executive_summary") or ""
    # Second thin pass must not spam the same caution
    r2 = apply_perceived_intelligence("e agora?", sport, ctx)
    assert r2 is sport or (r2.get("executive_summary") == sport.get("executive_summary"))
    # Signature block
    assert ctx.get("pie_last_signature")


def test_pie_rich_exception_on_hce_market_ask():
    ctx = {
        "human_conversation_state": {
            "last_entity": "Fluminense x Bragantino",
            "is_live": True,
        },
        "last_analysis": {
            "positive_factors": ["Pressao ofensiva aumentou"],
            "best_markets": [
                {
                    "market": "Over 1.5 gols",
                    "odds": 1.45,
                    "risk_level": "conservative",
                    "reasoning": "ritmo alto",
                }
            ],
            "confidence": {"label": "moderate", "score": 0.6},
        },
    }
    p = finalize_early_ownership(
        {
            "executive_summary": "soft",
            "entities": {"hce_kind": "soft_followup", "human_conversation": True},
        }
    )
    assert pie_allowed(p) is False
    out = apply_perceived_intelligence("qual mercado mais conservador?", p, ctx)
    assert "Over 1.5" in (out.get("executive_summary") or "")
