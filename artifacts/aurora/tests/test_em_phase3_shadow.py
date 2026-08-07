"""
Mission 032 Phase 3 — Execution Manager Shadow Mode tests.

Observe-only · fail-open · flag DEFAULT OFF · no response/ctx/CM mutation ·
no `_run_*` extraction · activation flags fail-closed.
"""

from __future__ import annotations

import ast
import copy
import os
from pathlib import Path

import pytest

from src.execution_manager import (
    APPENDIX_A_MANDATORY_KEYS,
    ExecutionManager,
    ExecutionMode,
    ExecutionRequest,
    IllegalEmFlagMatrixError,
    assert_legal_em_flag_matrix,
    em_flag_snapshot,
    em_flags_all_off,
    maybe_em_shadow_observe,
    rollback_em_shadow_off,
    shadow_compare,
    shadow_enabled,
    shadow_metrics_snapshot,
)
from src.execution_manager.flags import (
    EM_BOOL_FLAGS,
    collect_illegal_em_combinations,
    rollback_em_all_off,
)
from src.execution_manager.observability import set_event_sink
from src.execution_manager.shadow import (
    NOISE_ALLOWLIST,
    cm_eligibility_for_shadow,
    compare_appendix_a,
    project_em_result,
    project_legacy_payload,
    reset_shadow_metrics,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SOT = REPO_ROOT / "artifacts" / "aurora"
EM_PKG = SOT / "src" / "execution_manager"
ROUTER = SOT / "src" / "routers" / "copilot_unified_router.py"
APPENDIX_A_BASELINE = (
    REPO_ROOT
    / "observations"
    / "execution_manager_impl_030"
    / "baselines"
    / "appendix_a_keys.json"
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


def _legacy_hard_abort() -> dict:
    return {
        "intent": "analyze_match",
        "fixture_quality": "INVALID",
        "status": "blocked",
        "entities": {
            "home": "FakeFC",
            "away": "NoClub",
            "entity_invalid": True,
            "markets_blocked": True,
            "fixture_quality": "INVALID",
            "fixture_id": 0,
        },
        "best_markets": [],
        "fixture_id": 0,
        "match_card": None,
    }


def _legacy_live() -> dict:
    return {
        "intent": "live_opportunities",
        "entities": {},
        "best_markets": [],
        "fixture_quality": None,
    }


def _legacy_thin(intent: str) -> dict:
    return {"intent": intent, "entities": {}, "best_markets": []}


# ---------------------------------------------------------------------------
# Defaults OFF / no-op
# ---------------------------------------------------------------------------


def test_shadow_flag_default_off_is_noop():
    _clear_em_flags()
    reset_shadow_metrics()
    assert shadow_enabled() is False
    assert em_flags_all_off() is True
    primary = _legacy_hard_abort()
    primary_copy = copy.deepcopy(primary)
    result = maybe_em_shadow_observe(
        legacy_payload=primary,
        intent="analyze_match",
        session_id="s1",
    )
    assert result is None
    assert primary == primary_copy
    assert shadow_metrics_snapshot()["runs_shadowed"] == 0


def test_shadow_on_observe_only_does_not_mutate_primary():
    _clear_em_flags()
    reset_shadow_metrics()
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    try:
        primary = _legacy_hard_abort()
        primary_id = id(primary)
        before = copy.deepcopy(primary)
        events: list[tuple[str, dict]] = []
        set_event_sink(lambda e, p: events.append((e, p)))
        result = maybe_em_shadow_observe(
            legacy_payload=primary,
            intent="analyze_match",
            session_id="s-shadow",
        )
        assert result is not None
        assert result.shadow_only is True
        assert result.primary_replaced is False
        assert result.cm_eligibility == "NO"
        assert result.wired is True
        assert id(primary) == primary_id
        assert primary == before
        assert any(e == "em.shadow.diff" for e, _ in events)
        assert shadow_metrics_snapshot()["runs_shadowed"] >= 1
    finally:
        set_event_sink(None)
        _clear_em_flags()


def test_force_observe_bypasses_flag_for_harness_only():
    _clear_em_flags()
    assert shadow_enabled() is False
    result = maybe_em_shadow_observe(
        legacy_payload=_legacy_hard_abort(),
        pipeline_id="analyze",
        force=True,
    )
    assert result is not None
    assert result.shadow_only is True
    assert result.cm_eligibility == "NO"


# ---------------------------------------------------------------------------
# Appendix A compare
# ---------------------------------------------------------------------------


def test_appendix_a_mandatory_keys_not_dropped():
    assert "pipeline_id" in APPENDIX_A_MANDATORY_KEYS
    assert "fixture_quality" in APPENDIX_A_MANDATORY_KEYS
    assert "best_markets" in APPENDIX_A_MANDATORY_KEYS
    assert "step_traces_engine_order" in APPENDIX_A_MANDATORY_KEYS
    assert APPENDIX_A_BASELINE.is_file()
    assert "timestamps" in NOISE_ALLOWLIST


def test_compare_hard_abort_parity_identity_integrity():
    _clear_em_flags()
    legacy = _legacy_hard_abort()
    result = shadow_compare(pipeline_id="analyze", legacy_payload=legacy)
    assert result.cm_eligibility == "NO"
    assert result.primary_replaced is False
    # Identity / integrity keys should align for HARD-ABORT stub vs blocked legacy.
    hard_keys = {d["key"] for d in result.hard_diffs}
    assert "pipeline_id" not in hard_keys
    assert "status" not in hard_keys
    assert "fixture_quality" not in hard_keys
    assert "abort_reason" not in hard_keys


def test_compare_appendix_a_direct():
    legacy_view = project_legacy_payload("analyze", _legacy_hard_abort())
    em = ExecutionManager()
    em_result = em.run(
        ExecutionRequest(
            run_id="c1",
            pipeline_id="analyze",
            session_id="s",
            mode=ExecutionMode.SHADOW,
            entities={"home": "FakeFC", "away": "NoClub"},
            flags={"integrity_outcome": "HARD_ABORT"},
        )
    )
    em_view = project_em_result(em_result)
    parity, hard, soft = compare_appendix_a(legacy_view, em_view)
    assert isinstance(parity, bool)
    assert isinstance(hard, list)
    assert isinstance(soft, list)


@pytest.mark.parametrize(
    "intent,pipeline,legacy_factory",
    [
        ("analyze_match", "analyze", _legacy_hard_abort),
        ("live_opportunities", "live", _legacy_live),
        ("bankroll_review", "bankroll", lambda: _legacy_thin("bankroll_review")),
        ("learning_recap", "learning", lambda: _legacy_thin("learning_recap")),
        ("knowledge_search", "knowledge", lambda: _legacy_thin("knowledge_search")),
    ],
)
def test_shadow_coverage_thin_live_analyze(intent, pipeline, legacy_factory):
    _clear_em_flags()
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    try:
        primary = legacy_factory()
        before = copy.deepcopy(primary)
        result = maybe_em_shadow_observe(
            legacy_payload=primary,
            intent=intent,
            session_id="cov",
        )
        assert result is not None
        assert result.pipeline_id == pipeline
        assert result.cm_eligibility == "NO"
        assert primary == before
    finally:
        _clear_em_flags()


# ---------------------------------------------------------------------------
# Fail-open / CM eligibility
# ---------------------------------------------------------------------------


def test_shadow_fail_open_on_em_exception():
    _clear_em_flags()
    reset_shadow_metrics()
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"

    class BoomEM:
        def run(self, request):
            raise RuntimeError("injected shadow failure")

    try:
        primary = _legacy_hard_abort()
        before = copy.deepcopy(primary)
        result = shadow_compare(
            pipeline_id="analyze",
            legacy_payload=primary,
            em=BoomEM(),
        )
        assert result.fail_open is True
        assert result.primary_replaced is False
        assert result.cm_eligibility == "NO"
        assert primary == before
        assert shadow_metrics_snapshot()["fail_open_count"] >= 1
    finally:
        _clear_em_flags()


def test_cm_eligibility_always_no():
    assert cm_eligibility_for_shadow() == "NO"
    _clear_em_flags()
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    try:
        result = maybe_em_shadow_observe(
            legacy_payload=_legacy_hard_abort(),
            intent="analyze_match",
        )
        assert result is not None
        assert result.cm_eligibility == "NO"
    finally:
        _clear_em_flags()


def test_illegal_i4_shadow_cm_eligible_fail_closed():
    _clear_em_flags()
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    os.environ["ENABLE_EM_SHADOW_CM_ELIGIBLE"] = "1"
    try:
        ids = {v["id"] for v in collect_illegal_em_combinations()}
        assert "I4" in ids
        with pytest.raises(IllegalEmFlagMatrixError):
            assert_legal_em_flag_matrix()
    finally:
        _clear_em_flags()


def test_activation_flags_fail_closed_without_shadow_evidence():
    """I1: sole-path / pipeline ON without Shadow = fail-closed."""
    _clear_em_flags()
    os.environ["ENABLE_EM_PIPELINE_ANALYZE"] = "1"
    try:
        ids = {v["id"] for v in collect_illegal_em_combinations()}
        assert "I1" in ids
    finally:
        _clear_em_flags()


def test_rollback_em_shadow_off():
    _clear_em_flags()
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    assert shadow_enabled() is True
    rollback_em_shadow_off()
    assert shadow_enabled() is False
    assert maybe_em_shadow_observe(
        legacy_payload=_legacy_hard_abort(),
        intent="analyze_match",
    ) is None


# ---------------------------------------------------------------------------
# Boundary / no extraction / no CM write from EM
# ---------------------------------------------------------------------------


def test_em_package_no_cm_write_or_match_card_calls():
    offenders: list[str] = []
    forbidden = ("_save_analysis_context", "attach_match_card", "begin_request")
    for path in EM_PKG.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = getattr(func, "attr", None) or getattr(func, "id", None)
                if name in forbidden:
                    offenders.append(f"{path.name}:call:{name}")
    assert offenders == []


def test_router_keeps_run_helpers_no_extraction():
    text = ROUTER.read_text(encoding="utf-8", errors="replace")
    for needle in (
        "async def _run_analyze",
        "async def _run_live",
        "async def _run_live_team_analysis",
        "def _run_bankroll",
        "def _run_learning",
        "def _run_knowledge",
        "def _save_analysis_context",
    ):
        assert needle in text
    # Observe hook present; Stage 1–4 shims present; defaults remain OFF
    assert "_observe_em_shadow" in text
    assert "_em_thin_or_legacy" in text
    assert "_em_live_or_legacy" in text
    assert "_em_analyze_or_legacy" in text
    assert "_em_live_team_or_legacy" in text
    assert "analyze_pipeline_extraction_enabled" in text
    assert "live_team_pipeline_extraction_enabled" in text
    assert "payload = maybe_em_shadow_observe" not in text


def test_conversational_intents_not_shadowed():
    _clear_em_flags()
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    try:
        result = maybe_em_shadow_observe(
            legacy_payload={"intent": "greeting", "executive_summary": "oi"},
            intent="greeting",
        )
        assert result is None
    finally:
        _clear_em_flags()


def test_flag_snapshot_phase3_posture():
    _clear_em_flags()
    snap = em_flag_snapshot()
    assert snap["phase3_shadow_observe_only"] is True
    assert snap["phase3_shadow_default_off"] is True
    assert snap["phase4_extraction_not_started"] is False
    assert snap["phase4_stage1_thin_reports"] is True
    assert snap["phase4_stage2_not_started"] is False
    assert snap["phase4_stage2_live"] is True
    assert snap["phase4_stage3_not_started"] is False
    assert snap["phase4_stage3_analyze"] is True
    assert snap["phase4_stage4_live_team"] is True
    assert snap["phase4_stage4_not_started"] is False
    assert snap["phase4_extraction_complete"] is True
    assert snap["shadow_enabled"] is False
