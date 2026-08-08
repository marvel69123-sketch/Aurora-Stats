"""
Mission 043 Phase 6 — STABILIZATION ONLY (no features / no Activation).

Trust question: Can we trust EM before definitive activation / Final Acceptance?

Proves:
  - Defaults OFF; all Plan §8 flags OFF / pct 0
  - Rollback valid (PGR-06 + global kill)
  - Shadow intact
  - Progressive Extraction E1–E4 intact (capability; defaults OFF)
  - Progressive Gates PGR-01..06 intact (capability; defaults OFF)
  - Feature flags correct (no auto-advance)
  - Observability sufficient (snapshots / mirror probe)
  - Mirror drift probe wired (Mission 047 closes R-EM-01 when mirror synced)
  - No definitive Activation; Mission 044 Acceptance pending
  - Illegal matrix green at defaults
"""

from __future__ import annotations

import os

from src.execution_manager import (
    AUTHORIZED_HIGHEST_GATE,
    AUTHORIZED_OPERATIONAL_MAX_PCT,
    assert_legal_em_flag_matrix,
    assess_em_mirror_drift,
    em_flag_snapshot,
    em_flags_all_off,
    em_pgr_flag_snapshot,
    maybe_em_shadow_observe,
    pgr06_enable_flag,
    rollback_em_pgr06_to_off,
    shadow_enabled,
)
from src.execution_manager.flags import (
    EM_BOOL_FLAGS,
    collect_illegal_em_combinations,
    rollback_em_all_off,
)
from src.execution_manager.progressive_gate import (
    get_effective_em_activation_pct,
    operator_enable_em_pgr06_instructions,
    reset_em_pgr_metrics,
)
from src.execution_manager.shadow import reset_shadow_metrics


def _clear_em_flags() -> None:
    rollback_em_all_off()
    for k in list(EM_BOOL_FLAGS) + [
        "EM_ACTIVATION_PCT",
        "CLAIM_EM_SHADOW_IS_SOLE_PATH",
        "ENABLE_EM_DUAL_RUN_HARNESS",
        "ENABLE_EM_CM_WRITE",
        "ENABLE_EM_SHADOW_CM_ELIGIBLE",
        "ENABLE_EM_SHADOW_PEER_COPILOT_ENGINE",
        "ENABLE_EM_PGR_AUTO_ADVANCE",
        "AURORA_EM_CLAIM_REPO_DEFAULTS_ON",
        "AURORA_EM_ASSERT_DEFAULTS_OFF_ONLY",
    ]:
        os.environ.pop(k, None)
    reset_em_pgr_metrics()
    reset_shadow_metrics()


def _arm_pgr06() -> None:
    os.environ["ENABLE_EM_PGR_06"] = "1"
    os.environ["EM_ACTIVATION_PCT"] = "100"
    os.environ["ENABLE_EXECUTION_MANAGER"] = "1"
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    os.environ["ENABLE_EM_DUAL_RUN_HARNESS"] = "1"
    os.environ["ENABLE_EM_PIPELINE_ANALYZE"] = "1"


def test_stabilization_defaults_off():
    _clear_em_flags()
    assert em_flags_all_off() is True
    assert get_effective_em_activation_pct() == 0
    assert pgr06_enable_flag() is False
    snap = em_flag_snapshot()
    assert snap["em_flags_all_off"] is True
    assert snap["phase6_stabilization_complete"] is True
    assert snap["phase6_stabilization_not_started"] is False
    assert snap["definitive_activation_not_started"] is True
    assert snap["progressive_gate_review"]["phase6_stabilization_complete"] is True
    assert snap["progressive_gate_review"]["auto_advance"] is False
    assert AUTHORIZED_HIGHEST_GATE == "PGR-06"
    assert AUTHORIZED_OPERATIONAL_MAX_PCT == 100


def test_stabilization_feature_flags_arming_path_documented():
    _clear_em_flags()
    _arm_pgr06()
    try:
        assert pgr06_enable_flag() is True
        assert get_effective_em_activation_pct() == 100
        snap = em_flag_snapshot()
        assert snap["phase6_stabilization_complete"] is True
        assert snap["definitive_activation_not_started"] is True
        assert snap["legacy_copilot_engine_present"] is True
        runbook = operator_enable_em_pgr06_instructions()
        assert "ENABLE_EM_PGR_06=1" in runbook
        assert "Mission 044" in runbook or "definitive Activation" in runbook
    finally:
        _clear_em_flags()


def test_stabilization_full_rollback_valid():
    _clear_em_flags()
    _arm_pgr06()
    assert get_effective_em_activation_pct() == 100
    out = rollback_em_pgr06_to_off()
    assert pgr06_enable_flag() is False
    assert get_effective_em_activation_pct() == 0
    assert isinstance(out, dict)
    rollback_em_all_off()
    assert em_flags_all_off() is True
    _clear_em_flags()


def test_stabilization_shadow_intact():
    _clear_em_flags()
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    try:
        assert shadow_enabled() is True
        maybe_em_shadow_observe(
            legacy_payload={"intent": "analyze"},
            pipeline_id="analyze",
            session_id="shadow-stab-043",
            entities={},
        )
        assert get_effective_em_activation_pct() == 0
        assert collect_illegal_em_combinations() == []
    finally:
        _clear_em_flags()


def test_stabilization_extraction_and_gates_intact():
    _clear_em_flags()
    snap = em_flag_snapshot()
    assert snap["phase4_extraction_complete"] is True
    assert snap["phase4_stage1_thin_reports"] is True
    assert snap["phase4_stage2_live"] is True
    assert snap["phase4_stage3_analyze"] is True
    assert snap["phase4_stage4_live_team"] is True
    assert snap["phase5_pgr01"] is True
    assert snap["phase5_pgr06"] is True
    assert snap["phase5_authorized_highest_gate"] == "PGR-06"
    # Defaults remain OFF
    assert snap["phase4_thin_defaults_off"] is True
    assert snap["phase4_live_defaults_off"] is True
    assert snap["phase4_analyze_defaults_off"] is True
    assert snap["phase4_live_team_defaults_off"] is True
    assert snap["phase5_pgr06_defaults_off"] is True


def test_stabilization_observability_sufficient():
    _clear_em_flags()
    snap = em_flag_snapshot()
    assert "progressive_gate_review" in snap
    assert "em_mirror_drift" in snap
    assert "illegal_violations" in snap
    pgr = em_pgr_flag_snapshot()
    assert "metrics" in pgr
    assert pgr["rollback_possible"] is True
    assert pgr["shadow_independent"] is True
    assert pgr["mirror_drift_open"] is False


def test_stabilization_mirror_drift_resolved_after_047():
    _clear_em_flags()
    probe = assess_em_mirror_drift()
    assert probe["deploy_sot"] == "artifacts/aurora/"
    assert probe["mirror_path"] == "aurora/"
    assert probe["sync_performed"] is False
    assert probe["definitive_activation_nogo_while_open"] is True
    assert probe["residual_id"] == "R-EM-01"
    # Mission 047: one-way sync SoT → aurora/ closes presence drift.
    assert probe["mirror_drift_open"] is False
    assert probe["disposition"] == "RESOLVED"
    assert probe["missing_in_mirror"] == []
    assert probe["missing_in_sot"] == []
    snap = em_flag_snapshot()
    assert snap["mirror_drift_open"] is False
    assert snap["em_mirror_drift"]["mirror_drift_open"] is False


def test_stabilization_no_definitive_activation():
    _clear_em_flags()
    _arm_pgr06()
    try:
        snap = em_flag_snapshot()
        assert snap["definitive_activation_not_started"] is True
        assert snap["progressive_gate_review"]["higher_gates_locked"] is True
        assert snap["progressive_gate_review"]["definitive_activation_not_started"] is True
        # Armed canary ≠ definitive full-env Activation / FA.
        assert snap["phase6_stabilization_complete"] is True
    finally:
        _clear_em_flags()


def test_stabilization_illegal_matrix_green_at_defaults():
    _clear_em_flags()
    assert collect_illegal_em_combinations() == []
    assert assert_legal_em_flag_matrix() == []
