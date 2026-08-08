"""
Mission 038 Phase 5 — Gated Activation EM PGR-02 (REGRA 25) ONLY.

Proves:
  - Repo default OFF / 0%; PGR-02 not armed
  - PGR-02 (5% / EM_STAGE2_SOLE_PATH_5PCT) path when explicitly flagged
  - pct > 5 fail-closed without higher PO unlock
  - PGR-03+ remain locked / not unlocked
  - Instant rollback to 0% / PGR-02 OFF; PGR-01 still re-armable
  - Shadow still works; pipeline flags remain DEFAULT OFF
  - Phase 4 extraction-only (pipeline ON, no activation posture) still 100%
  - No auto-advance; prior EM / PGR-01 suites remain green under defaults OFF
"""

from __future__ import annotations

import os
from unittest.mock import patch

from src.execution_manager import (
    AUTHORIZED_HIGHEST_GATE,
    AUTHORIZED_OPERATIONAL_MAX_PCT,
    PGR01_PCT,
    PGR01_STAGE,
    PGR02_PCT,
    PGR02_STAGE,
    assert_legal_em_flag_matrix,
    effective_em_activation_pct,
    em_flag_snapshot,
    em_flags_all_off,
    em_pipeline_may_route,
    em_pgr_flag_snapshot,
    em_thin_or_legacy,
    get_effective_em_activation_pct,
    maybe_em_shadow_observe,
    pgr01_enable_flag,
    pgr02_enable_flag,
    require_em_pgr01,
    require_em_pgr02,
    rollback_em_pgr01_to_off,
    rollback_em_pgr02_to_off,
    shadow_enabled,
)
from src.execution_manager.flags import (
    EM_BOOL_FLAGS,
    collect_illegal_em_combinations,
    rollback_em_all_off,
)
from src.execution_manager.progressive_gate import (
    EM_PGR_LADDER,
    em_activation_stage_name,
    em_pgr_metrics_snapshot,
    get_configured_em_activation_pct,
    higher_em_pgr_gate_attempted,
    in_em_canary_bucket,
    operator_enable_em_pgr02_instructions,
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


def _arm_pgr01(*, pipeline: str | None = "ENABLE_EM_PIPELINE_ANALYZE") -> None:
    os.environ["ENABLE_EM_PGR_01"] = "1"
    os.environ["EM_ACTIVATION_PCT"] = "1"
    os.environ["ENABLE_EXECUTION_MANAGER"] = "1"
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    os.environ["ENABLE_EM_DUAL_RUN_HARNESS"] = "1"
    if pipeline:
        os.environ[pipeline] = "1"


def _arm_pgr02(*, pipeline: str | None = "ENABLE_EM_PIPELINE_ANALYZE") -> None:
    os.environ["ENABLE_EM_PGR_02"] = "1"
    os.environ["EM_ACTIVATION_PCT"] = "5"
    os.environ["ENABLE_EXECUTION_MANAGER"] = "1"
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    os.environ["ENABLE_EM_DUAL_RUN_HARNESS"] = "1"
    if pipeline:
        os.environ[pipeline] = "1"


# ---------------------------------------------------------------------------
# Defaults / PGR-02 independent gate
# ---------------------------------------------------------------------------


def test_pgr02_defaults_off_not_armed():
    _clear_em_flags()
    assert pgr02_enable_flag() is False
    assert pgr01_enable_flag() is False
    assert get_configured_em_activation_pct() == 0
    assert get_effective_em_activation_pct() == 0
    assert effective_em_activation_pct() == 0
    assert em_activation_stage_name() == "OFF_0"
    assert em_flags_all_off() is True
    assert collect_illegal_em_combinations() == []
    snap = em_pgr_flag_snapshot()
    assert snap["active_gate"] == "NONE"
    assert snap["pgr02_enable"] is False
    assert snap["effective_pct"] == 0
    assert snap["higher_gates_locked"] is True
    assert snap["pgr02_not_started"] is False
    assert snap["pgr03_not_started"] is False
    assert snap["pgr04_not_started"] is False
    assert snap["pgr05_not_started"] is False
    assert snap["pgr06_not_started"] is False
    assert snap["auto_advance"] is False
    assert snap["rollback_possible"] is True
    assert PGR02_PCT == 5
    assert PGR02_STAGE == "EM_STAGE2_SOLE_PATH_5PCT"
    assert AUTHORIZED_HIGHEST_GATE == "PGR-06"
    assert AUTHORIZED_OPERATIONAL_MAX_PCT == 100
    assert len(EM_PGR_LADDER) == 6
    assert EM_PGR_LADDER[0]["authorized_this_mission"] is True
    assert EM_PGR_LADDER[1]["authorized_this_mission"] is True
    assert EM_PGR_LADDER[2]["authorized_this_mission"] is True
    assert EM_PGR_LADDER[3]["authorized_this_mission"] is True
    assert EM_PGR_LADDER[4]["authorized_this_mission"] is True
    assert EM_PGR_LADDER[5]["authorized_this_mission"] is True
    flag_snap = em_flag_snapshot()
    assert flag_snap["phase5_pgr02"] is True
    assert flag_snap["phase5_pgr02_defaults_off"] is True
    assert flag_snap["phase5_pgr02_not_started"] is False
    assert flag_snap["phase5_pgr03_not_started"] is False
    assert flag_snap["phase5_pgr04_not_started"] is False
    assert flag_snap["phase5_pgr05_not_started"] is False
    assert flag_snap["phase5_pgr06_not_started"] is False
    assert flag_snap["phase5_authorized_highest_gate"] == "PGR-06"
    assert flag_snap["phase5_authorized_max_pct"] == 100
    assert flag_snap["progressive_gate_review"]["pgr02_enable"] is False


def test_pgr02_pct5_without_flag_remains_off():
    """Independent gate: EM_ACTIVATION_PCT=5 alone must NOT activate without PGR-02."""
    _clear_em_flags()
    os.environ["EM_ACTIVATION_PCT"] = "5"
    os.environ["ENABLE_EXECUTION_MANAGER"] = "1"
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    os.environ["ENABLE_EM_DUAL_RUN_HARNESS"] = "1"
    os.environ["ENABLE_EM_PIPELINE_ANALYZE"] = "1"
    try:
        assert get_configured_em_activation_pct() == 5
        assert get_effective_em_activation_pct() == 0
        assert require_em_pgr02() is False
        assert em_pipeline_may_route(True, "session-a") is False
        assert em_pgr_metrics_snapshot()["em_pgr02_blocked_missing_flag"] >= 1
        ids = {v["id"] for v in collect_illegal_em_combinations()}
        assert "I6" in ids
    finally:
        _clear_em_flags()


def test_pgr02_five_pct_path_when_enabled():
    _clear_em_flags()
    _arm_pgr02()
    try:
        assert pgr02_enable_flag() is True
        assert require_em_pgr02() is True
        assert get_effective_em_activation_pct() == 5
        assert em_activation_stage_name() == PGR02_STAGE
        assert collect_illegal_em_combinations() == []
        assert assert_legal_em_flag_matrix() == []
        snap = em_pgr_flag_snapshot()
        assert snap["effective_pct"] == 5
        assert snap["active_gate"] == "PGR-02"
        assert snap["pgr03_not_started"] is False
        assert snap["pgr04_not_started"] is False
        assert snap["pgr05_not_started"] is False
        assert snap["pgr06_not_started"] is False
        assert snap["auto_advance"] is False
    finally:
        _clear_em_flags()


def test_pgr02_canary_bucket_deterministic():
    _clear_em_flags()
    _arm_pgr02()
    try:
        assert in_em_canary_bucket("any", force=True) is True
        assert in_em_canary_bucket("any", pct=0) is False
        assert in_em_canary_bucket("any", pct=100) is True
        a = in_em_canary_bucket("stable-em-pgr02-session", pct=5)
        b = in_em_canary_bucket("stable-em-pgr02-session", pct=5)
        assert a is b
        assert isinstance(a, bool)
        assert em_pipeline_may_route(True, "x", force=True) is True
    finally:
        _clear_em_flags()


def test_pgr02_shim_canary_routes_or_legacy():
    _clear_em_flags()
    _arm_pgr02(pipeline="ENABLE_EM_PIPELINE_BANKROLL")
    legacy_calls = {"n": 0}

    def legacy():
        legacy_calls["n"] += 1
        return {"intent": "bankroll", "source": "legacy"}

    try:
        with patch(
            "src.execution_manager.progressive_gate.in_em_canary_bucket",
            return_value=False,
        ):
            out = em_thin_or_legacy("bankroll", legacy, session_id="miss")
            assert out["source"] == "legacy"
            assert legacy_calls["n"] == 1

        with patch(
            "src.execution_manager.progressive_gate.in_em_canary_bucket",
            return_value=True,
        ):
            with patch(
                "src.execution_manager.ports.ProductionDbReadPort.learning_stats",
                return_value={
                    "bankroll": 1000,
                    "units": 10,
                    "stop_loss": 0,
                    "stop_win": 0,
                },
            ):
                out2 = em_thin_or_legacy("bankroll", legacy, session_id="hit")
                assert isinstance(out2, dict)
                assert "intent" in out2 or "source" in out2
    finally:
        _clear_em_flags()


def test_phase4_extraction_without_activation_posture_still_full():
    """Pipeline flag alone (no master/PGR/pct) keeps Phase 4 100% extraction path."""
    _clear_em_flags()
    os.environ["ENABLE_EM_PIPELINE_BANKROLL"] = "1"
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    try:
        assert em_pipeline_may_route(True, "sess") is True
        assert get_effective_em_activation_pct() == 0
        assert pgr02_enable_flag() is False
    finally:
        _clear_em_flags()


# ---------------------------------------------------------------------------
# Higher pct / PGR-06 locked / PGR-01 still available
# ---------------------------------------------------------------------------


def test_pgr02_pct_above_5_without_pgr03_fail_closed():
    """pct=10 with only PGR-02 stays OFF (independent PGR-03 gate)."""
    _clear_em_flags()
    os.environ["ENABLE_EM_PGR_02"] = "1"
    os.environ["EM_ACTIVATION_PCT"] = "10"
    os.environ["ENABLE_EXECUTION_MANAGER"] = "1"
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    os.environ["ENABLE_EM_DUAL_RUN_HARNESS"] = "1"
    try:
        assert get_configured_em_activation_pct() == 10
        assert get_effective_em_activation_pct() == 0
        assert em_pipeline_may_route(True, "s") is False
        assert em_pgr_metrics_snapshot()["em_pgr03_blocked_missing_flag"] >= 1
    finally:
        _clear_em_flags()


def test_pgr02_hundred_pct_not_unlocked():
    _clear_em_flags()
    os.environ["ENABLE_EM_PGR_02"] = "1"
    os.environ["EM_ACTIVATION_PCT"] = "100"
    try:
        assert get_effective_em_activation_pct() == 0
        assert em_pgr_metrics_snapshot()["em_pgr06_blocked_missing_flag"] >= 1
    finally:
        _clear_em_flags()


def test_pgr06_enable_does_not_auto_advance_from_pgr02():
    """PGR-06 enable with pct=5 stays at 5% (no auto-advance to 100%)."""
    _clear_em_flags()
    _arm_pgr02()
    os.environ["ENABLE_EM_PGR_06"] = "1"
    try:
        assert higher_em_pgr_gate_attempted() is False
        assert get_effective_em_activation_pct() == 5
        assert require_em_pgr02() is True
        assert em_pgr_flag_snapshot()["pgr06_not_started"] is False
        assert em_pgr_flag_snapshot()["active_gate"] == "PGR-06"
    finally:
        _clear_em_flags()


def test_pgr06_enable_alone_does_not_unlock_without_pct():
    _clear_em_flags()
    os.environ["ENABLE_EM_PGR_06"] = "1"
    os.environ["ENABLE_EXECUTION_MANAGER"] = "1"
    try:
        assert get_effective_em_activation_pct() == 0
        assert higher_em_pgr_gate_attempted() is False
    finally:
        _clear_em_flags()


def test_pgr01_still_rearmable_when_pgr02_off():
    """Prior gate PGR-01 remains available after PGR-02 rollback / when PGR-02 unset."""
    _clear_em_flags()
    _arm_pgr02()
    rollback_em_pgr02_to_off()
    _arm_pgr01()
    try:
        assert pgr02_enable_flag() is False
        assert pgr01_enable_flag() is True
        assert require_em_pgr01() is True
        assert get_effective_em_activation_pct() == 1
        assert em_activation_stage_name() == PGR01_STAGE
        assert PGR01_PCT == 1
        assert em_pgr_flag_snapshot()["active_gate"] == "PGR-01"
    finally:
        _clear_em_flags()


def test_pgr01_pct5_without_pgr02_remains_off():
    """pct=5 with only PGR-01 armed stays OFF (independent PGR-02 gate)."""
    _clear_em_flags()
    os.environ["ENABLE_EM_PGR_01"] = "1"
    os.environ["EM_ACTIVATION_PCT"] = "5"
    os.environ["ENABLE_EXECUTION_MANAGER"] = "1"
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    os.environ["ENABLE_EM_DUAL_RUN_HARNESS"] = "1"
    try:
        assert get_configured_em_activation_pct() == 5
        assert get_effective_em_activation_pct() == 0
        assert em_pgr_metrics_snapshot()["em_pgr02_blocked_missing_flag"] >= 1
    finally:
        _clear_em_flags()


# ---------------------------------------------------------------------------
# Rollback / Shadow / matrix / runbook
# ---------------------------------------------------------------------------


def test_rollback_pgr02_to_off():
    _clear_em_flags()
    _arm_pgr02()
    assert get_effective_em_activation_pct() == 5
    out = rollback_em_pgr02_to_off()
    assert pgr02_enable_flag() is False
    assert get_effective_em_activation_pct() == 0
    assert out["pgr02_enable"] is False
    assert em_pgr_metrics_snapshot()["em_pgr02_rollback"] >= 1
    assert shadow_enabled() is True
    _clear_em_flags()


def test_shadow_still_works_with_pgr02_off():
    _clear_em_flags()
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    try:
        assert shadow_enabled() is True
        assert pgr02_enable_flag() is False
        assert get_effective_em_activation_pct() == 0
        maybe_em_shadow_observe(
            legacy_payload={"intent": "analyze"},
            pipeline_id="analyze",
            session_id="shadow-pgr02",
            entities={},
        )
    finally:
        _clear_em_flags()


def test_no_auto_advance_and_runbook():
    _clear_em_flags()
    _arm_pgr02()
    try:
        snap = em_flag_snapshot()
        assert snap["auto_advance"] is False
        assert snap["phase5_pgr03_not_started"] is False
        assert snap["phase5_pgr04_not_started"] is False
        assert snap["phase5_pgr05_not_started"] is False
        assert snap["phase5_pgr06_not_started"] is False
        assert snap["EM_ACTIVATION_PCT_EFFECTIVE"] == 5
        runbook = operator_enable_em_pgr02_instructions()
        assert "ENABLE_EM_PGR_02=1" in runbook
        assert "EM_ACTIVATION_PCT=5" in runbook
        assert "ENABLE_EXECUTION_MANAGER=1" in runbook
        assert "PGR-06" in runbook or "ENABLE_EM_PGR_06" in runbook
        assert "rollback_em_pgr02_to_off" in runbook
    finally:
        _clear_em_flags()


def test_pipeline_flags_remain_default_off_in_repo():
    _clear_em_flags()
    snap = em_flag_snapshot()
    for name in (
        "ENABLE_EM_PIPELINE_BANKROLL",
        "ENABLE_EM_PIPELINE_LEARNING",
        "ENABLE_EM_PIPELINE_KNOWLEDGE",
        "ENABLE_EM_PIPELINE_LIVE",
        "ENABLE_EM_PIPELINE_ANALYZE",
        "ENABLE_EM_PIPELINE_LIVE_TEAM",
        "ENABLE_EM_PGR_01",
        "ENABLE_EM_PGR_02",
        "ENABLE_EXECUTION_MANAGER",
    ):
        assert snap["flags"][name] is False


def test_rollback_pgr01_helper_still_works():
    _clear_em_flags()
    _arm_pgr01()
    assert get_effective_em_activation_pct() == 1
    rollback_em_pgr01_to_off()
    assert pgr01_enable_flag() is False
    assert get_effective_em_activation_pct() == 0
    _clear_em_flags()
