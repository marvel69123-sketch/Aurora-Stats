"""Mission 050 — bare market chip short-FU parity (gols ≈ escanteios)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.conversation.conversation_continuity import _is_short_followup
from src.conversation.market_short_followup import (
    bare_market_kind,
    has_sport_sticky_context,
    is_bare_market_followup,
)
from src.conversation.master_intent_router import (
    apply_master_intent,
    classify_master_intent,
)
from src.conversation.ownership_stability import is_continuity_followup_candidate
from src.conversation.sport_continuity_guard import is_sport_short_followup
from src.conversation.sport_intent_layer import MARKET_QUESTION, classify_sport_intent
from src.core.follow_up_engine import _detect_followup_type, is_followup

# Chips solicited by ResponseSelector market_question prompt
_MARKET_CHIPS = (
    "gols",
    "escanteios",
    "cartões",
    "cartoes",
    "BTTS",
    "btts",
    "ambas",
    "over",
    "under",
)


def _sticky_ctx() -> dict:
    return {
        "last_match": "Gremio x Sao Paulo",
        "last_home": "Gremio",
        "last_away": "Sao Paulo",
        "last_analysis": {
            "executive_summary": "Leitura preliminar Gremio x Sao Paulo.",
            "best_markets": [
                {
                    "market": "Over 2.5 gols",
                    "probability": 55.0,
                    "recommended": True,
                },
                {
                    "market": "Over 8.5 escanteios",
                    "probability": 52.0,
                },
            ],
        },
        "conversation_continuity": {
            "active": True,
            "turns_left": 2,
            "last_team": "Gremio",
            "last_fixture": "Gremio x Sao Paulo",
            "mode": "partial_analysis",
        },
        "sport_continuity_guard": {
            "anchor": {
                "fixture": "Gremio x Sao Paulo",
                "teams": ["Gremio", "Sao Paulo"],
                "turns_left": 3,
            },
            "counters": {},
            "turn_index": 1,
        },
    }


def test_shared_bare_market_detector_parity():
    for chip in _MARKET_CHIPS:
        assert is_bare_market_followup(chip), chip
        assert bare_market_kind(chip) is not None, chip
    assert is_bare_market_followup("ambas marcam")
    assert bare_market_kind("gols") == "gols"
    assert bare_market_kind("escanteios") == "escanteios"
    assert bare_market_kind("cartões") == "cartoes"
    assert bare_market_kind("BTTS") == "btts"
    assert bare_market_kind("over") == "over"
    assert bare_market_kind("under") == "under"
    assert not is_bare_market_followup("oi")
    assert not is_bare_market_followup("qual melhor mercado?")


def test_follow_up_engine_bare_gols_parity_with_escanteios():
    assert is_followup("escanteios") is True
    assert is_followup("gols") is True
    assert _detect_followup_type("escanteios") == "corners_market"
    assert _detect_followup_type("gols") == "goals_market"
    assert _detect_followup_type("cartoes") == "cards_market"
    assert _detect_followup_type("cartões") == "cards_market"
    assert _detect_followup_type("btts") == "goals_market"
    assert _detect_followup_type("over") == "goals_market"
    assert _detect_followup_type("under") == "goals_market"
    # Leading "e " still works
    assert _detect_followup_type("e gols") == "goals_market"
    assert _detect_followup_type("e os escanteios") == "corners_market"


def test_scg_and_os_short_fu_parity():
    for chip in ("gols", "escanteios", "cartões", "BTTS", "over", "under"):
        assert is_sport_short_followup(chip) is True, chip
        assert is_continuity_followup_candidate(chip) is True, chip
    assert is_sport_short_followup("oi") is False


def test_sport_intent_bare_market_chips():
    for chip in ("gols", "escanteios", "cartões", "btts", "over", "under"):
        intent, conf, _ = classify_sport_intent(chip)
        assert intent == MARKET_QUESTION, (chip, intent)
        assert conf >= 0.70


def test_continuity_short_fu_kinds():
    assert _is_short_followup("gols") == "gols"
    assert _is_short_followup("escanteios") == "escanteios"
    assert _is_short_followup("cartões") == "cartoes"
    assert _is_short_followup("BTTS") == "btts"
    assert _is_short_followup("over") == "over"
    assert _is_short_followup("under") == "under"


def test_master_intent_sticky_market_chip_not_short_general():
    sticky = _sticky_ctx()
    assert has_sport_sticky_context(sticky) is True

    cold = classify_master_intent("gols")
    assert cold.intent == "GENERAL_CHAT"
    assert cold.reason == "short_general"
    assert cold.allow_sport_pipeline is False

    for chip in ("gols", "escanteios", "cartões", "BTTS", "over", "under"):
        r = classify_master_intent(chip, sticky)
        assert r.intent == "SPORT_QUERY", (chip, r)
        assert r.allow_sport_pipeline is True, chip
        assert r.reason == "sticky_market_chip", (chip, r.reason)

    ctx = dict(sticky)
    applied = apply_master_intent("gols", ctx)
    assert applied.intent == "SPORT_QUERY"
    assert applied.allow_sport_pipeline is True
    assert ctx.get("sport_pipeline_blocked") is not True
    mi = ctx.get("master_intent") or {}
    assert mi.get("allow_sport_pipeline") is True
    assert mi.get("reason") == "sticky_market_chip"


def test_gols_not_general_chat_soft_ga_path_after_market_prompt():
    """After market prompt context, bare gols must stay on sport path."""
    sticky = _sticky_ctx()
    r = classify_master_intent("gols", sticky)
    assert r.intent != "GENERAL_CHAT"
    assert r.allow_sport_pipeline is True
    assert is_followup("gols") is True
    assert is_sport_short_followup("gols") is True
    # Parity: same sport-ok / FU / SCG acceptance as escanteios
    e = classify_master_intent("escanteios", sticky)
    assert e.intent == r.intent
    assert e.allow_sport_pipeline == r.allow_sport_pipeline
    assert is_followup("escanteios") == is_followup("gols")
    assert is_sport_short_followup("escanteios") == is_sport_short_followup("gols")
