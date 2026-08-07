"""
Mission 016 Phase 5 — Gated Activation PGR-01 (REGRA 25).

Proves:
  - Repo default OFF / 0%; PGR-01 not armed
  - PGR-01 (1% / STAGE1_BOUNDARY_1PCT) path when explicitly flagged
  - Higher PGR gates (PGR-04+) remain locked / no unlock
  - Instant rollback to 0% / PGR-01 OFF
  - Shadow still works; legacy writers present
  - ENABLE_LANGGRAPH_STATE remains OFF (no full prod write / Phase 6)
  - No auto-advance

Note: PGR-02 (5%) is authorized in a separate gate module/tests
(test_context_manager_phase5_pgr02_016.py). This suite keeps PGR-01 coherence.
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
    PGR01_PCT,
    PGR01_STAGE,
    PGR_LADDER,
    higher_pgr_gate_attempted,
    operator_enable_pgr01_instructions,
    pgr01_enable_flag,
    pgr_flag_snapshot,
    pgr_metrics_snapshot,
    require_pgr01_for_stage1,
    reset_pgr_metrics,
    rollback_pgr01_to_off,
)
from src.conversation.sole_writer_funnel import (
    boundary_funnel_enabled,
    commit_via_c17_funnel,
    funnel_flag_snapshot,
    funnel_owns_path,
    funnel_stage_name,
    get_configured_funnel_pct,
    get_funnel_pct,
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
        "session_id": "pgr01-test-session-001",
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


# ---------------------------------------------------------------------------
# Defaults / PGR-01 independent gate
# ---------------------------------------------------------------------------


def test_phase5_defaults_off_pgr01_not_armed():
    _clear_flags()
    assert pgr01_enable_flag() is False
    assert get_funnel_pct() == 0
    assert get_configured_funnel_pct() == 0
    assert funnel_stage_name() == "OFF_0"
    assert boundary_funnel_enabled() is False
    assert langgraph_state_enabled() is False
    assert collect_illegal_combinations() == []
    snap = pgr_flag_snapshot()
    assert snap["active_gate"] == "NONE"
    assert snap["pgr01_enable"] is False
    assert snap["higher_gates_locked"] is True
    assert snap["pgr03_not_started"] is False
    assert snap["pgr04_not_started"] is False
    assert snap["pgr05_not_started"] is False
    assert snap["pgr06_not_started"] is True
    assert snap["phase6_not_started"] is True
    assert snap["auto_advance"] is False
    assert snap["mirror_drift_open"] is True
    assert PGR01_PCT == 1
    assert PGR01_STAGE == "STAGE1_BOUNDARY_1PCT"
    assert len(PGR_LADDER) == 6


def test_phase5_pct1_without_pgr01_remains_off():
    """Independent gate: funnel pct=1 alone must NOT activate without PGR-01."""
    _clear_flags()
    os.environ["AURORA_SOLE_WRITER_FUNNEL_PCT"] = "1"
    os.environ["ENABLE_STS_WRITE_FUNNEL_BOUNDARY"] = "1"
    try:
        assert get_configured_funnel_pct() == 1
        assert get_funnel_pct() == 0
        assert boundary_funnel_enabled() is False
        assert funnel_owns_path("boundary", force=False) is False
        assert pgr_metrics_snapshot()["pgr01_blocked_missing_flag"] >= 1
    finally:
        _clear_flags()


def test_phase5_pgr01_one_pct_path_when_enabled():
    _clear_flags()
    _arm_pgr01()
    try:
        assert pgr01_enable_flag() is True
        assert require_pgr01_for_stage1() is True
        assert get_funnel_pct() == 1
        assert funnel_stage_name() == "STAGE1_BOUNDARY_1PCT"
        assert boundary_funnel_enabled() is True
        assert funnel_owns_path("analyze", force=True) is False
        assert funnel_owns_path("note_subject", force=True) is False
        snap = funnel_flag_snapshot()
        assert snap["effective_pct"] == 1
        assert snap["pgr03_not_started"] is False
        assert snap["pgr04_not_started"] is False
        assert snap["pgr05_not_started"] is False
        assert snap["pgr06_not_started"] is True
        assert snap["phase6_not_started"] is True
        assert snap["phase5_langgraph_write_not_started"] is True
        assert langgraph_state_enabled() is False
    finally:
        _clear_flags()


def test_phase5_pgr01_c17_commit_when_armed():
    _clear_flags()
    _arm_pgr01()
    reset_funnel_metrics()
    ctx = _prior_ctx()
    try:
        res = commit_via_c17_funnel(
            "Liverpool x Chelsea",
            ctx,
            owner="boundary",
            session_key=ctx["session_id"],
            force=True,
        )
        assert res.owned is True
        assert res.committed is True
        assert res.pct == 1
        assert res.stage_name == "STAGE1_BOUNDARY_1PCT"
        assert res.dual_write_forbidden is True
        assert res.sts is not None
        assert int(res.sts.subject_generation or 0) >= 1
    finally:
        _clear_flags()


def test_phase5_rollback_pgr01_to_off():
    _clear_flags()
    _arm_pgr01()
    assert get_funnel_pct() == 1
    out = rollback_pgr01_to_off()
    assert pgr01_enable_flag() is False
    assert get_funnel_pct() == 0
    assert boundary_funnel_enabled() is False
    assert out["pgr01_enable"] is False
    assert pgr_metrics_snapshot()["pgr01_rollback"] >= 1
    _clear_flags()


def test_phase5_funnel_rollback_alone_clears_pct():
    _clear_flags()
    _arm_pgr01()
    assert rollback_funnel_to_off() == 0
    assert get_funnel_pct() == 0
    # PGR flag may still be on, but without pct effective stays 0
    assert pgr01_enable_flag() is True
    assert boundary_funnel_enabled() is False
    _clear_flags()


# ---------------------------------------------------------------------------
# Higher gates locked / no PGR-06+ via PGR-01 suite
# ---------------------------------------------------------------------------


def test_phase5_pgr06_enable_does_not_unlock_pgr01_path():
    _clear_flags()
    os.environ["AURORA_PGR_01_ENABLE"] = "1"
    os.environ["AURORA_PGR_06_ENABLE"] = "1"
    os.environ["AURORA_SOLE_WRITER_FUNNEL_PCT"] = "1"
    os.environ["ENABLE_STS_WRITE_FUNNEL_BOUNDARY"] = "1"
    try:
        assert higher_pgr_gate_attempted() is True
        # Higher gate attempt fail-closes live path this mission
        assert get_funnel_pct() == 0
        assert boundary_funnel_enabled() is False
        assert pgr_flag_snapshot()["pgr06_not_started"] is True
    finally:
        _clear_flags()


def test_phase5_higher_pct_still_blocked_without_pgr02():
    """pct=5 without PGR-02 remains OFF (independent gate — see PGR-02 suite)."""
    _clear_flags()
    os.environ["AURORA_PGR_01_ENABLE"] = "1"
    os.environ["AURORA_SOLE_WRITER_FUNNEL_PCT"] = "5"
    os.environ["ENABLE_STS_WRITE_FUNNEL_BOUNDARY"] = "1"
    os.environ["ENABLE_STS_WRITE_FUNNEL_ANALYZE"] = "1"
    try:
        assert get_configured_funnel_pct() == 5
        assert get_funnel_pct() == 0
        assert funnel_owns_path("analyze", force=True) is False
    finally:
        _clear_flags()


def test_phase5_hundred_pct_not_unlocked():
    _clear_flags()
    os.environ["AURORA_PGR_01_ENABLE"] = "1"
    os.environ["AURORA_SOLE_WRITER_FUNNEL_PCT"] = "100"
    try:
        assert get_funnel_pct() == 0
        assert langgraph_state_enabled() is False
    finally:
        _clear_flags()


# ---------------------------------------------------------------------------
# Shadow / legacy / matrix / snapshots
# ---------------------------------------------------------------------------


def test_phase5_shadow_still_works_with_pgr01_off():
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
        assert pgr01_enable_flag() is False
    finally:
        _clear_flags()


def test_phase5_legacy_writers_present():
    _clear_flags()
    assert callable(apply_episode_boundary)
    ctx = _prior_ctx()
    res = commit_via_c17_funnel(
        "Liverpool x Chelsea",
        ctx,
        owner="boundary",
        force=True,
    )
    # Without boundary flag / PGR, force alone with cleared flags → skipped
    assert res.owned is False or res.skipped is True


def test_phase5_flag_snapshot_includes_pgr():
    _clear_flags()
    snap = flag_snapshot()
    assert "progressive_gate_review" in snap
    assert snap["progressive_gate_review"]["pgr01_enable"] is False
    assert snap["AURORA_PGR_01_ENABLE"] is False
    assert snap["production_write_active"] is False
    assert assert_legal_flag_matrix() == []
    runbook = operator_enable_pgr01_instructions()
    assert "AURORA_PGR_01_ENABLE=1" in runbook
    assert "AURORA_SOLE_WRITER_FUNNEL_PCT=1" in runbook
    assert "ENABLE_LANGGRAPH_STATE=0" in runbook


def test_phase5_no_auto_advance_and_phase6_not_started():
    _clear_flags()
    _arm_pgr01()
    try:
        snap = funnel_flag_snapshot()
        assert snap["auto_advance"] is False
        assert snap["pgr03_not_started"] is False
        assert snap["pgr04_not_started"] is False
        assert snap["pgr05_not_started"] is False
        assert snap["pgr06_not_started"] is True
        assert snap["phase6_not_started"] is True
        assert snap["effective_pct"] == 1
        # Must not unlock analyze/note via PGR-01 alone
        assert snap["analyze_funnel_live"] is False
        assert snap["note_funnel_live"] is False
    finally:
        _clear_flags()
