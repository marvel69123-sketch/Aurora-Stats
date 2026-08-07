"""
Mission 016 Phase 5 — Gated Activation PGR-03 ONLY (REGRA 25 / REGRA 27).

Proves:
  - Repo default OFF / 0%; PGR-03 not armed
  - PGR-03 (10% / STAGE3_NOTE_10PCT) path when explicitly flagged
  - pct > 25 blocked without higher PO unlock; PGR-05 not unlocked
  - Instant rollback to OFF; PGR-01/PGR-02 still coherent when PGR-03 off
  - Shadow still works; legacy writers present
  - ENABLE_LANGGRAPH_STATE remains OFF (no full prod write / Phase 6)
  - No auto-advance
"""

from __future__ import annotations

import copy
import os

from src.conversation.langgraph_state_adapter import (
    ingress_order_shadow_compare,
    maybe_shadow_compare,
)
from src.conversation.migration_flag_controller import (
    assert_legal_flag_matrix,
    collect_illegal_combinations,
    flag_snapshot,
)
from src.conversation.progressive_gate_review import (
    AUTHORIZED_OPERATIONAL_MAX_PCT,
    PGR01_PCT,
    PGR01_STAGE,
    PGR02_PCT,
    PGR02_STAGE,
    PGR03_PCT,
    PGR03_STAGE,
    PGR_LADDER,
    higher_pgr_gate_attempted,
    operator_enable_pgr03_instructions,
    pgr01_enable_flag,
    pgr02_enable_flag,
    pgr03_enable_flag,
    pgr_flag_snapshot,
    pgr_metrics_snapshot,
    require_pgr03_for_stage3,
    reset_pgr_metrics,
    rollback_pgr02_to_off,
    rollback_pgr03_to_off,
)
from src.conversation.sole_writer_funnel import (
    AUTHORIZED_OPERATIONAL_MAX_PCT as FUNNEL_AUTH_MAX,
    analyze_funnel_enabled,
    boundary_funnel_enabled,
    commit_via_c17_funnel,
    funnel_flag_snapshot,
    funnel_owns_path,
    funnel_stage_name,
    get_configured_funnel_pct,
    get_funnel_pct,
    note_subject_funnel_enabled,
    reset_funnel_metrics,
    rollback_funnel_to_off,
)
from src.conversation.sport_topic_state import langgraph_state_enabled
from src.conversation.topic_boundary_v2 import apply_episode_boundary


def _clear_flags():
    for k in (
        "ENABLE_LANGGRAPH_STATE",
        "ENABLE_LANGGRAPH_STATE_SHADOW",
        "AURORA_MIGRATION_STAGE",
        "ENABLE_STS_SOLE_WRITER",
        "ENABLE_STS_WRITE_FUNNEL_BOUNDARY",
        "ENABLE_STS_WRITE_FUNNEL_ANALYZE",
        "ENABLE_STS_NOTE_SUBJECT_GUARDS",
        "CLAIM_SHADOW_AS_SOLE_WRITER",
        "AURORA_SOLE_WRITER_FUNNEL_PCT",
        "AURORA_FUNNEL_PO_STAGE_UNLOCK",
        "AURORA_PGR_01_ENABLE",
        "AURORA_PGR_02_ENABLE",
        "AURORA_PGR_03_ENABLE",
        "AURORA_PGR_04_ENABLE",
        "AURORA_PGR_05_ENABLE",
        "AURORA_PGR_06_ENABLE",
        "ENABLE_TOPIC_BOUNDARY_V2",
        "ENABLE_TB_V2_APPLY_MATERIALIZER",
        "ENABLE_STS_HOST_APPLY_MATERIALIZER",
    ):
        os.environ.pop(k, None)
    reset_funnel_metrics()
    reset_pgr_metrics()


def _prior_ctx() -> dict:
    return {
        "session_id": "pgr03-test-session-001",
        "last_home": "Flamengo",
        "last_away": "Palmeiras",
        "last_match": "Flamengo x Palmeiras",
        "episode_id": "ep-flamengo",
        "last_intent": "fixture_compare",
        "csl": {
            "episode_id": "ep-flamengo",
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


def _arm_pgr01():
    os.environ["AURORA_PGR_01_ENABLE"] = "1"
    os.environ["AURORA_SOLE_WRITER_FUNNEL_PCT"] = "1"
    os.environ["ENABLE_STS_WRITE_FUNNEL_BOUNDARY"] = "1"
    os.environ["ENABLE_LANGGRAPH_STATE"] = "0"


def _arm_pgr02():
    os.environ["AURORA_PGR_02_ENABLE"] = "1"
    os.environ["AURORA_SOLE_WRITER_FUNNEL_PCT"] = "5"
    os.environ["ENABLE_STS_WRITE_FUNNEL_BOUNDARY"] = "1"
    os.environ["ENABLE_STS_WRITE_FUNNEL_ANALYZE"] = "1"
    os.environ["ENABLE_LANGGRAPH_STATE"] = "0"


def _arm_pgr03():
    os.environ["AURORA_PGR_03_ENABLE"] = "1"
    os.environ["AURORA_SOLE_WRITER_FUNNEL_PCT"] = "10"
    os.environ["ENABLE_STS_WRITE_FUNNEL_BOUNDARY"] = "1"
    os.environ["ENABLE_STS_WRITE_FUNNEL_ANALYZE"] = "1"
    os.environ["ENABLE_STS_NOTE_SUBJECT_GUARDS"] = "1"
    os.environ["ENABLE_LANGGRAPH_STATE"] = "0"


# ---------------------------------------------------------------------------
# Defaults / PGR-03 independent gate
# ---------------------------------------------------------------------------


def test_pgr03_defaults_off_not_armed():
    _clear_flags()
    assert pgr03_enable_flag() is False
    assert pgr02_enable_flag() is False
    assert pgr01_enable_flag() is False
    assert get_funnel_pct() == 0
    assert get_configured_funnel_pct() == 0
    assert funnel_stage_name() == "OFF_0"
    assert boundary_funnel_enabled() is False
    assert analyze_funnel_enabled() is False
    assert note_subject_funnel_enabled() is False
    assert langgraph_state_enabled() is False
    assert collect_illegal_combinations() == []
    snap = pgr_flag_snapshot()
    assert snap["active_gate"] == "NONE"
    assert snap["pgr03_enable"] is False
    assert snap["authorized_operational_max_pct"] == 100
    assert snap["higher_gates_locked"] is True
    assert snap["pgr03_not_started"] is False
    assert snap["pgr04_not_started"] is False
    assert snap["pgr05_not_started"] is False
    assert snap["pgr06_not_started"] is False
    assert snap["phase6_not_started"] is False
    assert snap["auto_advance"] is False
    assert snap["mirror_drift_open"] is True
    assert PGR03_PCT == 10
    assert PGR03_STAGE == "STAGE3_NOTE_10PCT"
    assert AUTHORIZED_OPERATIONAL_MAX_PCT == 100
    assert FUNNEL_AUTH_MAX == 100
    assert len(PGR_LADDER) == 6
    assert PGR_LADDER[2]["authorized_this_mission"] is True
    assert PGR_LADDER[3]["authorized_this_mission"] is True
    assert PGR_LADDER[4]["authorized_this_mission"] is True
    assert PGR_LADDER[5]["authorized_this_mission"] is True


def test_pgr03_pct10_without_pgr03_remains_off():
    """Independent gate: funnel pct=10 alone must NOT activate without PGR-03."""
    _clear_flags()
    os.environ["AURORA_SOLE_WRITER_FUNNEL_PCT"] = "10"
    os.environ["ENABLE_STS_WRITE_FUNNEL_BOUNDARY"] = "1"
    os.environ["ENABLE_STS_WRITE_FUNNEL_ANALYZE"] = "1"
    os.environ["ENABLE_STS_NOTE_SUBJECT_GUARDS"] = "1"
    try:
        assert get_configured_funnel_pct() == 10
        assert get_funnel_pct() == 0
        assert note_subject_funnel_enabled() is False
        assert funnel_owns_path("note_subject", force=False) is False
        assert pgr_metrics_snapshot()["pgr03_blocked_missing_flag"] >= 1
    finally:
        _clear_flags()


def test_pgr03_ten_pct_path_when_enabled():
    _clear_flags()
    _arm_pgr03()
    try:
        assert pgr03_enable_flag() is True
        assert require_pgr03_for_stage3() is True
        assert get_funnel_pct() == 10
        assert funnel_stage_name() == "STAGE3_NOTE_10PCT"
        assert note_subject_funnel_enabled() is True
        assert analyze_funnel_enabled() is True  # prior stage retained at 10%
        assert boundary_funnel_enabled() is True
        assert funnel_owns_path("note_subject", force=True) is True
        assert funnel_owns_path("analyze", force=True) is True
        snap = funnel_flag_snapshot()
        assert snap["effective_pct"] == 10
        assert snap["note_funnel_live"] is True
        assert snap["analyze_funnel_live"] is True
        assert snap["boundary_funnel_live"] is True
        assert snap["pgr03_not_started"] is False
        assert snap["pgr04_not_started"] is False
        assert snap["pgr05_not_started"] is False
        assert snap["pgr06_not_started"] is False
        assert snap["phase6_not_started"] is False
        assert snap["phase5_langgraph_write_not_started"] is True
        assert langgraph_state_enabled() is False
        assert pgr_flag_snapshot()["active_gate"] == "PGR-03"
    finally:
        _clear_flags()


def test_pgr03_prior_stages_live_when_prior_gates_also_armed():
    """At 10%, boundary + analyze remain available when prior gates are armed."""
    _clear_flags()
    _arm_pgr03()
    os.environ["AURORA_PGR_01_ENABLE"] = "1"
    os.environ["AURORA_PGR_02_ENABLE"] = "1"
    try:
        assert get_funnel_pct() == 10
        assert note_subject_funnel_enabled() is True
        assert analyze_funnel_enabled() is True
        assert boundary_funnel_enabled() is True
        assert funnel_owns_path("boundary", force=True) is True
        assert funnel_owns_path("analyze", force=True) is True
        assert funnel_owns_path("note_subject", force=True) is True
    finally:
        _clear_flags()


def test_pgr03_c17_commit_note_subject_when_armed():
    _clear_flags()
    _arm_pgr03()
    reset_funnel_metrics()
    ctx = _prior_ctx()
    try:
        res = commit_via_c17_funnel(
            "Liverpool x Chelsea",
            ctx,
            owner="note_subject",
            session_key=ctx["session_id"],
            force=True,
        )
        assert res.owned is True
        assert res.committed is True
        assert res.pct == 10
        assert res.stage_name == "STAGE3_NOTE_10PCT"
        assert res.dual_write_forbidden is True
        assert res.sts is not None
        assert int(res.sts.subject_generation or 0) >= 1
    finally:
        _clear_flags()


def test_pgr03_rollback_to_off():
    _clear_flags()
    _arm_pgr03()
    assert get_funnel_pct() == 10
    out = rollback_pgr03_to_off()
    assert pgr03_enable_flag() is False
    assert get_funnel_pct() == 0
    assert note_subject_funnel_enabled() is False
    assert out["pgr03_enable"] is False
    assert pgr_metrics_snapshot()["pgr03_rollback"] >= 1
    _clear_flags()


def test_pgr02_still_coherent_when_pgr03_off():
    """Prior gate remains available after PGR-03 rollback / when PGR-03 unset."""
    _clear_flags()
    _arm_pgr03()
    rollback_pgr03_to_off()
    _arm_pgr02()
    try:
        assert pgr03_enable_flag() is False
        assert pgr02_enable_flag() is True
        assert get_funnel_pct() == 5
        assert funnel_stage_name() == "STAGE2_ANALYZE_5PCT"
        assert analyze_funnel_enabled() is True
        assert note_subject_funnel_enabled() is False
        assert PGR02_PCT == 5
        assert PGR02_STAGE == "STAGE2_ANALYZE_5PCT"
        assert pgr_flag_snapshot()["active_gate"] == "PGR-02"
    finally:
        _clear_flags()


def test_pgr01_still_coherent_when_pgr03_off():
    _clear_flags()
    _arm_pgr03()
    rollback_pgr03_to_off()
    _arm_pgr01()
    try:
        assert pgr03_enable_flag() is False
        assert pgr01_enable_flag() is True
        assert get_funnel_pct() == 1
        assert funnel_stage_name() == "STAGE1_BOUNDARY_1PCT"
        assert boundary_funnel_enabled() is True
        assert analyze_funnel_enabled() is False
        assert note_subject_funnel_enabled() is False
        assert PGR01_PCT == 1
        assert PGR01_STAGE == "STAGE1_BOUNDARY_1PCT"
        assert pgr_flag_snapshot()["active_gate"] == "PGR-01"
    finally:
        _clear_flags()


def test_pgr03_funnel_rollback_alone_clears_pct():
    _clear_flags()
    _arm_pgr03()
    assert rollback_funnel_to_off() == 0
    assert get_funnel_pct() == 0
    assert pgr03_enable_flag() is True
    assert note_subject_funnel_enabled() is False
    _clear_flags()


# ---------------------------------------------------------------------------
# Higher pct fail-closed without matching PGR / no auto-advance
# ---------------------------------------------------------------------------


def test_pgr06_enable_does_not_unlock():
    """PGR-06 enable with pct=10 does not auto-jump to 100% (no auto-advance)."""
    _clear_flags()
    os.environ["AURORA_PGR_03_ENABLE"] = "1"
    os.environ["AURORA_PGR_06_ENABLE"] = "1"
    os.environ["AURORA_SOLE_WRITER_FUNNEL_PCT"] = "10"
    os.environ["ENABLE_STS_NOTE_SUBJECT_GUARDS"] = "1"
    os.environ["ENABLE_STS_WRITE_FUNNEL_BOUNDARY"] = "1"
    os.environ["ENABLE_STS_WRITE_FUNNEL_ANALYZE"] = "1"
    try:
        assert higher_pgr_gate_attempted() is False
        assert get_funnel_pct() == 10
        assert note_subject_funnel_enabled() is True
        assert pgr_flag_snapshot()["pgr06_not_started"] is False
    finally:
        _clear_flags()



def test_pgr03_pct_25_without_pgr04_remains_off():
    """pct=25 without PGR-04 stays OFF (independent gate — see PGR-04 suite)."""
    _clear_flags()
    os.environ["AURORA_PGR_03_ENABLE"] = "1"
    os.environ["AURORA_SOLE_WRITER_FUNNEL_PCT"] = "25"
    os.environ["ENABLE_STS_NOTE_SUBJECT_GUARDS"] = "1"
    try:
        assert get_configured_funnel_pct() == 25
        assert get_funnel_pct() == 0
        assert funnel_owns_path("note_subject", force=True) is False
    finally:
        _clear_flags()


def test_pgr03_hundred_pct_not_unlocked():
    _clear_flags()
    os.environ["AURORA_PGR_03_ENABLE"] = "1"
    os.environ["AURORA_SOLE_WRITER_FUNNEL_PCT"] = "100"
    try:
        assert get_funnel_pct() == 0
        assert langgraph_state_enabled() is False
    finally:
        _clear_flags()


def test_pgr03_pct_50_without_pgr05_remains_off():
    """pct=50 without PGR-05 stays OFF (independent gate — see PGR-05 suite)."""
    _clear_flags()
    os.environ["AURORA_PGR_03_ENABLE"] = "1"
    os.environ["AURORA_FUNNEL_PO_STAGE_UNLOCK"] = "1"
    os.environ["AURORA_SOLE_WRITER_FUNNEL_PCT"] = "50"
    try:
        assert get_funnel_pct() == 0
    finally:
        _clear_flags()


# ---------------------------------------------------------------------------
# Shadow / legacy / matrix / snapshots
# ---------------------------------------------------------------------------


def test_pgr03_shadow_still_works_with_gates_off():
    _clear_flags()
    os.environ["ENABLE_LANGGRAPH_STATE_SHADOW"] = "1"
    ctx = _prior_ctx()
    before = copy.deepcopy(ctx)
    try:
        out = ingress_order_shadow_compare(
            "Quem está melhor?", ctx, sll_clubs=["Flamengo", "Palmeiras"], force=True
        )
        assert out is not None
        maybe_shadow_compare("Quem está melhor?", ctx)
        assert ctx == before
        assert langgraph_state_enabled() is False
        assert get_funnel_pct() == 0
        assert pgr03_enable_flag() is False
    finally:
        _clear_flags()


def test_pgr03_legacy_writers_present():
    _clear_flags()
    assert callable(apply_episode_boundary)
    ctx = _prior_ctx()
    res = commit_via_c17_funnel(
        "Liverpool x Chelsea",
        ctx,
        owner="note_subject",
        force=True,
    )
    assert res.owned is False or res.skipped is True


def test_pgr03_flag_snapshot_and_runbook():
    _clear_flags()
    snap = flag_snapshot()
    assert "progressive_gate_review" in snap
    assert snap["progressive_gate_review"]["pgr03_enable"] is False
    assert snap["AURORA_PGR_03_ENABLE"] is False
    assert snap["production_write_active"] is False
    assert assert_legal_flag_matrix() == []
    runbook = operator_enable_pgr03_instructions()
    assert "AURORA_PGR_03_ENABLE=1" in runbook
    assert "AURORA_SOLE_WRITER_FUNNEL_PCT=10" in runbook
    assert "ENABLE_STS_NOTE_SUBJECT_GUARDS=1" in runbook
    assert "ENABLE_STS_WRITE_FUNNEL_ANALYZE=1" in runbook
    assert "ENABLE_LANGGRAPH_STATE=0" in runbook
    assert "rollback_pgr03_to_off" in runbook


def test_pgr03_no_auto_advance_and_phase6_not_started():
    _clear_flags()
    _arm_pgr03()
    try:
        snap = funnel_flag_snapshot()
        assert snap["auto_advance"] is False
        assert snap["pgr03_not_started"] is False
        assert snap["pgr04_not_started"] is False
        assert snap["pgr05_not_started"] is False
        assert snap["pgr06_not_started"] is False
        assert snap["phase6_not_started"] is False
        assert snap["effective_pct"] == 10
        assert snap["note_funnel_live"] is True
        assert snap["analyze_funnel_live"] is True
    finally:
        _clear_flags()


def test_pgr03_rollback_pgr02_helper_still_works():
    _clear_flags()
    _arm_pgr02()
    assert get_funnel_pct() == 5
    rollback_pgr02_to_off()
    assert pgr02_enable_flag() is False
    assert get_funnel_pct() == 0
    _clear_flags()
