"""
Mission 016 Phase 6 — STABILIZATION ONLY (no features / no Activation).

Trust question: Can we trust this new brain before turning it on definitively?

Proves:
  - Defaults OFF; ENABLE_LANGGRAPH_STATE OFF
  - Rollback valid (funnel + PGR-06)
  - Shadow intact
  - Sole Writer consistent
  - Feature flags correct (PGR ladder; no auto-advance)
  - Observability sufficient (snapshots / metrics / mirror probe)
  - Mirror drift OPEN and honestly documented (FINDING-024 / IO9)
  - No definitive Activation; Mission 017 Acceptance pending
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
    assess_cm_mirror_drift,
    collect_illegal_combinations,
    deploy_sts_modules_present,
    flag_snapshot,
)
from src.conversation.progressive_gate_review import (
    AUTHORIZED_OPERATIONAL_MAX_PCT,
    pgr_flag_snapshot,
    pgr06_enable_flag,
    reset_pgr_metrics,
    rollback_pgr06_to_off,
)
from src.conversation.sole_writer_funnel import (
    commit_via_c17_funnel,
    funnel_flag_snapshot,
    get_funnel_pct,
    reset_funnel_metrics,
    rollback_funnel_to_off,
)
from src.conversation.sport_topic_state import langgraph_state_enabled


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


def _arm_pgr06():
    os.environ["AURORA_PGR_06_ENABLE"] = "1"
    os.environ["AURORA_SOLE_WRITER_FUNNEL_PCT"] = "100"
    os.environ["ENABLE_STS_WRITE_FUNNEL_BOUNDARY"] = "1"
    os.environ["ENABLE_STS_WRITE_FUNNEL_ANALYZE"] = "1"
    os.environ["ENABLE_STS_NOTE_SUBJECT_GUARDS"] = "1"
    os.environ["ENABLE_LANGGRAPH_STATE"] = "0"


def _prior_ctx():
    return {
        "episode_id": "ep-stab",
        "active_fixture_id": "fix-1",
        "teams": ["Liverpool", "Chelsea"],
        "subject_generation": 1,
    }


def test_stabilization_defaults_off_and_write_off():
    _clear_flags()
    assert langgraph_state_enabled() is False
    assert get_funnel_pct() == 0
    snap = flag_snapshot()
    assert snap["ENABLE_LANGGRAPH_STATE"] is False
    assert snap["production_write_active"] is False
    assert snap["phase6_stabilization_complete"] is True
    assert snap["definitive_activation_not_started"] is True
    assert snap["progressive_gate_review"]["phase6_not_started"] is False
    assert snap["progressive_gate_review"]["phase6_stabilization_complete"] is True
    assert snap["progressive_gate_review"]["auto_advance"] is False
    assert AUTHORIZED_OPERATIONAL_MAX_PCT == 100


def test_stabilization_feature_flags_arming_path_documented():
    _clear_flags()
    _arm_pgr06()
    try:
        assert pgr06_enable_flag() is True
        assert get_funnel_pct() == 100
        assert langgraph_state_enabled() is False
        funnel = funnel_flag_snapshot()
        assert funnel["phase6_stabilization_complete"] is True
        assert funnel["definitive_activation_not_started"] is True
        assert funnel["legacy_writers_present"] is True
        pgr = pgr_flag_snapshot()
        assert "Mission 017" in pgr["operator_enable_pgr06_runbook"] or (
            "definitive Activation" in pgr["operator_enable_pgr06_runbook"]
        )
        assert "ENABLE_LANGGRAPH_STATE=0" in pgr["operator_enable_pgr06_runbook"]
    finally:
        _clear_flags()


def test_stabilization_full_rollback_valid():
    _clear_flags()
    _arm_pgr06()
    assert get_funnel_pct() == 100
    out = rollback_pgr06_to_off()
    assert pgr06_enable_flag() is False
    assert get_funnel_pct() == 0
    assert langgraph_state_enabled() is False
    assert isinstance(out, dict)
    # funnel helper also clears
    os.environ["AURORA_SOLE_WRITER_FUNNEL_PCT"] = "50"
    rollback_funnel_to_off()
    assert get_funnel_pct() == 0
    _clear_flags()


def test_stabilization_shadow_intact():
    _clear_flags()
    os.environ["ENABLE_LANGGRAPH_STATE_SHADOW"] = "1"
    os.environ["ENABLE_LANGGRAPH_STATE"] = "0"
    try:
        ctx = _prior_ctx()
        # Shadow helpers remain callable; must not mutate as production write.
        maybe_shadow_compare("Liverpool x Chelsea", copy.deepcopy(ctx))
        ingress_order_shadow_compare("Liverpool x Chelsea", copy.deepcopy(ctx))
        assert langgraph_state_enabled() is False
        assert assert_legal_flag_matrix() == []
    finally:
        _clear_flags()


def test_stabilization_sole_writer_consistent():
    _clear_flags()
    _arm_pgr06()
    try:
        funnel = funnel_flag_snapshot()
        assert funnel["note_funnel_live"] is True
        assert funnel["boundary_funnel_live"] is True
        assert funnel["analyze_funnel_live"] is True
        assert funnel["effective_pct"] == 100
        res = commit_via_c17_funnel(
            "Liverpool x Chelsea",
            _prior_ctx(),
            owner="note_subject",
            force=False,
        )
        assert res is not None
        assert collect_illegal_combinations() == []
    finally:
        _clear_flags()


def test_stabilization_observability_sufficient():
    _clear_flags()
    snap = flag_snapshot()
    assert "sole_writer_funnel" in snap
    assert "progressive_gate_review" in snap
    assert "cm_mirror_drift" in snap
    assert snap["deploy_sts_modules_present"] is True
    assert deploy_sts_modules_present() is True
    pgr = snap["progressive_gate_review"]
    assert "metrics" in pgr
    assert pgr["legacy_writers_present"] is True
    assert pgr["mirror_drift_open"] is False


def test_stabilization_mirror_drift_resolved_after_047():
    _clear_flags()
    probe = assess_cm_mirror_drift()
    assert probe["deploy_sot"] == "artifacts/aurora/"
    assert probe["mirror_path"] == "aurora/"
    assert probe["sync_performed"] is False
    assert probe["definitive_activation_nogo_while_open"] is True
    # Mission 047: one-way sync SoT → aurora/ closes presence drift.
    assert probe["mirror_drift_open"] is False
    assert probe["disposition"] == "RESOLVED"
    assert probe["missing_in_mirror"] == []
    snap = flag_snapshot()
    assert snap["mirror_drift_open"] is False
    assert snap["cm_mirror_drift"]["mirror_drift_open"] is False


def test_stabilization_no_definitive_activation():
    _clear_flags()
    _arm_pgr06()
    try:
        assert langgraph_state_enabled() is False
        snap = flag_snapshot()
        assert snap["production_write_active"] is False
        assert snap["definitive_activation_not_started"] is True
        assert snap["progressive_gate_review"]["higher_gates_locked"] is True
        assert snap["progressive_gate_review"]["production_langgraph_write_required"] is False
    finally:
        _clear_flags()


def test_stabilization_illegal_matrix_green_at_defaults():
    _clear_flags()
    assert collect_illegal_combinations() == []
    assert assert_legal_flag_matrix() == []
