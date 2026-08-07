"""
Mission 033 Phase 4 Progressive Extraction Stage 1 — thin reports only.

DEFAULT OFF → legacy. ON (tests) → EM thin path. Shadow still OK.
Live / analyze / live_team untouched. No PGR / Activation.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.execution_manager import (
    ExecutionManager,
    ExecutionMode,
    ExecutionRequest,
    ExecutionStatus,
    assert_legal_em_flag_matrix,
    em_flag_snapshot,
    em_flags_all_off,
    thin_pipeline_extraction_enabled,
)
from src.execution_manager.flags import (
    EM_BOOL_FLAGS,
    rollback_em_all_off,
    rollback_em_sole_path_off,
)
from src.execution_manager.ports import InertDbReadPort, PortBundle, ProductionDbReadPort
from src.execution_manager.shadow import maybe_em_shadow_observe, reset_shadow_metrics

REPO_ROOT = Path(__file__).resolve().parents[3]
SOT = REPO_ROOT / "artifacts" / "aurora"
EM_PKG = SOT / "src" / "execution_manager"
ROUTER = SOT / "src" / "routers" / "copilot_unified_router.py"

THIN_FLAGS = (
    "ENABLE_EM_PIPELINE_BANKROLL",
    "ENABLE_EM_PIPELINE_LEARNING",
    "ENABLE_EM_PIPELINE_KNOWLEDGE",
)

THIN_KEYS = [
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


def _req(pipeline: str, *, run_id: str = "t1", entities: dict | None = None):
    return ExecutionRequest(
        run_id=run_id,
        pipeline_id=pipeline,
        session_id="s-stage1",
        mode=ExecutionMode.PRIMARY,
        entities=dict(entities or {}),
    )


def _sample_stats() -> dict:
    return {
        "total_predictions": 40,
        "wins": 22,
        "losses": 10,
        "pending": 8,
        "current_accuracy": 68.75,
        "roi_pct": 4.2,
        "best_market": "over_25",
        "worst_market": "btts",
        "best_league": "Serie A",
        "market_breakdown": [
            {"rule": "over_25", "accuracy": 70.0, "wins": 7, "losses": 3},
            {"rule": "btts", "accuracy": 40.0, "wins": 2, "losses": 4},
        ],
        "league_breakdown": [
            {"league": "Serie A", "accuracy": 66.0, "wins": 6, "losses": 3},
        ],
    }


# ---------------------------------------------------------------------------
# Defaults OFF / flags
# ---------------------------------------------------------------------------


def test_stage1_flags_default_off():
    _clear_em_flags()
    assert em_flags_all_off() is True
    for name in THIN_FLAGS:
        assert thin_pipeline_extraction_enabled(name.split("_")[-1].lower()) is False
    assert thin_pipeline_extraction_enabled("bankroll") is False
    assert thin_pipeline_extraction_enabled("learning") is False
    assert thin_pipeline_extraction_enabled("knowledge") is False
    assert thin_pipeline_extraction_enabled("live") is False
    assert thin_pipeline_extraction_enabled("analyze") is False
    snap = em_flag_snapshot()
    assert snap["phase4_stage1_thin_reports"] is True
    assert snap["phase4_stage2_not_started"] is False
    assert snap["phase4_stage2_live"] is True
    assert snap["phase4_thin_defaults_off"] is True
    assert snap["phase4_live_defaults_off"] is True
    assert snap["phase5_activation_not_started"] is False
    assert snap["phase5_pgr01"] is True
    assert snap["phase5_pgr02_not_started"] is True


def test_thin_flag_on_enables_only_that_pipeline():
    _clear_em_flags()
    os.environ["ENABLE_EM_PIPELINE_BANKROLL"] = "1"
    assert thin_pipeline_extraction_enabled("bankroll") is True
    assert thin_pipeline_extraction_enabled("learning") is False
    assert thin_pipeline_extraction_enabled("knowledge") is False
    _clear_em_flags()


# ---------------------------------------------------------------------------
# EM thin handlers
# ---------------------------------------------------------------------------


def test_em_thin_bankroll_parity_keys():
    _clear_em_flags()
    em = ExecutionManager(ports=PortBundle(db=InertDbReadPort(stats=_sample_stats())))
    result = em.run(_req("bankroll", run_id="br-1"))
    assert result.status == ExecutionStatus.COMPLETED
    for k in THIN_KEYS:
        assert k in result.payload
    assert result.payload["intent"] == "bankroll_review"
    assert result.payload["entities"]["total_predictions"] == 40
    assert result.diagnostics.get("phase4_stage1") is True


def test_em_thin_learning_and_knowledge():
    _clear_em_flags()
    ports = PortBundle(
        db=InertDbReadPort(
            stats=_sample_stats(),
            knowledge=[
                {
                    "category": "market_rule",
                    "title": "Over 2.5",
                    "description": "Prefer strong attacks",
                    "confidence": 0.8,
                }
            ],
        )
    )
    em = ExecutionManager(ports=ports)
    learn = em.run(_req("learning", run_id="lr-1"))
    assert learn.status == ExecutionStatus.COMPLETED
    assert learn.payload["intent"] == "learning_recap"
    know = em.run(_req("knowledge", run_id="kn-1", entities={"query": "over"}))
    assert know.status == ExecutionStatus.COMPLETED
    assert know.payload["intent"] == "knowledge_search"
    assert know.payload["knowledge_notes"]
    assert "Over 2.5" in know.payload["knowledge_notes"][0]


def test_em_thin_matches_legacy_bankroll_shape():
    """EM bankroll vs legacy assembler with same stats — key parity."""
    _clear_em_flags()
    stats = _sample_stats()
    from src.execution_manager.pipelines.thin_reports import _assemble_bankroll_payload

    em = ExecutionManager(ports=PortBundle(db=InertDbReadPort(stats=stats)))
    em_result = em.run(_req("bankroll", run_id="parity-1"))
    assert em_result.status == ExecutionStatus.COMPLETED
    em_payload = em_result.payload
    direct = _assemble_bankroll_payload(stats)
    # Drop brain (may include dynamic meta) for structural compare of core fields
    for payload in (em_payload, direct):
        assert payload["intent"] == "bankroll_review"
        assert payload["entities"] == {
            "total_predictions": 40,
            "wins": 22,
            "losses": 10,
            "pending": 8,
            "accuracy_pct": 68.75,
            "roi_pct": 4.2,
        }
    assert em_payload["executive_summary"] == direct["executive_summary"]
    assert em_payload["final_recommendation"] == direct["final_recommendation"]
    for k in THIN_KEYS:
        assert k in em_payload


def test_router_shim_default_off_calls_legacy():
    _clear_em_flags()
    from src.execution_manager.router_shim import em_thin_or_legacy

    called = {"legacy": 0}

    def legacy():
        called["legacy"] += 1
        return {"intent": "bankroll_review", "source": "legacy"}

    out = em_thin_or_legacy("bankroll", legacy)
    assert out["source"] == "legacy"
    assert called["legacy"] == 1


def test_router_shim_on_uses_em_path():
    _clear_em_flags()
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"  # I1-legal when asserting
    os.environ["ENABLE_EM_PIPELINE_BANKROLL"] = "1"
    from src.execution_manager.router_shim import em_thin_or_legacy

    called = {"legacy": 0}

    def legacy():
        called["legacy"] += 1
        return {"intent": "bankroll_review", "source": "legacy"}

    with patch(
        "src.execution_manager.ports.ProductionDbReadPort.learning_stats",
        return_value=_sample_stats(),
    ):
        out = em_thin_or_legacy("bankroll", legacy)
    assert out["intent"] == "bankroll_review"
    assert out.get("source") != "legacy"
    assert called["legacy"] == 0
    assert "executive_summary" in out
    _clear_em_flags()


def test_router_shim_fail_open_fallback_to_legacy():
    _clear_em_flags()
    os.environ["ENABLE_EM_PIPELINE_BANKROLL"] = "1"
    from src.execution_manager.router_shim import em_thin_or_legacy

    def legacy():
        return {"intent": "bankroll_review", "source": "legacy-fallback"}

    with patch(
        "src.execution_manager.step_runner.ExecutionManager.run",
        side_effect=RuntimeError("injected em failure"),
    ):
        out = em_thin_or_legacy("bankroll", legacy)
    assert out["source"] == "legacy-fallback"
    _clear_em_flags()


def test_other_pipelines_stage1_coexists_with_later_stages():
    """Stage 1 thin shim retained; Stage 2/3/4 shims may coexist."""
    _clear_em_flags()
    text = ROUTER.read_text(encoding="utf-8", errors="replace")
    assert "_em_thin_or_legacy" in text
    assert "_em_live_or_legacy" in text
    assert "_em_analyze_or_legacy" in text
    assert "_em_live_team_or_legacy" in text
    assert "async def _run_analyze" in text
    assert "async def _run_live_team_analysis" in text


# ---------------------------------------------------------------------------
# Shadow still operational
# ---------------------------------------------------------------------------


def test_shadow_still_works_with_stage1_present():
    _clear_em_flags()
    reset_shadow_metrics()
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    legacy = {
        "intent": "bankroll_review",
        "executive_summary": "x",
        "entities": {},
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
        intent="bankroll_review",
        session_id="shadow-s1",
    )
    assert result is not None
    assert result.shadow_only is True
    assert result.primary_replaced is False
    assert result.cm_eligibility == "NO"
    _clear_em_flags()


# ---------------------------------------------------------------------------
# Rollback + CM boundary
# ---------------------------------------------------------------------------


def test_rollback_clears_thin_flags():
    _clear_em_flags()
    os.environ["ENABLE_EM_PIPELINE_BANKROLL"] = "1"
    os.environ["ENABLE_EM_PIPELINE_LEARNING"] = "1"
    os.environ["ENABLE_EM_PIPELINE_KNOWLEDGE"] = "1"
    assert thin_pipeline_extraction_enabled("bankroll") is True
    rollback_em_sole_path_off()
    assert thin_pipeline_extraction_enabled("bankroll") is False
    assert thin_pipeline_extraction_enabled("learning") is False
    assert thin_pipeline_extraction_enabled("knowledge") is False


def test_em_package_no_cm_writes():
    forbidden = {"_save_analysis_context", "attach_match_card"}
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


def test_legacy_bodies_retained_dual_path():
    text = ROUTER.read_text(encoding="utf-8", errors="replace")
    assert "def _run_bankroll" in text
    assert "def _run_learning" in text
    assert "def _run_knowledge" in text
    assert "_em_thin_or_legacy" in text
    assert "async def _run_analyze" in text
    assert "async def _run_live" in text


def test_pipeline_on_without_shadow_is_illegal_i1():
    _clear_em_flags()
    os.environ["ENABLE_EM_PIPELINE_BANKROLL"] = "1"
    with pytest.raises(Exception):
        assert_legal_em_flag_matrix(raise_on_illegal=True)
    # With Shadow evidence armed, legal for operator tests.
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "1"
    assert assert_legal_em_flag_matrix(raise_on_illegal=True) == []
    _clear_em_flags()


def test_production_db_port_is_read_only_surface():
    port = ProductionDbReadPort()
    assert callable(port.learning_stats)
    assert callable(port.knowledge_search)
    assert callable(port.memory_recall)
    # No write attributes
    assert not hasattr(port, "save")
    assert not hasattr(port, "write")
