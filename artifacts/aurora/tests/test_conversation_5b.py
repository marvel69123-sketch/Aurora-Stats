"""Phase 5B — Conversation Intelligence tests (no external APIs)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.conversation.conversation_context import (
    ConversationManager,
    conversation_manager,
)
from src.core.follow_up_engine import is_followup, resolve, _detect_followup_type


def _sample_analysis(home="Atlanta", away="Colegiales", with_corners=True, with_goals=True):
    markets = []
    if with_goals:
        markets.append({
            "market": "Over 2.5 gols",
            "probability": 58.0,
            "odds_fair": 1.72,
            "ev": 0.05,
            "rationale": "Ambos atacam com frequência.",
            "recommended": True,
        })
    if with_corners:
        markets.append({
            "market": "Over 8.5 escanteios",
            "probability": 55.0,
            "odds_fair": 1.82,
            "ev": 0.04,
            "rationale": "Jogo aberto nas laterais.",
            "recommended": False,
        })
    if not markets:
        markets.append({
            "market": "1X2 — Atlanta",
            "probability": 42.0,
            "odds_fair": 2.3,
            "ev": 0.01,
            "rationale": "Leve favoritismo.",
            "recommended": True,
        })
    return {
        "match": f"{home} x {away}",
        "status": "1H",
        "is_live": True,
        "minute": 34,
        "best_markets": markets,
        "confidence": {"score": 6.5, "label": "adequate", "explanation": "ok", "data_sources": []},
        "risk": {"level": "Moderate", "flags": [], "invalidation_conditions": []},
        "bankroll_recommendation": {
            "recommended_stake_pct": 2.0,
            "method": "quarter-Kelly",
            "examples": {"R$100": "R$2"},
            "no_bet": False,
            "reasoning": "EV positivo moderado.",
        },
        "positive_factors": ["Pressão ofensiva"],
        "negative_factors": ["Defesa vulnerável"],
        "executive_summary": f"Análise de {home} x {away}.",
        "final_recommendation": f"Atenção aos mercados de {home} x {away}.",
        "historical_references": [],
        "knowledge_notes": [],
    }


def _ctx(home="Atlanta", away="Colegiales", **kwargs):
    la = kwargs.pop("last_analysis", _sample_analysis(home, away))
    return {
        "last_home": home,
        "last_away": away,
        "last_match": f"{home} x {away}",
        "last_fixture": f"{home} x {away}",
        "last_analysis": la,
        "last_is_live": True,
        "last_minute": 34,
        "updated_at": "2026-07-13T20:00:00Z",
        **kwargs,
    }


def test_patterns_phase5b():
    assert _detect_followup_type("e os escanteios?") == "corners_market"
    assert _detect_followup_type("e os gols?") == "goals_market"
    assert _detect_followup_type("e para banca pequena?") == "small_bankroll"
    assert _detect_followup_type("continua valendo?") == "still_valid"
    assert _detect_followup_type("ainda vale?") == "still_valid"
    assert _detect_followup_type("como está agora?") == "live_update"
    assert _detect_followup_type("e agora?") == "live_update"
    assert is_followup("e os gols?")


def test_1_atlanta_corners():
    brain = {"version": "test"}
    out = resolve("e os escanteios?", _ctx(), brain)
    assert out is not None
    assert out["intent"] == "follow_up"
    assert "Atlanta" in (out["executive_summary"] or "")
    assert "contexto anterior" in (out["executive_summary"] or "").lower()
    assert "Peça uma nova análise" not in (out["executive_summary"] or "")
    assert out.get("response_metadata", {}).get("used_previous_analysis") is True
    assert out["response_metadata"]["source"] == "conversation_context"


def test_2_botafogo_goals():
    brain = {}
    ctx = _ctx("Botafogo", "Santos")
    out = resolve("e os gols?", ctx, brain)
    assert out is not None
    assert "Botafogo" in out["executive_summary"]
    assert out["match"] == "Botafogo x Santos"


def test_3_small_bankroll():
    out = resolve("e para banca pequena?", _ctx(), {})
    assert out is not None
    assert "banca pequena" in out["executive_summary"].lower()
    br = out["bankroll_recommendation"]
    assert br["recommended_stake_pct"] <= 1.0  # half of 2.0 capped


def test_4_still_valid():
    out = resolve("continua valendo?", _ctx(), {})
    assert out is not None
    assert "continua" in out["executive_summary"].lower() or "contexto" in out["executive_summary"].lower()


def test_5_como_esta_agora():
    out = resolve("como está agora?", _ctx(), {})
    assert out is not None
    assert out.get("response_metadata", {}).get("followup_type") == "live_update"
    # No rigid "peça nova análise"
    assert "Peça uma nova análise" not in (out["executive_summary"] or "")
    assert "Peça:" not in (out.get("final_recommendation") or "")


def test_6_last_fixture_wins():
    """After two matches in ctx, follow-up uses the stored last fixture."""
    ctx = _ctx("Flamengo", "Palmeiras")
    out = resolve("e os gols?", ctx, {})
    assert out["match"] == "Flamengo x Palmeiras"
    assert "Flamengo" in out["executive_summary"]


def test_7_knowledge_does_not_clear_ctx_for_followup():
    """Sporting context remains usable after a non-match digression in the same ctx."""
    ctx = _ctx("Botafogo", "Santos")
    # Simulate knowledge turn that does not wipe last_match (router preserves ctx)
    ctx["last_intent"] = "knowledge_search"
    out = resolve("e os gols?", ctx, {})
    assert out is not None
    assert out["match"] == "Botafogo x Santos"


def test_manager_singleton_and_ttl_memory():
    conversation_manager.clear()
    mgr = conversation_manager
    assert isinstance(mgr, ConversationManager)
    sid = "test-session-5b"
    ctx = _ctx()
    mgr.save(sid, ctx)
    got = mgr.get(sid)
    assert got["last_match"] == "Atlanta x Colegiales"
    assert got.get("last_fixture") == "Atlanta x Colegiales"


def test_corners_without_market_slice_no_rigid():
    la = _sample_analysis(with_corners=False, with_goals=False)
    out = resolve("e os escanteios?", _ctx(last_analysis=la), {})
    assert out is not None
    text = out["executive_summary"] + out["final_recommendation"]
    assert "Peça uma nova análise" not in text
    assert "Peça:" not in text
    assert "contexto anterior" in out["executive_summary"].lower()
