"""Phase 7.9-A P0-1 — ensure_soft_sections anti-KeyError."""

from __future__ import annotations

from src.conversation.ensure_soft_sections import ensure_soft_sections


def test_fills_missing_confidence_risk_bankroll():
    payload = {
        "intent": "general_chat",
        "executive_summary": "x",
        "final_recommendation": "x",
        "best_markets": [],
    }
    out = ensure_soft_sections(payload)
    assert out is payload
    assert isinstance(out["confidence"], dict)
    assert out["confidence"]["label"] == "insufficient"
    assert isinstance(out["risk"], dict)
    assert isinstance(out["bankroll_recommendation"], dict)
    # builder-style access must not raise
    _ = out["confidence"]
    _ = out["risk"]
    _ = out["bankroll_recommendation"]


def test_idempotent_preserves_existing():
    payload = {
        "confidence": {
            "score": 7.5,
            "label": "strong",
            "explanation": "ok",
            "data_sources": ["X"],
        },
        "risk": {"level": "Low", "flags": [], "invalidation_conditions": []},
        "bankroll_recommendation": {
            "recommended_stake_pct": 1.0,
            "method": "quarter-Kelly",
            "examples": {},
            "no_bet": False,
            "reasoning": "r",
        },
    }
    out = ensure_soft_sections(payload)
    assert out["confidence"]["score"] == 7.5
    assert out["confidence"]["label"] == "strong"
    assert out["risk"]["level"] == "Low"
    assert out["bankroll_recommendation"]["recommended_stake_pct"] == 1.0
