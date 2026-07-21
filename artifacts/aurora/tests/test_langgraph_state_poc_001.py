"""LANGGRAPH-STATE-POC-001 — SportTopicState / LangGraph host unit tests.

Exercises POC graph/state API directly (not full engines / router).
Flag may be ON for these tests; production default remains OFF.
"""

from __future__ import annotations

import os

from src.conversation.langgraph_state_adapter import (
    compare_shadow,
    langgraph_state_enabled,
    legacy_snapshot,
    shadow_from_ctx,
)
from src.conversation.langgraph_state_graph import (
    classify_turn,
    langgraph_package_available,
    process_sport_state_turn,
)
from src.conversation.sport_topic_state import (
    SportTopicState,
    langgraph_state_shadow_enabled,
)


def _enable():
    os.environ["ENABLE_LANGGRAPH_STATE"] = "1"


def _disable():
    os.environ.pop("ENABLE_LANGGRAPH_STATE", None)
    os.environ.pop("ENABLE_LANGGRAPH_STATE_SHADOW", None)


def test_flag_default_off():
    _disable()
    assert langgraph_state_enabled() is False
    assert langgraph_state_shadow_enabled() is False


def test_flag_false_noop_keeps_prior():
    os.environ["ENABLE_LANGGRAPH_STATE"] = "0"
    try:
        sts = SportTopicState(
            teams=["Flamengo", "Palmeiras"],
            fixture="Flamengo x Palmeiras",
            subject="Flamengo x Palmeiras",
        )
        ep = sts.episode_id
        out = process_sport_state_turn("Liverpool x Chelsea", sts)
        assert out.fixture == "Flamengo x Palmeiras"
        assert out.episode_id == ep
    finally:
        _disable()


def test_sticky_bleed_new_fixture_then_soft_fu():
    """
    Critical: Flamengo×Palmeiras → Liverpool×Chelsea → Quem está melhor?
    Fixture must be Liverpool×Chelsea (NOT Flamengo).
    """
    _enable()
    try:
        sts = SportTopicState()
        sts = process_sport_state_turn("Flamengo x Palmeiras", sts)
        assert sts.fixture == "Flamengo x Palmeiras"
        assert "Flamengo" in sts.teams

        sts = process_sport_state_turn("Liverpool x Chelsea", sts)
        assert sts.fixture == "Liverpool x Chelsea"
        assert "Liverpool" in sts.teams
        assert "Flamengo" not in sts.teams

        sts = process_sport_state_turn("Quem está melhor?", sts)
        assert sts.fixture == "Liverpool x Chelsea"
        assert "Liverpool" in sts.teams
        assert "Flamengo" not in (sts.teams or [])
        assert sts.boundary_reason == "soft_followup_same_episode"
    finally:
        _disable()


def test_soft_fu_stays_flamengo():
    """Flamengo×Palmeiras → Quem está melhor? → stays Flamengo."""
    _enable()
    try:
        sts = SportTopicState()
        sts = process_sport_state_turn("Flamengo x Palmeiras", sts)
        ep = sts.episode_id
        sts = process_sport_state_turn("Quem está melhor?", sts)
        assert sts.fixture == "Flamengo x Palmeiras"
        assert "Flamengo" in sts.teams
        assert sts.episode_id == ep
        assert sts.boundary_reason == "soft_followup_same_episode"
    finally:
        _disable()


def test_partial_inter_boundary():
    """Flamengo×Palmeiras → Inter joga hoje? → Inter subject / boundary."""
    _enable()
    try:
        sts = SportTopicState()
        sts = process_sport_state_turn("Flamengo x Palmeiras", sts)
        old_ep = sts.episode_id
        sts = process_sport_state_turn("Inter joga hoje?", sts)
        assert sts.episode_id != old_ep
        assert "Inter" in sts.teams
        assert "Flamengo" not in sts.teams
        assert sts.fixture is None or "Flamengo" not in (sts.fixture or "")
        assert sts.subject == "Inter" or (sts.teams and sts.teams[0] == "Inter")
        assert sts.boundary_reason == "low_entity_overlap"
    finally:
        _disable()


def test_chelsea_soft_keep_after_liverpool_chelsea():
    """
    Soft: Chelsea after Liverpool×Chelsea episode → soft followup keep.

    Expected: short single-token / in-episode team mention keeps Liverpool×Chelsea
    (no new fixture phrase; message ≤ 6 tokens → soft_followup_same_episode,
    or soft_team_in_episode if entities resolved).
    """
    _enable()
    try:
        sts = SportTopicState()
        sts = process_sport_state_turn("Liverpool x Chelsea", sts)
        ep = sts.episode_id
        route, reason = classify_turn("Chelsea", sts)
        assert route == "keep_followup"
        assert reason in {"soft_followup_same_episode", "soft_team_in_episode", "no_current_entities"}
        sts = process_sport_state_turn("Chelsea", sts)
        assert sts.fixture == "Liverpool x Chelsea"
        assert sts.episode_id == ep
        assert "Chelsea" in sts.teams
    finally:
        _disable()


def test_clear_for_new_episode_helper():
    sts = SportTopicState(
        teams=["Flamengo", "Palmeiras"],
        fixture="Flamengo x Palmeiras",
        subject="Flamengo x Palmeiras",
        topic="comparison",
    )
    old = sts.episode_id
    sts.clear_for_new_episode(
        reason="new_fixture",
        seed_teams=["Liverpool", "Chelsea"],
        seed_fixture="Liverpool x Chelsea",
    )
    assert sts.episode_id != old
    assert sts.fixture == "Liverpool x Chelsea"
    assert sts.teams == ["Liverpool", "Chelsea"]
    assert sts.boundary_reason == "new_fixture"
    assert sts.followup_context == {}


def test_replace_subject_keeps_episode():
    sts = SportTopicState(teams=["A"], fixture=None, subject="A")
    ep = sts.episode_id
    sts.replace_subject(teams=["Liverpool", "Chelsea"], fixture="Liverpool x Chelsea")
    assert sts.episode_id == ep
    assert sts.fixture == "Liverpool x Chelsea"


def test_shadow_from_ctx_and_compare():
    ctx = {
        "last_home": "Flamengo",
        "last_away": "Palmeiras",
        "last_match": "Flamengo x Palmeiras",
        "csl": {
            "episode_id": "ep-1",
            "teams": ["Flamengo", "Palmeiras"],
            "fixture": "Flamengo x Palmeiras",
            "topic": "comparison",
        },
        "sport_referent_frame": {
            "fixture_label": "Flamengo x Palmeiras",
            "home": "Flamengo",
            "away": "Palmeiras",
        },
    }
    shadow = shadow_from_ctx(ctx)
    assert shadow.fixture == "Flamengo x Palmeiras"
    assert "Flamengo" in shadow.teams
    leg = legacy_snapshot(ctx)
    diff = compare_shadow(leg, shadow)
    assert diff["divergent"] is False

    other = SportTopicState(
        episode_id="ep-2",
        teams=["Liverpool", "Chelsea"],
        fixture="Liverpool x Chelsea",
    )
    diff2 = compare_shadow(leg, other)
    assert diff2["divergent"] is True
    assert "fixture" in diff2["fields"]


def test_to_dict_from_dict_roundtrip():
    sts = SportTopicState(
        teams=["Liverpool", "Chelsea"],
        fixture="Liverpool x Chelsea",
        subject="Liverpool x Chelsea",
        topic="comparison",
        boundary_reason="seed_subject",
    )
    again = SportTopicState.from_dict(sts.snapshot())
    assert again.fixture == sts.fixture
    assert again.teams == sts.teams
    assert again.episode_id == sts.episode_id


def test_langgraph_package_optional_probe():
    # Installed in CI/dev for this POC; adapter must still import if missing elsewhere.
    assert isinstance(langgraph_package_available(), bool)
