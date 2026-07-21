"""AURORA-TOPIC-BOUNDARY-001 — Episode boundary V2 tests."""

from __future__ import annotations

import os

from src.conversation.message_intelligence import is_topic_switch
from src.conversation.topic_boundary_v2 import (
    apply_topic_boundary_v2,
    detect_episode_boundary,
    entity_overlap,
    topic_boundary_v2_enabled,
)


def _sticky_flamengo_ctx() -> dict:
    return {
        "last_home": "Flamengo",
        "last_away": "Palmeiras",
        "last_match": "Flamengo x Palmeiras",
        "csl": {
            "teams": ["Flamengo", "Palmeiras"],
            "fixture": "Flamengo x Palmeiras",
            "episode_id": "ep-old",
            "phase": "COMPARE",
            "topic": "comparison",
        },
        "conversation_focus": {
            "topic_teams": ["Flamengo", "Palmeiras"],
            "topic_fixture": "Flamengo x Palmeiras",
            "topic_kind": "fixture",
        },
        "conversation_continuity": {
            "fixture": "Flamengo x Palmeiras",
            "home": "Flamengo",
            "away": "Palmeiras",
        },
        "sport_continuity_guard": {
            "anchor": {
                "active": True,
                "fixture": "Flamengo x Palmeiras",
                "home": "Flamengo",
                "away": "Palmeiras",
                "teams": ["Flamengo", "Palmeiras"],
                "turns_left": 3,
            }
        },
    }


def test_flag_default_off():
    os.environ.pop("ENABLE_TOPIC_BOUNDARY_V2", None)
    assert topic_boundary_v2_enabled() is False


def test_flag_off_noop():
    os.environ["ENABLE_TOPIC_BOUNDARY_V2"] = "0"
    try:
        ctx = _sticky_flamengo_ctx()
        d = apply_topic_boundary_v2("Santos x Corinthians", ctx)
        assert d.is_boundary is False
        assert d.skipped_reason == "flag_disabled"
        assert ctx.get("last_match") == "Flamengo x Palmeiras"
        assert ctx.get("episode_boundary") is None
    finally:
        os.environ.pop("ENABLE_TOPIC_BOUNDARY_V2", None)


def test_new_fixture_creates_episode():
    os.environ["ENABLE_TOPIC_BOUNDARY_V2"] = "1"
    try:
        ctx = _sticky_flamengo_ctx()
        old_ep = ctx["csl"]["episode_id"]
        d = apply_topic_boundary_v2("Santos x Corinthians", ctx)
        assert d.is_boundary is True
        assert d.reason == "new_fixture"
        assert ctx.get("episode_boundary") is True
        assert ctx.get("last_match") is None
        assert ctx["csl"]["episode_id"] != old_ep
        assert ctx.get("episode_id") == ctx["csl"]["episode_id"]
        assert "Santos" in (ctx["csl"].get("teams") or [])
        # Sport anchor expired via public API
        anchor = (ctx.get("sport_continuity_guard") or {}).get("anchor") or {}
        assert anchor.get("active") is False
    finally:
        os.environ.pop("ENABLE_TOPIC_BOUNDARY_V2", None)


def test_low_entity_overlap_compare():
    os.environ["ENABLE_TOPIC_BOUNDARY_V2"] = "1"
    try:
        ctx = _sticky_flamengo_ctx()
        d = detect_episode_boundary("Santos ou Corinthians?", ctx)
        assert d.is_boundary is True
        assert d.reason == "low_entity_overlap"
        assert d.overlap is not None and d.overlap < 0.34
    finally:
        os.environ.pop("ENABLE_TOPIC_BOUNDARY_V2", None)


def test_soft_followup_keeps_episode():
    os.environ["ENABLE_TOPIC_BOUNDARY_V2"] = "1"
    try:
        ctx = _sticky_flamengo_ctx()
        d = apply_topic_boundary_v2("Quem está melhor?", ctx)
        assert d.is_boundary is False
        assert d.reason == "soft_followup_same_episode"
        assert ctx.get("last_match") == "Flamengo x Palmeiras"
        assert ctx.get("episode_boundary") is not True
    finally:
        os.environ.pop("ENABLE_TOPIC_BOUNDARY_V2", None)


def test_same_fixture_restated_keeps():
    os.environ["ENABLE_TOPIC_BOUNDARY_V2"] = "1"
    try:
        ctx = _sticky_flamengo_ctx()
        d = detect_episode_boundary("Flamengo x Palmeiras", ctx)
        assert d.is_boundary is False
        assert d.reason in {"same_fixture_restated", "overlap_ok"}
    finally:
        os.environ.pop("ENABLE_TOPIC_BOUNDARY_V2", None)


def test_entity_overlap_jaccard():
    ov = entity_overlap(["Flamengo", "Palmeiras"], ["Santos", "Corinthians"])
    assert ov == 0.0
    ov2 = entity_overlap(["Flamengo", "Palmeiras"], ["Flamengo", "Santos"])
    assert abs(ov2 - 1 / 3) < 1e-9
    assert entity_overlap(["Flamengo"], []) is None


def test_is_topic_switch_defers_to_v2_when_flag_on():
    os.environ["ENABLE_TOPIC_BOUNDARY_V2"] = "1"
    try:
        ctx = _sticky_flamengo_ctx()
        assert is_topic_switch("Santos x Corinthians", ctx) is True
        assert is_topic_switch("Quem está melhor?", ctx) is False
        # Same fixture restated should not hard-switch under V2
        assert is_topic_switch("Flamengo x Palmeiras", ctx) is False
    finally:
        os.environ.pop("ENABLE_TOPIC_BOUNDARY_V2", None)


def test_is_topic_switch_legacy_when_flag_off():
    os.environ["ENABLE_TOPIC_BOUNDARY_V2"] = "0"
    try:
        # Legacy: any A x B matches regex regardless of ctx
        assert is_topic_switch("Flamengo x Palmeiras") is True
        assert is_topic_switch("Quem está melhor?") is False
    finally:
        os.environ.pop("ENABLE_TOPIC_BOUNDARY_V2", None)


def test_csl_same_turn_refresh_does_not_hide_switch():
    """CSL may already hold new teams; sticky last_* still drives prior."""
    os.environ["ENABLE_TOPIC_BOUNDARY_V2"] = "1"
    try:
        ctx = _sticky_flamengo_ctx()
        # Simulate CSL refresh before V2
        ctx["csl"]["teams"] = ["Santos", "Corinthians"]
        ctx["csl"]["fixture"] = "Santos x Corinthians"
        d = detect_episode_boundary("Santos x Corinthians", ctx)
        assert d.is_boundary is True
        assert d.reason == "new_fixture"
    finally:
        os.environ.pop("ENABLE_TOPIC_BOUNDARY_V2", None)
