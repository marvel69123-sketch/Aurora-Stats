"""
Mission 031 Phase 2 — Execution Manager Infrastructure unit tests.

Flags OFF by default. No Router wiring. No Shadow dual-run. No user-path change.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from src.execution_manager import (
    ANALYZE_FROZEN_ENGINE_ORDER,
    ExecutionManager,
    ExecutionMode,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    FixtureQuality,
    IllegalEmFlagMatrixError,
    PipelineId,
    StepRunner,
    assert_legal_em_flag_matrix,
    em_flag_snapshot,
    em_flags_all_off,
)
from src.execution_manager.contracts import (
    ANALYZE_STEP_ORDER,
    AbortReason,
)
from src.execution_manager.flags import (
    EM_BOOL_FLAGS,
    collect_illegal_em_combinations,
    rollback_em_all_off,
    rollback_em_pgrXX_to_off,
    rollback_em_shadow_off,
    rollback_em_sole_path_off,
)
from src.execution_manager.ports import (
    InertBudgetGate,
    InertFetchFixture,
    PortBundle,
)
from src.execution_manager.registry import (
    ensure_default_registrations,
    registered_pipeline_ids,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SOT = REPO_ROOT / "artifacts" / "aurora"
EM_PKG = SOT / "src" / "execution_manager"
ROUTER = SOT / "src" / "routers" / "copilot_unified_router.py"

FORBIDDEN_EM_TOKENS = (
    "_save_analysis_context",
    "attach_match_card",
    "begin_request",
    "end_request",
)


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


# ---------------------------------------------------------------------------
# Import / registration / defaults
# ---------------------------------------------------------------------------


def test_em_package_importable_and_registered():
    _clear_em_flags()
    assert EM_PKG.is_dir()
    ensure_default_registrations()
    ids = set(registered_pipeline_ids())
    assert ids == {
        PipelineId.ANALYZE,
        PipelineId.LIVE,
        PipelineId.BANKROLL,
        PipelineId.LEARNING,
        PipelineId.KNOWLEDGE,
        PipelineId.LIVE_TEAM_ANALYZE,
    }
    assert em_flags_all_off() is True
    assert collect_illegal_em_combinations() == []
    assert assert_legal_em_flag_matrix() == []


def test_flags_default_off_snapshot():
    _clear_em_flags()
    snap = em_flag_snapshot()
    assert snap["em_flags_all_off"] is True
    assert snap["shadow_enabled"] is False
    assert snap["sole_path_master_enabled"] is False
    assert snap["EM_ACTIVATION_PCT"] == 0.0
    assert snap["phase3_shadow_observe_only"] is True
    assert snap["phase3_shadow_default_off"] is True
    # Phase 4 Stage 1+2 capability exists; thin/live pipeline defaults remain OFF.
    assert snap["phase4_extraction_not_started"] is False
    assert snap["phase4_stage1_thin_reports"] is True
    assert snap["phase4_stage2_not_started"] is False
    assert snap["phase4_stage2_live"] is True
    assert snap["phase4_thin_defaults_off"] is True
    assert snap["phase4_live_defaults_off"] is True
    assert snap["phase4_stage3_not_started"] is False
    assert snap["phase4_stage3_analyze"] is True
    assert snap["phase4_analyze_defaults_off"] is True
    for name in EM_BOOL_FLAGS:
        assert snap["flags"][name] is False


# ---------------------------------------------------------------------------
# Illegal matrix I1–I8
# ---------------------------------------------------------------------------


def test_illegal_i1_sole_path_without_shadow():
    _clear_em_flags()
    os.environ["ENABLE_EXECUTION_MANAGER"] = "1"
    try:
        ids = {v["id"] for v in collect_illegal_em_combinations()}
        assert "I1" in ids
        with pytest.raises(IllegalEmFlagMatrixError):
            assert_legal_em_flag_matrix(raise_on_illegal=True)
    finally:
        _clear_em_flags()


def test_illegal_i2_shadow_plus_sole_without_harness():
    _clear_em_flags()
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    os.environ["ENABLE_EXECUTION_MANAGER"] = "1"
    try:
        ids = {v["id"] for v in collect_illegal_em_combinations()}
        assert "I2" in ids
    finally:
        _clear_em_flags()


def test_illegal_i3_cm_write_flag():
    _clear_em_flags()
    os.environ["ENABLE_EM_CM_WRITE"] = "1"
    try:
        ids = {v["id"] for v in collect_illegal_em_combinations()}
        assert "I3" in ids
    finally:
        _clear_em_flags()


def test_illegal_i4_shadow_cm_eligible():
    _clear_em_flags()
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    os.environ["ENABLE_EM_SHADOW_CM_ELIGIBLE"] = "1"
    try:
        ids = {v["id"] for v in collect_illegal_em_combinations()}
        assert "I4" in ids
    finally:
        _clear_em_flags()


def test_illegal_i5_copilot_engine_shadow_peer():
    _clear_em_flags()
    os.environ["ENABLE_EM_SHADOW_PEER_COPILOT_ENGINE"] = "1"
    try:
        ids = {v["id"] for v in collect_illegal_em_combinations()}
        assert "I5" in ids
    finally:
        _clear_em_flags()


def test_illegal_i6_pct_without_pgr():
    _clear_em_flags()
    os.environ["EM_ACTIVATION_PCT"] = "5"
    try:
        ids = {v["id"] for v in collect_illegal_em_combinations()}
        assert "I6" in ids
    finally:
        _clear_em_flags()


def test_illegal_i7_pgr_auto_advance():
    _clear_em_flags()
    os.environ["ENABLE_EM_PGR_AUTO_ADVANCE"] = "1"
    try:
        ids = {v["id"] for v in collect_illegal_em_combinations()}
        assert "I7" in ids
    finally:
        _clear_em_flags()


def test_illegal_i8_claim_repo_defaults_on():
    _clear_em_flags()
    os.environ["AURORA_EM_CLAIM_REPO_DEFAULTS_ON"] = "1"
    try:
        ids = {v["id"] for v in collect_illegal_em_combinations()}
        assert "I8" in ids
    finally:
        _clear_em_flags()


def test_rollback_helpers():
    _clear_em_flags()
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    os.environ["ENABLE_EXECUTION_MANAGER"] = "1"
    os.environ["ENABLE_EM_PIPELINE_ANALYZE"] = "1"
    os.environ["ENABLE_EM_PGR_01"] = "1"
    os.environ["EM_ACTIVATION_PCT"] = "1"
    rollback_em_shadow_off()
    assert os.environ.get("ENABLE_EXECUTION_MANAGER_SHADOW") == "0"
    rollback_em_sole_path_off()
    assert os.environ.get("ENABLE_EXECUTION_MANAGER") == "0"
    assert os.environ.get("ENABLE_EM_PIPELINE_ANALYZE") == "0"
    assert os.environ.get("EM_ACTIVATION_PCT") == "0"
    rollback_em_pgrXX_to_off(1)
    assert os.environ.get("ENABLE_EM_PGR_01") == "0"
    rollback_em_all_off()
    assert em_flags_all_off() is True


# ---------------------------------------------------------------------------
# Contracts / frozen order
# ---------------------------------------------------------------------------


def test_closed_status_and_fixture_quality_enums():
    assert {s.value for s in ExecutionStatus} == {"Completed", "Failed", "Interrupted"}
    assert {q.value for q in FixtureQuality} == {
        "VALID",
        "PARTIAL",
        "INVALID",
        "VALID_LOCATED",
    }


def test_analyze_a3_a10_order_frozen_snapshot():
    assert ANALYZE_FROZEN_ENGINE_ORDER == (
        "methodology",
        "learning",
        "confidence",
        "market",
        "methodology_v1",
        "decision_center",
        "knowledge_consult",
        "intelligence",
    )
    assert ANALYZE_STEP_ORDER[3:11] == ANALYZE_FROZEN_ENGINE_ORDER


# ---------------------------------------------------------------------------
# Step Runner stubs — §5.2.1 golden 1–3
# ---------------------------------------------------------------------------


def _req(
    *,
    run_id: str = "run-1",
    pipeline: str = "analyze",
    flags: dict | None = None,
    entities: dict | None = None,
) -> ExecutionRequest:
    return ExecutionRequest(
        run_id=run_id,
        pipeline_id=pipeline,
        session_id="sess-1",
        mode=ExecutionMode.DRY_RUN,
        entities=entities or {},
        flags=flags or {},
    )


def test_golden1_hard_abort_completed_blocked():
    """Fiction / unknown names, no fixture → HARD-ABORT → Completed + blocked."""
    _clear_em_flags()
    ports = PortBundle(
        fetch_fixture=InertFetchFixture(response={"fixture_id": 0, "found": False})
    )
    em = ExecutionManager(ports=ports)
    result = em.run(
        _req(
            flags={"integrity_outcome": "HARD_ABORT"},
            entities={"home": "FakeFC", "away": "NoClub"},
        )
    )
    assert result.status == ExecutionStatus.COMPLETED
    assert result.abort_reason == AbortReason.INTEGRITY_INVALID_HARD_ABORT.value
    assert result.fixture_quality == FixtureQuality.INVALID.value
    assert result.payload["fixture_quality"] == "INVALID"
    assert result.payload["entities"]["entity_invalid"] is True
    assert result.payload["best_markets"] == []
    assert result.payload["match_card"] is None
    a2 = next(t for t in result.step_traces if t.step_id == "integrity_gate")
    assert a2.status.value in {"failed", "terminal_gate"}
    # Engines must not run after HARD-ABORT
    engine_ids = {t.step_id for t in result.step_traces}
    assert "methodology" not in engine_ids


def test_golden2_soft_skip_engines_run():
    _clear_em_flags()
    ports = PortBundle(
        fetch_fixture=InertFetchFixture(
            response={"fixture_id": 12345, "found": True, "fixture_quality": "INVALID"}
        )
    )
    em = ExecutionManager(ports=ports)
    result = em.run(
        _req(
            flags={"named_assess_blocked": True},
            entities={"home": "Flamengo", "away": "Palmeiras", "fixture_id": 12345},
        )
    )
    assert result.status == ExecutionStatus.COMPLETED
    assert result.abort_reason is None
    assert result.fixture_quality == FixtureQuality.VALID_LOCATED.value
    a2 = next(t for t in result.step_traces if t.step_id == "integrity_gate")
    assert a2.status.value == "skipped"
    assert a2.reason == "integrity_soft_skip_fixture_located"
    assert [t.step_id for t in result.step_traces] == list(ANALYZE_STEP_ORDER)


def test_golden3_partial_continue():
    _clear_em_flags()
    em = ExecutionManager()
    result = em.run(_req(flags={"integrity_outcome": "PARTIAL"}))
    assert result.status == ExecutionStatus.COMPLETED
    assert result.fixture_quality == FixtureQuality.PARTIAL.value
    assert [t.step_id for t in result.step_traces] == list(ANALYZE_STEP_ORDER)


def test_live_and_thin_stubs():
    _clear_em_flags()
    em = ExecutionManager()
    live = em.run(_req(pipeline="live", run_id="live-1"))
    assert live.status == ExecutionStatus.COMPLETED
    assert live.payload.get("intent") == "live_opportunities"
    assert live.diagnostics.get("phase4_stage2") is True
    assert live.diagnostics.get("stub") is False
    # Phase 4 Stage 1: thin pipelines are real handlers (not stub payloads).
    expected_intent = {
        "bankroll": "bankroll_review",
        "learning": "learning_recap",
        "knowledge": "knowledge_search",
    }
    for pid in ("bankroll", "learning", "knowledge"):
        r = em.run(_req(pipeline=pid, run_id=f"{pid}-1"))
        assert r.status == ExecutionStatus.COMPLETED
        assert r.payload.get("intent") == expected_intent[pid]
        assert r.diagnostics.get("thin") is True
        assert "stub" not in r.payload


def test_live_team_analyze_stub_delegates():
    _clear_em_flags()
    em = ExecutionManager()
    result = em.run(
        _req(
            pipeline="live_team_analyze",
            run_id="lta-1",
            flags={"integrity_outcome": "PASS"},
            entities={"home": "A", "away": "B"},
        )
    )
    assert result.status == ExecutionStatus.COMPLETED
    assert result.payload["analyze"]["stub"] is True


def test_budget_denied_fails():
    _clear_em_flags()
    em = ExecutionManager(ports=PortBundle(budget_gate=InertBudgetGate(allow=False)))
    result = em.run(_req())
    assert result.status == ExecutionStatus.FAILED
    assert result.payload["error"] == "budget_denied"


def test_shadow_compare_wired_observe_only():
    """Phase 3: shadow_compare is wired for observe; never primary replacement."""
    _clear_em_flags()
    em = ExecutionManager()
    legacy = {
        "intent": "analyze_match",
        "fixture_quality": "INVALID",
        "status": "blocked",
        "entities": {"entity_invalid": True, "markets_blocked": True, "home": "Fake", "away": "No"},
        "best_markets": [],
        "fixture_id": 0,
    }
    meta = em.shadow_compare(_req(run_id="shadow-1"), legacy_payload=legacy)
    assert meta["wired"] is True
    assert meta["shadow_only"] is True
    assert meta["primary_replaced"] is False
    assert meta["cm_eligibility"] == "NO"
    assert meta["stub"] is False


# ---------------------------------------------------------------------------
# Boundary / Router isolation
# ---------------------------------------------------------------------------


def test_em_package_forbids_cm_matchcard_begin_request():
    """Boundary negative: EM sources must not contain forbidden tokens."""
    offenders: list[str] = []
    for path in EM_PKG.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        for token in FORBIDDEN_EM_TOKENS:
            if f"{token}(" in text or f"import {token}" in text:
                offenders.append(f"{path.name}:{token}")
            if f" {token}" in text and "import" in text:
                try:
                    tree = ast.parse(text)
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        for alias in node.names:
                            if alias.name == token:
                                offenders.append(f"{path.name}:import:{token}")
                    if isinstance(node, ast.Call):
                        func = node.func
                        name = getattr(func, "attr", None) or getattr(func, "id", None)
                        if name == token:
                            offenders.append(f"{path.name}:call:{token}")
    assert offenders == []


def test_router_shadow_hook_is_observe_only_not_sole_path():
    """
    Phase 3 shadow remains observe-only. Phase 4 Stage 1/2/3 add thin+live+analyze shims.
    live_team must NOT be sole-pathed. Legacy bodies remain.
    """
    text = ROUTER.read_text(encoding="utf-8", errors="replace")
    assert "_observe_em_shadow" in text
    assert "maybe_em_shadow_observe" in text
    assert "ENABLE_EXECUTION_MANAGER_SHADOW" in text
    assert "_em_thin_or_legacy" in text
    assert "_em_live_or_legacy" in text
    assert "_em_analyze_or_legacy" in text
    assert "analyze_pipeline_extraction_enabled" in text
    # Stage 3 analyze wired; live_team pipeline flag absent from Router
    assert "ENABLE_EM_PIPELINE_LIVE_TEAM" not in text
    # Must not assign shadow result onto production payload
    assert "payload = maybe_em_shadow_observe" not in text
    assert "payload = _observe_em_shadow" not in text
    for needle in (
        "async def _run_analyze",
        "async def _run_live",
        "def _run_bankroll",
        "def _run_learning",
        "def _run_knowledge",
    ):
        assert needle in text


def test_step_runner_direct_callable_but_isolated():
    """Runner is callable in harness; not a Router concern."""
    _clear_em_flags()
    runner = StepRunner()
    result = runner.run(_req(flags={"integrity_outcome": "PASS"}))
    assert isinstance(result, ExecutionResult)
    assert result.status == ExecutionStatus.COMPLETED
