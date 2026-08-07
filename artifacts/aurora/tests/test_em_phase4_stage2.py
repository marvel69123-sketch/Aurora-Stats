"""
Mission 034 Phase 4 Progressive Extraction Stage 2 — live only (E2).

DEFAULT OFF → legacy `_run_live`. ON (tests) → EM live path. Shadow still OK.
Analyze / live_team untouched. Thin Stage 1 untouched. No PGR / Activation.
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
    ExecutionManager,
    ExecutionMode,
    ExecutionRequest,
    ExecutionStatus,
    assert_legal_em_flag_matrix,
    em_flag_snapshot,
    em_flags_all_off,
    live_pipeline_extraction_enabled,
    thin_pipeline_extraction_enabled,
)
from src.execution_manager.contracts import LIVE_STEP_ORDER
from src.execution_manager.flags import (
    EM_BOOL_FLAGS,
    rollback_em_all_off,
    rollback_em_sole_path_off,
)
from src.execution_manager.ports import (
    InertBudgetGate,
    InertFetchLiveFeed,
    PortBundle,
    PrefetchedLiveFeed,
    ProductionLiveEnginePort,
)
from src.execution_manager.shadow import maybe_em_shadow_observe, reset_shadow_metrics

REPO_ROOT = Path(__file__).resolve().parents[3]
SOT = REPO_ROOT / "artifacts" / "aurora"
EM_PKG = SOT / "src" / "execution_manager"
ROUTER = SOT / "src" / "routers" / "copilot_unified_router.py"

LIVE_KEYS = [
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


def _req(pipeline: str = "live", *, run_id: str = "t1", entities: dict | None = None):
    return ExecutionRequest(
        run_id=run_id,
        pipeline_id=pipeline,
        session_id="s-stage2",
        mode=ExecutionMode.PRIMARY,
        entities=dict(entities or {}),
    )


def _sample_feed() -> dict:
    return {
        "total": 1,
        "cached": False,
        "matches": [
            {
                "fixture_id": 101,
                "status": {"long": "Second Half", "short": "2H", "minute": 67},
                "league": {"name": "Serie A", "country": "Brazil"},
                "home": {"id": 1, "name": "Palmeiras", "score": 1},
                "away": {"id": 2, "name": "Flamengo", "score": 0},
                "stats": {
                    "home": {"shots_on_goal": 5, "corners": 4},
                    "away": {"shots_on_goal": 2, "corners": 1},
                },
                "events": [],
            }
        ],
    }


# ---------------------------------------------------------------------------
# Defaults OFF / flags
# ---------------------------------------------------------------------------


def test_stage2_flags_default_off():
    _clear_em_flags()
    assert em_flags_all_off() is True
    assert live_pipeline_extraction_enabled() is False
    assert thin_pipeline_extraction_enabled("bankroll") is False
    snap = em_flag_snapshot()
    assert snap["phase4_stage1_thin_reports"] is True
    assert snap["phase4_stage2_live"] is True
    assert snap["phase4_stage2_not_started"] is False
    assert snap["phase4_live_defaults_off"] is True
    assert snap["phase4_stage3_not_started"] is False
    assert snap["phase4_stage3_analyze"] is True
    assert snap["phase4_stage4_live_team"] is True
    assert snap["phase4_stage4_not_started"] is False
    assert snap["phase5_activation_not_started"] is False
    assert snap["phase5_pgr01"] is True
    assert snap["phase5_pgr02"] is True
    assert snap["phase5_pgr02_not_started"] is False
    assert snap["phase5_pgr03_not_started"] is False
    assert snap["phase5_pgr04_not_started"] is False
    assert snap["phase5_pgr05_not_started"] is False
    assert snap["phase5_pgr06_not_started"] is True


def test_live_flag_on_does_not_arm_analyze_or_thin():
    _clear_em_flags()
    os.environ["ENABLE_EM_PIPELINE_LIVE"] = "1"
    assert live_pipeline_extraction_enabled() is True
    assert thin_pipeline_extraction_enabled("bankroll") is False
    assert thin_pipeline_extraction_enabled("analyze") is False
    _clear_em_flags()


# ---------------------------------------------------------------------------
# EM live handlers
# ---------------------------------------------------------------------------


def test_em_live_step_order_and_parity_keys():
    _clear_em_flags()
    ports = PortBundle(
        fetch_live_feed=PrefetchedLiveFeed(response=_sample_feed()),
        engine=ProductionLiveEnginePort(),
    )
    em = ExecutionManager(ports=ports)
    result = em.run(_req(run_id="live-1"))
    assert result.status == ExecutionStatus.COMPLETED
    assert [t.step_id for t in result.step_traces] == list(LIVE_STEP_ORDER)
    for k in LIVE_KEYS:
        assert k in result.payload
    assert result.payload["intent"] == "live_opportunities"
    assert result.diagnostics.get("phase4_stage2") is True
    assert result.diagnostics.get("match_card_fields", {}).get("attached") is False
    assert "live_fixtures" in result.diagnostics


def test_em_live_empty_feed():
    _clear_em_flags()
    ports = PortBundle(
        fetch_live_feed=PrefetchedLiveFeed(response={"matches": []}),
        engine=ProductionLiveEnginePort(),
    )
    em = ExecutionManager(ports=ports)
    result = em.run(_req(run_id="live-empty"))
    assert result.status == ExecutionStatus.COMPLETED
    assert result.payload["intent"] == "live_opportunities"
    assert result.payload["entities"].get("live_count") == 0


def test_em_live_budget_denied():
    _clear_em_flags()
    em = ExecutionManager(
        ports=PortBundle(
            budget_gate=InertBudgetGate(allow=False),
            fetch_live_feed=InertFetchLiveFeed(),
        )
    )
    result = em.run(_req(run_id="live-budget"))
    assert result.status == ExecutionStatus.FAILED
    assert result.payload["error"] == "budget_denied"


def test_em_live_from_feed_helper():
    _clear_em_flags()
    from src.execution_manager.router_shim import em_live_from_feed

    payload = em_live_from_feed(_sample_feed(), session_id="s2")
    assert payload is not None
    assert payload["intent"] == "live_opportunities"
    assert "executive_summary" in payload


def test_router_shim_default_off_calls_legacy():
    _clear_em_flags()
    from src.execution_manager.router_shim import em_live_or_legacy

    called = {"legacy": 0}

    async def legacy():
        called["legacy"] += 1
        return {"intent": "live_opportunities", "source": "legacy"}

    out = asyncio.run(em_live_or_legacy(legacy))
    assert out["source"] == "legacy"
    assert called["legacy"] == 1


def test_router_shim_on_uses_em_path():
    _clear_em_flags()
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    os.environ["ENABLE_EM_PIPELINE_LIVE"] = "1"
    from src.execution_manager.router_shim import em_live_or_legacy

    called = {"legacy": 0}

    async def legacy():
        called["legacy"] += 1
        return {"intent": "live_opportunities", "source": "legacy"}

    fake_live = type(sys)("src.routers.live")
    fake_live._build_live_response = AsyncMock(return_value=_sample_feed())
    with patch.dict(sys.modules, {"src.routers.live": fake_live}):
        out = asyncio.run(em_live_or_legacy(legacy))
    assert out["intent"] == "live_opportunities"
    assert out.get("source") != "legacy"
    assert called["legacy"] == 0
    assert "_em_live_fixtures" in out
    _clear_em_flags()


def test_router_shim_fail_open_fallback_to_legacy():
    _clear_em_flags()
    os.environ["ENABLE_EM_PIPELINE_LIVE"] = "1"
    from src.execution_manager.router_shim import em_live_or_legacy

    async def legacy():
        return {"intent": "live_opportunities", "source": "legacy-fallback"}

    fake_live = type(sys)("src.routers.live")
    fake_live._build_live_response = AsyncMock(
        side_effect=RuntimeError("injected feed failure")
    )
    with patch.dict(sys.modules, {"src.routers.live": fake_live}):
        out = asyncio.run(em_live_or_legacy(legacy))
    assert out["source"] == "legacy-fallback"
    _clear_em_flags()


def test_analyze_wired_live_team_gated_by_stage4():
    _clear_em_flags()
    text = ROUTER.read_text(encoding="utf-8", errors="replace")
    assert "_em_live_or_legacy" in text
    assert "_em_analyze_or_legacy" in text
    assert "_em_live_team_or_legacy" in text
    assert "analyze_pipeline_extraction_enabled" in text
    assert "live_team_pipeline_extraction_enabled" in text
    assert "async def _run_analyze" in text
    assert "async def _run_live_team_analysis" in text
    assert "live_team_analysis" in text


def test_thin_stage1_still_present():
    text = ROUTER.read_text(encoding="utf-8", errors="replace")
    assert "_em_thin_or_legacy" in text
    assert "def _run_bankroll" in text


# ---------------------------------------------------------------------------
# Shadow still operational
# ---------------------------------------------------------------------------


def test_shadow_still_works_with_stage2_present():
    _clear_em_flags()
    reset_shadow_metrics()
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    legacy = {
        "intent": "live_opportunities",
        "executive_summary": "x",
        "entities": {"live_count": 0},
        "confidence": {},
        "risk": {},
        "bankroll_recommendation": {},
        "positive_factors": [],
        "negative_factors": [],
        "historical_references": [],
        "knowledge_notes": [],
        "final_recommendation": "y",
        "best_markets": [],
    }
    result = maybe_em_shadow_observe(
        legacy_payload=legacy,
        intent="live_opportunities",
        session_id="shadow-s2",
    )
    assert result is not None
    assert result.shadow_only is True
    assert result.primary_replaced is False
    assert result.cm_eligibility == "NO"
    _clear_em_flags()


# ---------------------------------------------------------------------------
# Rollback + CM / match-card boundary
# ---------------------------------------------------------------------------


def test_rollback_clears_live_flag():
    _clear_em_flags()
    os.environ["ENABLE_EM_PIPELINE_LIVE"] = "1"
    assert live_pipeline_extraction_enabled() is True
    rollback_em_sole_path_off()
    assert live_pipeline_extraction_enabled() is False


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


def test_legacy_live_body_retained_dual_path():
    text = ROUTER.read_text(encoding="utf-8", errors="replace")
    assert "async def _run_live" in text
    assert "_em_live_or_legacy" in text
    assert "_attach_live_match_card" in text
    assert "async def _run_analyze" in text


def test_pipeline_live_on_without_shadow_is_illegal_i1():
    _clear_em_flags()
    os.environ["ENABLE_EM_PIPELINE_LIVE"] = "1"
    with pytest.raises(Exception):
        assert_legal_em_flag_matrix(raise_on_illegal=True)
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    assert assert_legal_em_flag_matrix(raise_on_illegal=True) == []
    _clear_em_flags()


def test_production_live_engine_is_consume_only():
    port = ProductionLiveEnginePort()
    out = port.run("live_intelligence", {"feed": {"matches": []}})
    assert out["intent"] == "live_opportunities"
    assert not hasattr(port, "attach_match_card")
    assert not hasattr(port, "save")
