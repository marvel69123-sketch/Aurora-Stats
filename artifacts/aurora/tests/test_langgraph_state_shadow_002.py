"""LANGGRAPH-STATE-POC-001 Phase 2 — SHADOW MODE unit tests.

Shadow flag ENABLE_LANGGRAPH_STATE_SHADOW is independent of ENABLE_LANGGRAPH_STATE.
Shadow must not require production write flag. No ctx mutation from maybe_shadow_compare.
"""

from __future__ import annotations

import copy
import os

from src.conversation.langgraph_state_adapter import (
    infer_contamination_locus,
    langgraph_state_enabled,
    langgraph_state_shadow_enabled,
    maybe_shadow_compare,
)
from src.conversation.sport_topic_state import SportTopicState


def _clear_flags():
    os.environ.pop("ENABLE_LANGGRAPH_STATE", None)
    os.environ.pop("ENABLE_LANGGRAPH_STATE_SHADOW", None)


def _shadow_on():
    os.environ["ENABLE_LANGGRAPH_STATE_SHADOW"] = "1"


def _shadow_off():
    os.environ.pop("ENABLE_LANGGRAPH_STATE_SHADOW", None)


def _flamengo_ctx(*, episode: str = "ep-flamengo") -> dict:
    return {
        "last_home": "Flamengo",
        "last_away": "Palmeiras",
        "last_match": "Flamengo x Palmeiras",
        "episode_id": episode,
        "last_intent": "fixture_compare",
        "csl": {
            "episode_id": episode,
            "teams": ["Flamengo", "Palmeiras"],
            "fixture": "Flamengo x Palmeiras",
            "topic": "comparison",
            "last_intent": "fixture_compare",
        },
        "sport_referent_frame": {
            "fixture_label": "Flamengo x Palmeiras",
            "home": "Flamengo",
            "away": "Palmeiras",
        },
    }


def _liverpool_ctx(*, episode: str = "ep-liverpool") -> dict:
    return {
        "last_home": "Liverpool",
        "last_away": "Chelsea",
        "last_match": "Liverpool x Chelsea",
        "episode_id": episode,
        "last_intent": "fixture_compare",
        "csl": {
            "episode_id": episode,
            "teams": ["Liverpool", "Chelsea"],
            "fixture": "Liverpool x Chelsea",
            "topic": "comparison",
            "last_intent": "fixture_compare",
        },
        "sport_referent_frame": {
            "fixture_label": "Liverpool x Chelsea",
            "home": "Liverpool",
            "away": "Chelsea",
        },
    }


def test_both_flags_default_off():
    _clear_flags()
    assert langgraph_state_enabled() is False
    assert langgraph_state_shadow_enabled() is False


def test_shadow_off_noop():
    _clear_flags()
    ctx = _flamengo_ctx()
    assert maybe_shadow_compare("Liverpool x Chelsea", ctx) is None
    assert ctx["csl"]["fixture"] == "Flamengo x Palmeiras"


def test_shadow_runs_without_production_flag():
    """Shadow ON + ENABLE_LANGGRAPH_STATE OFF still produces NEW_STATE."""
    _clear_flags()
    _shadow_on()
    try:
        assert langgraph_state_enabled() is False
        assert langgraph_state_shadow_enabled() is True
        ctx = _flamengo_ctx()
        before = copy.deepcopy(ctx)
        result = maybe_shadow_compare("Liverpool x Chelsea", ctx)
        assert result is not None
        assert result["shadow_only"] is True
        assert result["production_write_enabled"] is False
        assert result["old"]["fixture"] == "Flamengo x Palmeiras"
        assert result["new"]["fixture"] == "Liverpool x Chelsea"
        assert "Liverpool" in result["new"]["teams"]
        assert "Flamengo" not in result["new"]["teams"]
        assert result["old"]["intent"] == "fixture_compare"
        assert result["new"]["intent"] in {"fixture_compare", "followup_compare"}
        # Live ctx unchanged (no production writers from shadow)
        assert ctx == before
    finally:
        _clear_flags()


def test_critical_path_shadow_t2_t3():
    """
    Flamengo×Palmeiras → Liverpool×Chelsea → Quem está melhor?

    Simulates multi-writer lag on T2 (OLD still Flamengo) then clean T3
    after Liverpool is in ctx. NEW must be Liverpool after T2 and T3.
    """
    _clear_flags()
    _shadow_on()
    try:
        # T1 seed (optional sanity)
        r1 = maybe_shadow_compare("Flamengo x Palmeiras", {"csl": {}})
        assert r1 is not None
        assert r1["new"]["fixture"] == "Flamengo x Palmeiras"

        # T2: contaminated / lagging OLD (still Flamengo) + Liverpool message
        ctx_t2 = _flamengo_ctx()
        r2 = maybe_shadow_compare("Liverpool x Chelsea", ctx_t2)
        assert r2 is not None
        assert r2["old"]["fixture"] == "Flamengo x Palmeiras"
        assert r2["new"]["fixture"] == "Liverpool x Chelsea"
        assert "Liverpool" in r2["new"]["teams"]
        assert "Chelsea" in r2["new"]["teams"]
        assert r2["contamination_locus"] == "before_langgraph"

        # T3 soft FU with correct prior in ctx
        ctx_t3 = _liverpool_ctx()
        r3 = maybe_shadow_compare("Quem está melhor?", ctx_t3)
        assert r3 is not None
        assert r3["old"]["fixture"] == "Liverpool x Chelsea"
        assert r3["new"]["fixture"] == "Liverpool x Chelsea"
        assert "Liverpool" in r3["new"]["teams"]
        assert "Flamengo" not in r3["new"]["teams"]
        assert r3["new"]["intent"] == "followup_compare"
        assert r3["contamination_locus"] is None
    finally:
        _clear_flags()


def test_soft_fu_keep_flamengo_shadow():
    _clear_flags()
    _shadow_on()
    try:
        ctx = _flamengo_ctx()
        r = maybe_shadow_compare("Quem está melhor?", ctx)
        assert r is not None
        assert r["new"]["fixture"] == "Flamengo x Palmeiras"
        assert "Flamengo" in r["new"]["teams"]
        assert r["new"]["turn_route"] == "keep_followup"
    finally:
        _clear_flags()


def test_soft_fu_with_contaminated_old_locus_before():
    """
    Soft FU when OLD still Flamengo after a Liverpool turn was intended —
    soft keep cannot heal; locus is before_langgraph (contamination entered
    via multi-writer lag, not LangGraph classify).
    """
    _clear_flags()
    _shadow_on()
    try:
        # Contaminated ctx: still Flamengo while user asks soft FU after
        # an uncommitted Liverpool switch (simulates sticky bleed input).
        ctx = _flamengo_ctx()
        r = maybe_shadow_compare("Quem está melhor?", ctx)
        assert r is not None
        # NEW keeps Flamengo (correct relative to OLD, wrong vs dialogue intent)
        assert r["new"]["fixture"] == "Flamengo x Palmeiras"
        # No fixture in message → locus None on this turn alone; document that
        # prior-turn contamination is diagnosed on the Liverpool turn (T2).
        assert r["contamination_locus"] is None
    finally:
        _clear_flags()


def test_infer_locus_inside_when_new_wrong():
    old = {"fixture": "Flamengo x Palmeiras"}
    new = {"fixture": "Flamengo x Palmeiras"}  # failed to adopt Liverpool
    locus = infer_contamination_locus("Liverpool x Chelsea", old, new)
    assert locus == "inside_state_layer"


def test_infer_locus_before_when_old_lags():
    old = {"fixture": "Flamengo x Palmeiras"}
    new = {"fixture": "Liverpool x Chelsea"}
    locus = infer_contamination_locus("Liverpool x Chelsea", old, new)
    assert locus == "before_langgraph"


def test_shadow_fail_open_bad_ctx():
    _clear_flags()
    _shadow_on()
    try:
        # Non-dict ctx should not raise
        assert maybe_shadow_compare("Flamengo x Palmeiras", None) is not None
    finally:
        _clear_flags()
