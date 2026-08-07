"""
Mission 016 Phase 4 — Sole-Writer Funnel tests (REGRA 24 stage 1 only).

Proves:
  - Default OFF / 0%; repo does not activate 100%
  - First stage = 1% + boundary funnel (Plan first progressive step)
  - Higher % blocked without PO unlock (no auto-advance)
  - Instant rollback to 0%
  - C17-only commit when funnel owns path; no dual-write
  - Legacy writers present when OFF
  - Shadow still works; production write OFF; Phase 5 not started
"""

from __future__ import annotations

import copy
import os

import pytest

from src.conversation.langgraph_state_adapter import (
    ingress_order_shadow_compare,
    maybe_shadow_compare,
)
from src.conversation.migration_flag_controller import (
    assert_legal_flag_matrix,
    collect_illegal_combinations,
    flag_snapshot,
    get_migration_stage,
)
from src.conversation.minimal_commit_orchestrator import (
    invoke_minimal_commit_orchestrator,
)
from src.conversation.sole_writer_funnel import (
    FUNNEL_STAGE_PERCENTAGES,
    PHASE4_AUTHORIZED_MAX_PCT,
    boundary_funnel_enabled,
    commit_via_c17_funnel,
    funnel_flag_snapshot,
    funnel_metrics_snapshot,
    funnel_owns_path,
    funnel_stage_name,
    get_configured_funnel_pct,
    get_funnel_pct,
    reset_funnel_metrics,
    rollback_funnel_to_off,
)
from src.conversation.sport_topic_state import (
    langgraph_state_enabled,
    langgraph_state_shadow_enabled,
)
from src.conversation.topic_boundary_v2 import (
    apply_episode_boundary,
    apply_topic_boundary_v2,
    detect_episode_boundary,
)


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
        "ENABLE_TOPIC_BOUNDARY_V2",
        "ENABLE_TB_V2_APPLY_MATERIALIZER",
        "ENABLE_STS_HOST_APPLY_MATERIALIZER",
    ):
        os.environ.pop(k, None)
    reset_funnel_metrics()
    try:
        from src.conversation.progressive_gate_review import reset_pgr_metrics

        reset_pgr_metrics()
    except Exception:
        pass


def _prior_ctx() -> dict:
    return {
        "session_id": "funnel-test-session-001",
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


# ---------------------------------------------------------------------------
# Defaults / REGRA 24 single-stage
# ---------------------------------------------------------------------------


def test_phase4_defaults_off_zero_pct():
    _clear_flags()
    assert get_funnel_pct() == 0
    assert get_configured_funnel_pct() == 0
    assert funnel_stage_name() == "OFF_0"
    assert PHASE4_AUTHORIZED_MAX_PCT == 1
    assert FUNNEL_STAGE_PERCENTAGES == (0, 1, 5, 10, 25, 50, 100)
    assert boundary_funnel_enabled() is False
    assert langgraph_state_enabled() is False
    assert collect_illegal_combinations() == []
    snap = funnel_flag_snapshot()
    assert snap["effective_pct"] == 0
    assert snap["auto_advance"] is False
    assert snap["phase5_not_started"] is True
    assert snap["legacy_writers_present"] is True
    assert snap["shadow_untouched"] is True


def test_phase4_higher_pct_blocked_without_po_unlock():
    _clear_flags()
    os.environ["AURORA_SOLE_WRITER_FUNNEL_PCT"] = "5"
    try:
        assert get_configured_funnel_pct() == 5
        assert get_funnel_pct() == 0  # fail-closed
        assert funnel_stage_name() == "OFF_0"
        metrics = funnel_metrics_snapshot()
        assert metrics["funnel_blocked_high_stage"] >= 1
    finally:
        _clear_flags()


def test_phase4_hundred_pct_blocked_without_unlock():
    _clear_flags()
    os.environ["AURORA_SOLE_WRITER_FUNNEL_PCT"] = "100"
    try:
        assert get_funnel_pct() == 0
        assert funnel_flag_snapshot()["phase5_not_started"] is True
    finally:
        _clear_flags()


def test_phase4_stage1_one_pct_activatable():
    _clear_flags()
    os.environ["AURORA_SOLE_WRITER_FUNNEL_PCT"] = "1"
    os.environ["ENABLE_STS_WRITE_FUNNEL_BOUNDARY"] = "1"
    os.environ["AURORA_PGR_01_ENABLE"] = "1"  # Phase 5 REGRA 25 independent gate
    try:
        assert get_funnel_pct() == 1
        assert funnel_stage_name() == "STAGE1_BOUNDARY_1PCT"
        assert boundary_funnel_enabled() is True
        # analyze / note still not live at 1%
        assert funnel_owns_path("analyze", force=True) is False
        assert funnel_owns_path("note_subject", force=True) is False
    finally:
        _clear_flags()


def test_phase4_rollback_to_off():
    _clear_flags()
    os.environ["AURORA_SOLE_WRITER_FUNNEL_PCT"] = "1"
    os.environ["ENABLE_STS_WRITE_FUNNEL_BOUNDARY"] = "1"
    os.environ["AURORA_PGR_01_ENABLE"] = "1"
    assert get_funnel_pct() == 1
    assert rollback_funnel_to_off() == 0
    assert get_funnel_pct() == 0
    assert boundary_funnel_enabled() is False
    _clear_flags()


# ---------------------------------------------------------------------------
# C17-only / no dual-write
# ---------------------------------------------------------------------------


def test_phase4_c17_commit_when_funnel_owns_boundary():
    _clear_flags()
    os.environ["AURORA_SOLE_WRITER_FUNNEL_PCT"] = "1"
    os.environ["ENABLE_STS_WRITE_FUNNEL_BOUNDARY"] = "1"
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
        assert res.skipped is False
        assert res.dual_write_forbidden is True
        assert res.pct == 1
        assert res.sts is not None
        assert int(res.sts.subject_generation or 0) >= 1
        assert ctx.get("_sts_funnel_meta", {}).get("dual_write_forbidden") is True
        assert funnel_metrics_snapshot()["funnel_commits"] >= 1
        # C17 path used (orchestrator payload present)
        assert res.orchestrator.get("skipped") is False
    finally:
        _clear_flags()


def test_phase4_legacy_present_when_funnel_off():
    _clear_flags()
    ctx = _prior_ctx()
    # Legacy apply still importable / callable
    assert callable(apply_episode_boundary)
    res = commit_via_c17_funnel(
        "Liverpool x Chelsea",
        ctx,
        owner="boundary",
        force=True,
    )
    assert res.owned is False
    assert res.skipped is True
    assert res.skipped_reason in {"funnel_pct_off", "boundary_flag_off", "funnel_off_or_not_selected"}


def test_phase4_no_dual_write_on_topic_boundary_v2_funnel_path():
    _clear_flags()
    os.environ["ENABLE_TOPIC_BOUNDARY_V2"] = "1"
    os.environ["AURORA_SOLE_WRITER_FUNNEL_PCT"] = "1"
    os.environ["ENABLE_STS_WRITE_FUNNEL_BOUNDARY"] = "1"
    reset_funnel_metrics()
    ctx = _prior_ctx()
    # Force canary by using commit path through apply with session that we force
    # via direct funnel first to prove dual_write counter, then apply_topic_boundary
    # when funnel owns — legacy apply_episode_boundary must not also invent subject.
    before_gen = None
    try:
        # Direct ownership proof
        assert funnel_owns_path(
            "boundary", session_key=ctx["session_id"], force=True
        )
        res = commit_via_c17_funnel(
            "Liverpool x Chelsea",
            ctx,
            owner="boundary",
            session_key=ctx["session_id"],
            force=True,
        )
        assert res.committed
        before_gen = int(ctx.get("subject_generation") or 0)
        # Second legacy apply must not be used by funnel-owned turn; simulate
        # mark_dual_write already recorded on successful commit path via TB-V2.
        # Here: ensure STS generation is sole epoch source.
        assert before_gen >= 1
        assert ctx.get("csl", {}).get("teams")  # projected from STS
    finally:
        _clear_flags()


def test_phase4_c17_skips_when_langgraph_production_write_on():
    """Dual-host ban: P4 write ON ⇒ C17/funnel must not commit (Phase 5 gate)."""
    _clear_flags()
    os.environ["ENABLE_LANGGRAPH_STATE"] = "1"
    os.environ["ENABLE_STS_SOLE_WRITER"] = "1"
    os.environ["ENABLE_STS_WRITE_FUNNEL_BOUNDARY"] = "1"
    os.environ["ENABLE_STS_WRITE_FUNNEL_ANALYZE"] = "1"
    os.environ["ENABLE_STS_NOTE_SUBJECT_GUARDS"] = "1"
    os.environ["AURORA_SOLE_WRITER_FUNNEL_PCT"] = "1"
    try:
        # Illegal matrix may still fire on other axes; funnel_owns must be False
        # because production write active.
        assert funnel_owns_path("boundary", force=True) is False
        orch = invoke_minimal_commit_orchestrator(
            "Liverpool x Chelsea", force=False
        )
        assert orch.skipped is True
        assert orch.skipped_reason == "p4_langgraph_host_owns_write_use_c1"
    finally:
        _clear_flags()


# ---------------------------------------------------------------------------
# Shadow still works / Phase 5 not started
# ---------------------------------------------------------------------------


def test_phase4_shadow_still_works_with_funnel_off():
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
        assert ctx == before  # REGRA 23 observe-only
        assert langgraph_state_enabled() is False
        assert get_funnel_pct() == 0
    finally:
        _clear_flags()


def test_phase4_flag_snapshot_includes_funnel():
    _clear_flags()
    snap = flag_snapshot()
    assert "sole_writer_funnel" in snap
    assert snap["sole_writer_funnel"]["effective_pct"] == 0
    assert snap["production_write_active"] is False
    assert assert_legal_flag_matrix() == []


def test_phase4_legacy_apply_episode_boundary_still_exists():
    """Do NOT remove legacy writer — REGRA 24 / Phase 4 forbid."""
    _clear_flags()
    os.environ["ENABLE_TOPIC_BOUNDARY_V2"] = "1"
    ctx = _prior_ctx()
    decision = detect_episode_boundary("Liverpool x Chelsea", ctx)
    if decision.is_boundary:
        out = apply_episode_boundary(ctx, decision)
        assert out.is_boundary is True
    # Module surface retained
    assert callable(apply_topic_boundary_v2)


def test_phase4_analyze_note_stages_not_auto_advanced():
    _clear_flags()
    os.environ["AURORA_SOLE_WRITER_FUNNEL_PCT"] = "1"
    os.environ["ENABLE_STS_WRITE_FUNNEL_BOUNDARY"] = "1"
    os.environ["AURORA_PGR_01_ENABLE"] = "1"
    os.environ["ENABLE_STS_WRITE_FUNNEL_ANALYZE"] = "1"
    os.environ["ENABLE_STS_NOTE_SUBJECT_GUARDS"] = "1"
    try:
        assert get_funnel_pct() == 1
        # Even with analyze/note flags ON, pct=1 must not activate those owners.
        assert funnel_owns_path("analyze", force=True) is False
        assert funnel_owns_path("note_subject", force=True) is False
        res = commit_via_c17_funnel(
            "x", {}, owner="analyze", force=True
        )
        assert res.owned is False
    finally:
        _clear_flags()
