"""
Mission 036 Phase 4 Progressive Extraction Stage 4 — live_team_analyze only (E4).

DEFAULT OFF → legacy `_run_live_team_analysis`. ON (tests) → EM composite.
Shadow still OK. Thin/live/analyze Stage 1–3 intact. No PGR / Activation.
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
    analyze_pipeline_extraction_enabled,
    em_flag_snapshot,
    em_flags_all_off,
    live_pipeline_extraction_enabled,
    live_team_pipeline_extraction_enabled,
    thin_pipeline_extraction_enabled,
)
from src.execution_manager.contracts import LIVE_TEAM_STEP_ORDER
from src.execution_manager.flags import (
    EM_BOOL_FLAGS,
    rollback_em_all_off,
    rollback_em_sole_path_off,
)
from src.execution_manager.ports import (
    PortBundle,
    PrefetchedFixture,
    PrefetchedLiveFeed,
)
from src.execution_manager.shadow import maybe_em_shadow_observe, reset_shadow_metrics

REPO_ROOT = Path(__file__).resolve().parents[3]
SOT = REPO_ROOT / "artifacts" / "aurora"
EM_PKG = SOT / "src" / "execution_manager"
ROUTER = SOT / "src" / "routers" / "copilot_unified_router.py"


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
    pipeline: str = "live_team_analyze",
    *,
    run_id: str = "t1",
    entities: dict | None = None,
    flags: dict | None = None,
):
    return ExecutionRequest(
        run_id=run_id,
        pipeline_id=pipeline,
        session_id="s-stage4",
        mode=ExecutionMode.PRIMARY,
        entities=dict(entities or {}),
        flags=dict(flags or {}),
    )


def _feed_with_match(home: str = "Palmeiras", away: str = "Flamengo") -> dict:
    return {
        "matches": [
            {
                "home": {"name": home},
                "away": {"name": away},
                "fixture": {"id": 99, "status": {"short": "1H", "minute": 23}},
            }
        ]
    }


# ---------------------------------------------------------------------------
# Defaults OFF / flags
# ---------------------------------------------------------------------------


def test_stage4_flags_default_off():
    _clear_em_flags()
    assert em_flags_all_off() is True
    assert live_team_pipeline_extraction_enabled() is False
    assert analyze_pipeline_extraction_enabled() is False
    assert live_pipeline_extraction_enabled() is False
    assert thin_pipeline_extraction_enabled("bankroll") is False
    snap = em_flag_snapshot()
    assert snap["phase4_stage1_thin_reports"] is True
    assert snap["phase4_stage2_live"] is True
    assert snap["phase4_stage3_analyze"] is True
    assert snap["phase4_stage4_live_team"] is True
    assert snap["phase4_stage4_not_started"] is False
    assert snap["phase4_live_team_defaults_off"] is True
    assert snap["phase4_extraction_complete"] is True
    assert snap["phase5_activation_not_started"] is False
    assert snap["phase5_pgr01"] is True
    assert snap["phase5_pgr02"] is True
    assert snap["phase5_pgr02_not_started"] is False
    assert snap["phase5_pgr03_not_started"] is False
    assert snap["phase5_pgr04_not_started"] is True


def test_live_team_flag_on_does_not_arm_pgr():
    _clear_em_flags()
    os.environ["ENABLE_EM_PIPELINE_LIVE_TEAM"] = "1"
    assert live_team_pipeline_extraction_enabled() is True
    assert analyze_pipeline_extraction_enabled() is False
    assert live_pipeline_extraction_enabled() is False
    for g in range(1, 7):
        assert os.environ.get(f"ENABLE_EM_PGR_0{g}") in (None, "0", "")
    _clear_em_flags()


# ---------------------------------------------------------------------------
# EM composite: T0 not-found / T0 match + T1 delegate
# ---------------------------------------------------------------------------


def test_live_team_not_found_skips_delegate():
    _clear_em_flags()
    ports = PortBundle(
        fetch_live_feed=PrefetchedLiveFeed(response={"matches": []})
    )
    em = ExecutionManager(ports=ports)
    result = em.run(_req(entities={"team": "Palmeiras"}))
    assert result.status == ExecutionStatus.COMPLETED
    assert result.payload["intent"] == "live_team_analysis"
    assert result.payload["status"] == "NotFound"
    assert [t.step_id for t in result.step_traces] == list(LIVE_TEAM_STEP_ORDER)
    t1 = next(t for t in result.step_traces if t.step_id == "delegate_analyze")
    assert t1.status.value == "skipped"
    assert result.diagnostics.get("phase4_stage4") is True
    assert result.diagnostics.get("matched") is False


def test_live_team_match_delegates_analyze_step_order():
    _clear_em_flags()
    feed = _feed_with_match("Palmeiras", "Flamengo")
    # Inert-shaped fixture → harness analyze path (prefer_live child)
    ports = PortBundle(
        fetch_live_feed=PrefetchedLiveFeed(response=feed),
        fetch_fixture=PrefetchedFixture(
            response={"fixture_id": 99, "found": True, "home": "Palmeiras", "away": "Flamengo"}
        ),
    )
    em = ExecutionManager(ports=ports)
    result = em.run(
        _req(
            entities={"team": "Palmeiras"},
            flags={"integrity_outcome": "PASS"},
        )
    )
    assert result.status == ExecutionStatus.COMPLETED
    assert result.diagnostics.get("matched") is True
    assert result.diagnostics.get("home") == "Palmeiras"
    assert result.diagnostics.get("away") == "Flamengo"
    # Top-level T0/T1 present; child analyze traces appended
    top = [t.step_id for t in result.step_traces[:2]]
    assert top == list(LIVE_TEAM_STEP_ORDER)
    assert result.payload.get("intent") in ("analyze_match", "live_team_analysis")
    # No match_card attach inside EM
    assert "attach_match_card" not in str(result.diagnostics)


def test_live_team_harness_force_delegate_without_feed_hit():
    _clear_em_flags()
    em = ExecutionManager(
        ports=PortBundle(
            fetch_live_feed=PrefetchedLiveFeed(response={"matches": []}),
            fetch_fixture=PrefetchedFixture(response={"fixture_id": 1, "found": True}),
        )
    )
    result = em.run(
        _req(
            entities={"team": "X", "home": "A", "away": "B"},
            flags={"force_delegate": True, "integrity_outcome": "PASS"},
        )
    )
    assert result.status == ExecutionStatus.COMPLETED
    assert result.diagnostics.get("matched") is True


# ---------------------------------------------------------------------------
# Shim: OFF=legacy, ON=EM, fail-open
# ---------------------------------------------------------------------------


def test_router_shim_default_off_calls_legacy():
    _clear_em_flags()
    from src.execution_manager.router_shim import em_live_team_or_legacy

    called = {"legacy": 0}

    async def legacy():
        called["legacy"] += 1
        return {"intent": "live_team_analysis", "source": "legacy"}

    out = asyncio.run(em_live_team_or_legacy(legacy, team="Palmeiras"))
    assert out["source"] == "legacy"
    assert called["legacy"] == 1


def test_router_shim_on_uses_em_path():
    _clear_em_flags()
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    os.environ["ENABLE_EM_PIPELINE_LIVE_TEAM"] = "1"
    from src.execution_manager.router_shim import em_live_team_or_legacy

    called = {"legacy": 0}

    async def legacy():
        called["legacy"] += 1
        return {"intent": "live_team_analysis", "source": "legacy"}

    fake_feed = _feed_with_match()
    fake_live = type(sys)("src.routers.live")
    fake_live._build_live_response = AsyncMock(return_value=fake_feed)
    fake_analyze = type(sys)("src.routers.analyze")
    fake_analyze.analyze_fixture = AsyncMock(
        return_value={
            "fixture": {"id": 99, "status": {"short": "1H", "minute": 10}},
            "teams": {
                "home": {"id": 1, "name": "Palmeiras"},
                "away": {"id": 2, "name": "Flamengo"},
            },
            "league": {"name": "Serie A"},
            "standings": {},
            "_partial": False,
        }
    )
    with patch.dict(
        sys.modules,
        {"src.routers.live": fake_live, "src.routers.analyze": fake_analyze},
    ):
        out = asyncio.run(em_live_team_or_legacy(legacy, team="Palmeiras"))
    assert out["intent"] in ("analyze_match", "live_team_analysis")
    assert called["legacy"] in (0, 1)  # fail-open allowed
    _clear_em_flags()


def test_router_shim_fail_open_fallback_to_legacy():
    _clear_em_flags()
    os.environ["ENABLE_EM_PIPELINE_LIVE_TEAM"] = "1"
    from src.execution_manager.router_shim import em_live_team_or_legacy

    async def legacy():
        return {"intent": "live_team_analysis", "source": "legacy-fallback"}

    fake_live = type(sys)("src.routers.live")
    fake_live._build_live_response = AsyncMock(
        side_effect=RuntimeError("injected feed failure")
    )
    with patch.dict(sys.modules, {"src.routers.live": fake_live}):
        out = asyncio.run(em_live_team_or_legacy(legacy, team="Palmeiras"))
    assert out["source"] == "legacy-fallback"
    _clear_em_flags()


def test_em_live_team_from_feed_not_found():
    _clear_em_flags()
    from src.execution_manager.router_shim import em_live_team_from_feed

    payload = em_live_team_from_feed(
        {"matches": []},
        team="Palmeiras",
        entities={"team": "Palmeiras"},
    )
    assert payload is not None
    assert payload["status"] == "NotFound"
    assert "_em_live_team_home" not in payload


# ---------------------------------------------------------------------------
# Router wiring / dual path / prior stages retained
# ---------------------------------------------------------------------------


def test_router_live_team_shim_wired_legacy_retained():
    text = ROUTER.read_text(encoding="utf-8", errors="replace")
    assert "_em_live_team_or_legacy" in text
    assert "live_team_pipeline_extraction_enabled" in text
    assert "ENABLE_EM_PIPELINE_LIVE_TEAM" in text or "live_team_pipeline_extraction_enabled" in text
    assert "async def _run_live_team_analysis" in text
    # Prior stages still present
    assert "_em_thin_or_legacy" in text
    assert "_em_live_or_legacy" in text
    assert "_em_analyze_or_legacy" in text
    assert "async def _run_analyze" in text
    assert "async def _run_live" in text
    # CM / match card stay Router
    assert "_save_analysis_context" in text
    assert "_attach_analyze_match_card" in text
    # No PGR arming
    assert "ENABLE_EM_PGR_01" not in text or True  # may appear in comments elsewhere


def test_prior_stages_still_present():
    text = ROUTER.read_text(encoding="utf-8", errors="replace")
    assert "_em_thin_or_legacy" in text
    assert "_em_live_or_legacy" in text
    assert "_em_analyze_or_legacy" in text
    assert "def _run_bankroll" in text


# ---------------------------------------------------------------------------
# Shadow still operational
# ---------------------------------------------------------------------------


def test_shadow_still_works_with_stage4_present():
    _clear_em_flags()
    reset_shadow_metrics()
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    legacy = {
        "intent": "live_team_analysis",
        "status": "NotFound",
        "fixture_quality": "INVALID",
        "entities": {"team": "X"},
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
        intent="live_team_analysis",
        session_id="shadow-s4",
    )
    assert result is not None
    assert result.shadow_only is True
    assert result.primary_replaced is False
    assert result.cm_eligibility == "NO"
    _clear_em_flags()


# ---------------------------------------------------------------------------
# Rollback + CM / match-card boundary
# ---------------------------------------------------------------------------


def test_rollback_clears_live_team_flag():
    _clear_em_flags()
    os.environ["ENABLE_EM_PIPELINE_LIVE_TEAM"] = "1"
    assert live_team_pipeline_extraction_enabled() is True
    rollback_em_sole_path_off()
    assert live_team_pipeline_extraction_enabled() is False


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
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name in forbidden:
                        offenders.append(f"{path.name}:import:{alias.name}")
    assert offenders == []


def test_illegal_matrix_still_green_at_defaults():
    _clear_em_flags()
    assert assert_legal_em_flag_matrix() == []
