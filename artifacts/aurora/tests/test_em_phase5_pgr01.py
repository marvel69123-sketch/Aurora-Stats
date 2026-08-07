"""
Mission 037 Phase 5 — Gated Activation EM PGR-01 (REGRA 25) ONLY.

Proves:
  - Repo default OFF / 0%; PGR-01 not armed
  - PGR-01 (1% / EM_STAGE1_SOLE_PATH_1PCT) path when explicitly flagged
  - pct > 1 fail-closed without higher PO unlock
  - PGR-02+ remain locked / not unlocked
  - Instant rollback to 0% / PGR-01 OFF
  - Shadow still works; pipeline flags remain DEFAULT OFF
  - Phase 4 extraction-only (pipeline ON, no activation posture) still 100%
  - No auto-advance; prior EM suites remain green under defaults OFF
"""

from __future__ import annotations

import os
from unittest.mock import patch

from src.execution_manager import (
    AUTHORIZED_HIGHEST_GATE,
    AUTHORIZED_OPERATIONAL_MAX_PCT,
    PGR01_PCT,
    PGR01_STAGE,
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
    require_em_pgr01,
    rollback_em_pgr01_to_off,
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
    operator_enable_em_pgr01_instructions,
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


# ---------------------------------------------------------------------------
# Defaults / PGR-01 independent gate
# ---------------------------------------------------------------------------


def test_pgr01_defaults_off_not_armed():
    _clear_em_flags()
    assert pgr01_enable_flag() is False
    assert get_configured_em_activation_pct() == 0
    assert get_effective_em_activation_pct() == 0
    assert effective_em_activation_pct() == 0
    assert em_activation_stage_name() == "OFF_0"
    assert em_flags_all_off() is True
    assert collect_illegal_em_combinations() == []
    snap = em_pgr_flag_snapshot()
    assert snap["active_gate"] == "NONE"
    assert snap["pgr01_enable"] is False
    assert snap["effective_pct"] == 0
    assert snap["higher_gates_locked"] is True
    assert snap["pgr02_not_started"] is False
    assert snap["pgr03_not_started"] is False
    assert snap["pgr04_not_started"] is False
    assert snap["pgr05_not_started"] is True
    assert snap["auto_advance"] is False
    assert snap["rollback_possible"] is True
    assert PGR01_PCT == 1
    assert PGR01_STAGE == "EM_STAGE1_SOLE_PATH_1PCT"
    assert AUTHORIZED_HIGHEST_GATE == "PGR-04"
    assert AUTHORIZED_OPERATIONAL_MAX_PCT == 25
    assert len(EM_PGR_LADDER) == 6
    flag_snap = em_flag_snapshot()
    assert flag_snap["phase5_pgr01"] is True
    assert flag_snap["phase5_pgr01_defaults_off"] is True
    assert flag_snap["phase5_pgr02_not_started"] is False
    assert flag_snap["phase5_pgr03_not_started"] is False
    assert flag_snap["phase5_pgr04_not_started"] is False
    assert flag_snap["phase5_pgr05_not_started"] is True
    assert flag_snap["progressive_gate_review"]["pgr01_enable"] is False


def test_pgr01_pct1_without_flag_remains_off():
    """Independent gate: EM_ACTIVATION_PCT=1 alone must NOT activate without PGR-01."""
    _clear_em_flags()
    os.environ["EM_ACTIVATION_PCT"] = "1"
    os.environ["ENABLE_EXECUTION_MANAGER"] = "1"
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    os.environ["ENABLE_EM_DUAL_RUN_HARNESS"] = "1"
    os.environ["ENABLE_EM_PIPELINE_ANALYZE"] = "1"
    try:
        assert get_configured_em_activation_pct() == 1
        assert get_effective_em_activation_pct() == 0
        assert require_em_pgr01() is False
        assert em_pipeline_may_route(True, "session-a") is False
        assert em_pgr_metrics_snapshot()["em_pgr01_blocked_missing_flag"] >= 1
        ids = {v["id"] for v in collect_illegal_em_combinations()}
        assert "I6" in ids
    finally:
        _clear_em_flags()


def test_pgr01_one_pct_path_when_enabled():
    _clear_em_flags()
    _arm_pgr01()
    try:
        assert pgr01_enable_flag() is True
        assert require_em_pgr01() is True
        assert get_effective_em_activation_pct() == 1
        assert em_activation_stage_name() == PGR01_STAGE
        assert collect_illegal_em_combinations() == []
        assert assert_legal_em_flag_matrix() == []
        snap = em_pgr_flag_snapshot()
        assert snap["effective_pct"] == 1
        assert snap["pgr02_not_started"] is False
        assert snap["pgr03_not_started"] is False
        assert snap["pgr04_not_started"] is False
        assert snap["pgr05_not_started"] is True
        assert snap["auto_advance"] is False
    finally:
        _clear_em_flags()


def test_pgr01_canary_bucket_deterministic():
    _clear_em_flags()
    _arm_pgr01()
    try:
        # force=True always selected
        assert in_em_canary_bucket("any", force=True) is True
        # Explicit pct edges
        assert in_em_canary_bucket("any", pct=0) is False
        assert in_em_canary_bucket("any", pct=100) is True
        # Deterministic for same session key at 1%
        a = in_em_canary_bucket("stable-em-pgr01-session", pct=1)
        b = in_em_canary_bucket("stable-em-pgr01-session", pct=1)
        assert a is b
        assert isinstance(a, bool)
        # With force routing helper
        assert em_pipeline_may_route(True, "x", force=True) is True
    finally:
        _clear_em_flags()


def test_pgr01_shim_canary_routes_or_legacy():
    _clear_em_flags()
    _arm_pgr01(pipeline="ENABLE_EM_PIPELINE_BANKROLL")
    legacy_calls = {"n": 0}

    def legacy():
        legacy_calls["n"] += 1
        return {"intent": "bankroll", "source": "legacy"}

    try:
        # force canary miss → legacy
        with patch(
            "src.execution_manager.progressive_gate.in_em_canary_bucket",
            return_value=False,
        ):
            out = em_thin_or_legacy("bankroll", legacy, session_id="miss")
            assert out["source"] == "legacy"
            assert legacy_calls["n"] == 1

        # force canary hit → EM path (may still fail-open to legacy if EM incomplete)
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
                # Either EM payload or fail-open legacy — must not crash
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
        assert pgr01_enable_flag() is False
    finally:
        _clear_em_flags()


# ---------------------------------------------------------------------------
# Higher pct / PGR-05 locked / independent prior gates
# ---------------------------------------------------------------------------


def test_pgr01_pct5_without_pgr02_remains_off():
    """Independent gate: pct=5 with only PGR-01 stays OFF (needs PGR-02)."""
    _clear_em_flags()
    os.environ["ENABLE_EM_PGR_01"] = "1"
    os.environ["EM_ACTIVATION_PCT"] = "5"
    os.environ["ENABLE_EXECUTION_MANAGER"] = "1"
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    os.environ["ENABLE_EM_DUAL_RUN_HARNESS"] = "1"
    try:
        assert get_configured_em_activation_pct() == 5
        assert get_effective_em_activation_pct() == 0
        assert em_pipeline_may_route(True, "s") is False
        assert em_pgr_metrics_snapshot()["em_pgr02_blocked_missing_flag"] >= 1
    finally:
        _clear_em_flags()


def test_pgr01_hundred_pct_not_unlocked():
    _clear_em_flags()
    os.environ["ENABLE_EM_PGR_01"] = "1"
    os.environ["EM_ACTIVATION_PCT"] = "100"
    try:
        assert get_effective_em_activation_pct() == 0
        assert em_pgr_metrics_snapshot()["em_activation_blocked_high_pct"] >= 1
    finally:
        _clear_em_flags()


def test_pgr05_not_unlocked_when_flag_set():
    """PGR-05 flag armed during PGR-04 plateau → higher gate blocked."""
    _clear_em_flags()
    _arm_pgr01()
    os.environ["ENABLE_EM_PGR_05"] = "1"
    try:
        assert higher_em_pgr_gate_attempted() is True
        assert get_effective_em_activation_pct() == 0
        assert require_em_pgr01() is False
        assert em_pgr_flag_snapshot()["pgr05_not_started"] is True
        assert em_pgr_metrics_snapshot()["em_pgr_higher_gate_blocked"] >= 1
    finally:
        _clear_em_flags()


def test_pgr05_enable_alone_does_not_unlock_50pct():
    _clear_em_flags()
    os.environ["ENABLE_EM_PGR_05"] = "1"
    os.environ["EM_ACTIVATION_PCT"] = "50"
    os.environ["ENABLE_EXECUTION_MANAGER"] = "1"
    try:
        assert get_effective_em_activation_pct() == 0
        assert higher_em_pgr_gate_attempted() is True
    finally:
        _clear_em_flags()


# ---------------------------------------------------------------------------
# Rollback / Shadow / matrix / runbook
# ---------------------------------------------------------------------------


def test_rollback_pgr01_to_off():
    _clear_em_flags()
    _arm_pgr01()
    assert get_effective_em_activation_pct() == 1
    out = rollback_em_pgr01_to_off()
    assert pgr01_enable_flag() is False
    assert get_effective_em_activation_pct() == 0
    assert out["pgr01_enable"] is False
    assert em_pgr_metrics_snapshot()["em_pgr01_rollback"] >= 1
    # Shadow / master may still be on — rollback is PGR-scoped
    assert shadow_enabled() is True
    _clear_em_flags()


def test_shadow_still_works_with_pgr01_off():
    _clear_em_flags()
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    try:
        assert shadow_enabled() is True
        assert pgr01_enable_flag() is False
        assert get_effective_em_activation_pct() == 0
        # observe helper must not raise
        maybe_em_shadow_observe(
            legacy_payload={"intent": "analyze"},
            pipeline_id="analyze",
            session_id="shadow-pgr01",
            entities={},
        )
    finally:
        _clear_em_flags()


def test_no_auto_advance_and_runbook():
    _clear_em_flags()
    _arm_pgr01()
    try:
        snap = em_flag_snapshot()
        assert snap["auto_advance"] is False
        assert snap["phase5_pgr02_not_started"] is False
        assert snap["phase5_pgr03_not_started"] is False
        assert snap["phase5_pgr04_not_started"] is False
        assert snap["phase5_pgr05_not_started"] is True
        assert snap["EM_ACTIVATION_PCT_EFFECTIVE"] == 1
        runbook = operator_enable_em_pgr01_instructions()
        assert "ENABLE_EM_PGR_01=1" in runbook
        assert "EM_ACTIVATION_PCT=1" in runbook
        assert "ENABLE_EXECUTION_MANAGER=1" in runbook
        assert "PGR-05" in runbook or "ENABLE_EM_PGR_05" in runbook
        assert "rollback_em_pgr01_to_off" in runbook
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
        "ENABLE_EXECUTION_MANAGER",
    ):
        assert snap["flags"][name] is False
