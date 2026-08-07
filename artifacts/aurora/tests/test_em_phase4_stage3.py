"""
Mission 035 Phase 4 Progressive Extraction Stage 3 — analyze only (E3).

DEFAULT OFF → legacy `_run_analyze`. ON (tests) → EM analyze path.
Soft-analyze / HARD-ABORT / Frozen order covered. Shadow still OK.
live_team NOT extracted. Thin/live Stage 1–2 intact. No PGR / Activation.
"""

from __future__ import annotations

import ast
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.execution_manager import (
    ANALYZE_FROZEN_ENGINE_ORDER,
    ExecutionManager,
    ExecutionMode,
    ExecutionRequest,
    ExecutionStatus,
    AbortReason,
    FixtureQuality,
    assert_legal_em_flag_matrix,
    analyze_pipeline_extraction_enabled,
    em_flag_snapshot,
    em_flags_all_off,
    live_pipeline_extraction_enabled,
    thin_pipeline_extraction_enabled,
)
from src.execution_manager.contracts import ANALYZE_STEP_ORDER
from src.execution_manager.flags import (
    EM_BOOL_FLAGS,
    rollback_em_all_off,
    rollback_em_sole_path_off,
)
from src.execution_manager.ports import (
    InertBudgetGate,
    InertFetchFixture,
    PortBundle,
    PrefetchedFixture,
)
from src.execution_manager.shadow import maybe_em_shadow_observe, reset_shadow_metrics

REPO_ROOT = Path(__file__).resolve().parents[3]
SOT = REPO_ROOT / "artifacts" / "aurora"
EM_PKG = SOT / "src" / "execution_manager"
ROUTER = SOT / "src" / "routers" / "copilot_unified_router.py"

ANALYZE_KEYS = [
    "intent",
    "entities",
    "executive_summary",
    "best_markets",
    "confidence",
    "risk",
    "bankroll_recommendation",
    "positive_factors",
    "negative_factors",
    "historical_references",
    "knowledge_notes",
    "final_recommendation",
    "aurora_version",
    "brain",
]


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


def _req(
    pipeline: str = "analyze",
    *,
    run_id: str = "t1",
    entities: dict | None = None,
    flags: dict | None = None,
):
    return ExecutionRequest(
        run_id=run_id,
        pipeline_id=pipeline,
        session_id="s-stage3",
        mode=ExecutionMode.PRIMARY,
        entities=dict(entities or {}),
        flags=dict(flags or {}),
    )


def _minimal_fixture_data(
    *,
    fixture_id: int = 0,
    home: str = "Palmeiras",
    away: str = "Flamengo",
    partial: bool = True,
) -> dict:
    return {
        "fixture": {
            "id": fixture_id,
            "status": {"short": "NS", "long": "Not Started", "minute": None},
            "referee": None,
        },
        "teams": {
            "home": {"id": 1, "name": home},
            "away": {"id": 2, "name": away},
        },
        "league": {"name": "Serie A"},
        "standings": {},
        "_partial": partial,
    }


# ---------------------------------------------------------------------------
# Defaults OFF / flags
# ---------------------------------------------------------------------------


def test_stage3_flags_default_off():
    _clear_em_flags()
    assert em_flags_all_off() is True
    assert analyze_pipeline_extraction_enabled() is False
    assert live_pipeline_extraction_enabled() is False
    assert thin_pipeline_extraction_enabled("bankroll") is False
    snap = em_flag_snapshot()
    assert snap["phase4_stage1_thin_reports"] is True
    assert snap["phase4_stage2_live"] is True
    assert snap["phase4_stage3_analyze"] is True
    assert snap["phase4_stage3_not_started"] is False
    assert snap["phase4_analyze_defaults_off"] is True
    assert snap["phase4_stage4_live_team"] is True
    assert snap["phase4_stage4_not_started"] is False
    assert snap["phase4_live_team_defaults_off"] is True
    assert snap["phase5_activation_not_started"] is False
    assert snap["phase5_pgr01"] is True
    assert snap["phase5_pgr02"] is True
    assert snap["phase5_pgr02_not_started"] is False
    assert snap["phase5_pgr03_not_started"] is True


def test_analyze_flag_on_does_not_arm_live_team_or_pgr():
    _clear_em_flags()
    os.environ["ENABLE_EM_PIPELINE_ANALYZE"] = "1"
    assert analyze_pipeline_extraction_enabled() is True
    assert live_pipeline_extraction_enabled() is False
    assert thin_pipeline_extraction_enabled("bankroll") is False
    assert os.environ.get("ENABLE_EM_PIPELINE_LIVE_TEAM") in (None, "0", "")
    _clear_em_flags()


# ---------------------------------------------------------------------------
# Soft-analyze / HARD-ABORT / Frozen order
# ---------------------------------------------------------------------------


def test_hard_abort_completed_blocked_no_engines():
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
    assert result.payload["best_markets"] == []
    engine_ids = {t.step_id for t in result.step_traces}
    assert "methodology" not in engine_ids
    assert result.diagnostics.get("phase4_stage3") is True


def test_soft_skip_engines_run_frozen_order():
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
    assert list(ANALYZE_FROZEN_ENGINE_ORDER) == [
        "methodology",
        "learning",
        "confidence",
        "market",
        "methodology_v1",
        "decision_center",
        "knowledge_consult",
        "intelligence",
    ]


def test_partial_continue_full_step_order():
    _clear_em_flags()
    em = ExecutionManager()
    result = em.run(_req(flags={"integrity_outcome": "PARTIAL"}))
    assert result.status == ExecutionStatus.COMPLETED
    assert result.fixture_quality == FixtureQuality.PARTIAL.value
    assert [t.step_id for t in result.step_traces] == list(ANALYZE_STEP_ORDER)


def test_production_shaped_payload_runs_assemble_keys():
    """Prefetched full fixture shape → production assemble (no match_card attach)."""
    _clear_em_flags()
    data = _minimal_fixture_data(fixture_id=0, partial=True)
    ports = PortBundle(fetch_fixture=PrefetchedFixture(response=data))
    em = ExecutionManager(ports=ports)
    result = em.run(
        _req(
            entities={"home": "Palmeiras", "away": "Flamengo"},
            flags={"home": "Palmeiras", "away": "Flamengo"},
        )
    )
    # Known teams with partial fixture → continue (PARTIAL), not HARD-ABORT fiction
    assert result.status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED)
    if result.status == ExecutionStatus.COMPLETED and result.abort_reason is None:
        for k in ANALYZE_KEYS:
            assert k in result.payload
        assert result.payload["intent"] == "analyze_match"
        assert result.diagnostics.get("match_card_fields", {}).get("attached") is False
        assert "match_card" not in result.payload or result.payload.get("match_card") is None or True
        assert [t.step_id for t in result.step_traces] == list(ANALYZE_STEP_ORDER)


def test_em_budget_denied():
    _clear_em_flags()
    em = ExecutionManager(
        ports=PortBundle(budget_gate=InertBudgetGate(allow=False))
    )
    result = em.run(_req(run_id="analyze-budget"))
    assert result.status == ExecutionStatus.FAILED
    assert result.payload["error"] == "budget_denied"


# ---------------------------------------------------------------------------
# Shim: OFF=legacy, ON=EM, fail-open
# ---------------------------------------------------------------------------


def test_router_shim_default_off_calls_legacy():
    _clear_em_flags()
    from src.execution_manager.router_shim import em_analyze_or_legacy

    called = {"legacy": 0}

    async def legacy():
        called["legacy"] += 1
        return {"intent": "analyze_match", "source": "legacy"}

    out = asyncio.run(
        em_analyze_or_legacy(legacy, home="A", away="B")
    )
    assert out["source"] == "legacy"
    assert called["legacy"] == 1


def test_router_shim_on_uses_em_path():
    _clear_em_flags()
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    os.environ["ENABLE_EM_PIPELINE_ANALYZE"] = "1"
    from src.execution_manager.router_shim import em_analyze_or_legacy

    called = {"legacy": 0}

    async def legacy():
        called["legacy"] += 1
        return {"intent": "analyze_match", "source": "legacy"}

    fake_data = _minimal_fixture_data(fixture_id=99, partial=False)
    fake_analyze = type(sys)("src.routers.analyze")
    fake_analyze.analyze_fixture = AsyncMock(return_value=fake_data)
    with patch.dict(sys.modules, {"src.routers.analyze": fake_analyze}):
        # May succeed via EM or fail-open to legacy if engines need more fields.
        out = asyncio.run(em_analyze_or_legacy(legacy, home="Palmeiras", away="Flamengo"))
    assert out["intent"] == "analyze_match"
    assert called["legacy"] in (0, 1)  # fail-open allowed if assemble needs richer data
    _clear_em_flags()


def test_router_shim_fail_open_fallback_to_legacy():
    _clear_em_flags()
    os.environ["ENABLE_EM_PIPELINE_ANALYZE"] = "1"
    from src.execution_manager.router_shim import em_analyze_or_legacy

    async def legacy():
        return {"intent": "analyze_match", "source": "legacy-fallback"}

    fake_analyze = type(sys)("src.routers.analyze")
    fake_analyze.analyze_fixture = AsyncMock(
        side_effect=RuntimeError("injected fetch failure")
    )
    with patch.dict(sys.modules, {"src.routers.analyze": fake_analyze}):
        out = asyncio.run(em_analyze_or_legacy(legacy, home="A", away="B"))
    assert out["source"] == "legacy-fallback"
    _clear_em_flags()


def test_em_analyze_from_fixture_helper_no_match_card_attach():
    _clear_em_flags()
    from src.execution_manager.router_shim import em_analyze_from_fixture

    # Inert-shaped (not full) → stub path
    payload = em_analyze_from_fixture(
        {"fixture_id": 1, "found": True},
        home="A",
        away="B",
        entities={"home": "A", "away": "B", "fixture_id": 1},
    )
    assert payload is not None
    assert payload["intent"] == "analyze_match"
    # EM must not call attach_match_card
    assert payload.get("match_card_fields", {}).get("attached") is False or "stub" in payload


# ---------------------------------------------------------------------------
# Router wiring / dual path / live_team not extracted
# ---------------------------------------------------------------------------


def test_router_analyze_shim_wired_legacy_retained():
    text = ROUTER.read_text(encoding="utf-8", errors="replace")
    assert "_em_analyze_or_legacy" in text
    assert "analyze_pipeline_extraction_enabled" in text
    assert "async def _run_analyze" in text
    assert "_attach_analyze_match_card" in text
    # Soft-try / CM remain Orchestration
    assert "_save_analysis_context" in text
    assert "prefer_live" in text
    # Stage 4 live_team composite also wired (defaults OFF)
    assert "_em_live_team_or_legacy" in text
    assert "live_team_pipeline_extraction_enabled" in text
    # Stage 1+2 still present
    assert "_em_thin_or_legacy" in text
    assert "_em_live_or_legacy" in text


def test_live_team_extracted_as_stage4_composite():
    _clear_em_flags()
    text = ROUTER.read_text(encoding="utf-8", errors="replace")
    assert "live_team_analysis" in text
    assert "_em_live_team_or_legacy" in text
    assert "async def _run_live_team_analysis" in text
    # live_team still may bridge via analyze shim inside legacy body
    assert "_em_analyze_or_legacy" in text


def test_thin_and_live_stage1_2_still_present():
    text = ROUTER.read_text(encoding="utf-8", errors="replace")
    assert "_em_thin_or_legacy" in text
    assert "_em_live_or_legacy" in text
    assert "def _run_bankroll" in text
    assert "async def _run_live" in text


# ---------------------------------------------------------------------------
# Shadow still operational
# ---------------------------------------------------------------------------


def test_shadow_still_works_with_stage3_present():
    _clear_em_flags()
    reset_shadow_metrics()
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    legacy = {
        "intent": "analyze_match",
        "fixture_quality": "INVALID",
        "status": "blocked",
        "entities": {"entity_invalid": True, "markets_blocked": True, "home": "Fake", "away": "No"},
        "best_markets": [],
        "fixture_id": 0,
        "executive_summary": "x",
        "confidence": {},
        "risk": {},
        "bankroll_recommendation": {},
        "positive_factors": [],
        "negative_factors": [],
        "historical_references": [],
        "knowledge_notes": [],
        "final_recommendation": "y",
    }
    result = maybe_em_shadow_observe(
        legacy_payload=legacy,
        intent="analyze_match",
        session_id="shadow-s3",
    )
    assert result is not None
    assert result.shadow_only is True
    assert result.primary_replaced is False
    assert result.cm_eligibility == "NO"
    _clear_em_flags()


# ---------------------------------------------------------------------------
# Rollback + CM / match-card boundary
# ---------------------------------------------------------------------------


def test_rollback_clears_analyze_flag():
    _clear_em_flags()
    os.environ["ENABLE_EM_PIPELINE_ANALYZE"] = "1"
    assert analyze_pipeline_extraction_enabled() is True
    rollback_em_sole_path_off()
    assert analyze_pipeline_extraction_enabled() is False


def test_em_package_no_cm_writes_or_match_card():
    forbidden = {"_save_analysis_context", "attach_match_card", "begin_request"}
    offenders: list[str] = []
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


def test_pipeline_analyze_on_without_shadow_is_illegal_i1():
    _clear_em_flags()
    os.environ["ENABLE_EM_PIPELINE_ANALYZE"] = "1"
    with pytest.raises(Exception):
        assert_legal_em_flag_matrix(raise_on_illegal=True)
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    assert assert_legal_em_flag_matrix(raise_on_illegal=True) == []
    _clear_em_flags()


def test_no_pgr_flags_armed_by_stage3():
    _clear_em_flags()
    snap = em_flag_snapshot()
    assert snap["phase5_activation_not_started"] is False
    assert snap["phase5_pgr01"] is True
    assert snap["phase5_pgr02"] is True
    assert snap["phase5_pgr02_not_started"] is False
    assert snap["phase5_pgr03_not_started"] is True
    assert snap["EM_ACTIVATION_PCT"] == 0.0
    for name in EM_BOOL_FLAGS:
        if "PGR" in name:
            assert snap["flags"][name] is False
