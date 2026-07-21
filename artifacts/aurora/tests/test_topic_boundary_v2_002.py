"""AURORA-TOPIC-BOUNDARY-002 — Sticky context bleed fix tests."""

from __future__ import annotations

import os

from src.conversation.conversation_state_layer import (
    apply_csl_resolve,
    note_csl_after_response,
)
from src.conversation.sport_intent_layer import apply_sport_intent_resolve
from src.conversation.topic_boundary_v2 import (
    apply_topic_boundary_v2,
    detect_episode_boundary,
)


def _sticky_flamengo_ctx() -> dict:
    return {
        "last_home": "Flamengo",
        "last_away": "Palmeiras",
        "last_match": "Flamengo x Palmeiras",
        "entity_v2_last_bind": {
            "home": "Flamengo",
            "away": "Palmeiras",
            "assumptions": ["fixture"],
        },
        "sport_referent_frame": {
            "focus_kind": "FIXTURE",
            "home": "Flamengo",
            "away": "Palmeiras",
            "fixture_label": "Flamengo x Palmeiras",
            "counters": {"assumes": 1},
        },
        "short_conversation_memory": {
            "last_team": "Flamengo",
            "last_fixture": "Flamengo x Palmeiras",
            "last_home": "Flamengo",
            "last_away": "Palmeiras",
        },
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


def _pipeline_turn(message: str, ctx: dict) -> str:
    """Mirror TOPIC-BOUNDARY-002 router order: boundary → CSL → sport intent."""
    apply_topic_boundary_v2(message, ctx)
    message = apply_csl_resolve(message, ctx)
    message = apply_sport_intent_resolve(message, ctx)
    return message


def test_scenario1_soft_followup_no_reset():
    os.environ["ENABLE_TOPIC_BOUNDARY_V2"] = "1"
    os.environ["ENABLE_CSL"] = "1"
    try:
        ctx = _sticky_flamengo_ctx()
        old_ep = ctx["csl"]["episode_id"]
        out = _pipeline_turn("Quem está melhor?", ctx)
        assert ctx.get("episode_boundary") is not True
        assert ctx["csl"]["episode_id"] == old_ep
        assert "Flamengo" in out or "Palmeiras" in out or "melhor" in out.lower()
        # Subject must remain Flamengo/Palmeiras
        teams = ctx.get("csl", {}).get("teams") or []
        assert "Flamengo" in teams and "Palmeiras" in teams
    finally:
        os.environ.pop("ENABLE_TOPIC_BOUNDARY_V2", None)


def test_scenario2_new_fixture_subject_rotates():
    os.environ["ENABLE_TOPIC_BOUNDARY_V2"] = "1"
    os.environ["ENABLE_CSL"] = "1"
    try:
        ctx = _sticky_flamengo_ctx()
        old_ep = ctx["csl"]["episode_id"]
        out = _pipeline_turn("Liverpool x Chelsea", ctx)

        assert ctx.get("episode_boundary") is True
        assert ctx.get("boundary_detected") is True
        assert ctx.get("boundary_reason") == "new_fixture"
        assert ctx.get("subject_replaced") is True
        assert ctx.get("srf_cleared") is True
        assert ctx.get("entity_bind_cleared") is True
        assert ctx["csl"]["episode_id"] != old_ep

        teams = [str(t) for t in (ctx["csl"].get("teams") or [])]
        assert any("Liverpool" in t for t in teams)
        assert any("Chelsea" in t for t in teams)
        assert not any("Flamengo" in t for t in teams)
        assert not any("Palmeiras" in t for t in teams)
        assert "Flamengo" not in (ctx["csl"].get("fixture") or "")
        assert "Flamengo" not in out
        assert "Palmeiras" not in out
        # Orphan SRF / bind cleared
        srf = ctx.get("sport_referent_frame") or {}
        assert srf.get("fixture_label") in (None, "", "x") or "Flamengo" not in str(
            srf.get("fixture_label") or ""
        )
        assert ctx.get("entity_v2_last_bind") is None
        sm = ctx.get("short_conversation_memory") or {}
        assert sm.get("last_fixture") != "Flamengo x Palmeiras"
    finally:
        os.environ.pop("ENABLE_TOPIC_BOUNDARY_V2", None)


def test_scenario3_followup_after_switch_uses_new_subject():
    os.environ["ENABLE_TOPIC_BOUNDARY_V2"] = "1"
    os.environ["ENABLE_CSL"] = "1"
    try:
        ctx = _sticky_flamengo_ctx()
        _pipeline_turn("Liverpool x Chelsea", ctx)
        # Seed sticky keys as a real analyze turn would (new subject only)
        ctx["last_home"] = "Liverpool"
        ctx["last_away"] = "Chelsea"
        ctx["last_match"] = "Liverpool x Chelsea"
        ctx["csl"]["teams"] = ["Liverpool", "Chelsea"]
        ctx["csl"]["fixture"] = "Liverpool x Chelsea"

        out = _pipeline_turn("Quem está melhor?", ctx)
        assert ctx.get("episode_boundary") is not True
        assert "Flamengo" not in out
        assert "Palmeiras" not in out
        # Contextualized FU or intent should reference Liverpool/Chelsea
        low = out.lower()
        assert "liverpool" in low or "chelsea" in low or "melhor" in low
        teams = ctx.get("csl", {}).get("teams") or []
        assert any("Liverpool" in str(t) for t in teams)
        assert not any("Flamengo" in str(t) for t in teams)
    finally:
        os.environ.pop("ENABLE_TOPIC_BOUNDARY_V2", None)


def test_scenario4_partial_boundary_single_team():
    os.environ["ENABLE_TOPIC_BOUNDARY_V2"] = "1"
    try:
        ctx = _sticky_flamengo_ctx()
        d = detect_episode_boundary("Inter joga hoje?", ctx)
        assert d.is_boundary is True
        assert d.reason == "low_entity_overlap"
        assert any("Inter" in e for e in d.current_entities)

        apply_topic_boundary_v2("Inter joga hoje?", ctx)
        assert ctx.get("episode_boundary") is True
        teams = ctx.get("csl", {}).get("teams") or []
        assert any("Inter" in str(t) for t in teams)
        assert not any("Flamengo" in str(t) for t in teams)
    finally:
        os.environ.pop("ENABLE_TOPIC_BOUNDARY_V2", None)


def test_note_csl_blocked_after_subject_reset():
    os.environ["ENABLE_TOPIC_BOUNDARY_V2"] = "1"
    os.environ["ENABLE_CSL"] = "1"
    try:
        ctx = _sticky_flamengo_ctx()
        _pipeline_turn("Liverpool x Chelsea", ctx)
        assert ctx.get("csl_subject_guard")

        payload = {
            "intent": "analyze_match",
            "match": "Flamengo x Palmeiras",
            "entities": {"home": "Flamengo", "away": "Palmeiras"},
        }
        note_csl_after_response(ctx, "Liverpool x Chelsea", payload)
        assert ctx.get("note_csl_blocked") is True
        fx = (ctx.get("csl") or {}).get("fixture") or ""
        teams = (ctx.get("csl") or {}).get("teams") or []
        assert "Flamengo" not in fx
        assert not any("Flamengo" in str(t) for t in teams)
        assert any("Liverpool" in str(t) for t in teams)
    finally:
        os.environ.pop("ENABLE_TOPIC_BOUNDARY_V2", None)


def test_flag_off_no_bleed_fix_path():
    os.environ["ENABLE_TOPIC_BOUNDARY_V2"] = "0"
    try:
        ctx = _sticky_flamengo_ctx()
        d = apply_topic_boundary_v2("Liverpool x Chelsea", ctx)
        assert d.is_boundary is False
        assert d.skipped_reason == "flag_disabled"
        assert ctx.get("last_match") == "Flamengo x Palmeiras"
        assert ctx.get("entity_v2_last_bind") is not None
    finally:
        os.environ.pop("ENABLE_TOPIC_BOUNDARY_V2", None)
