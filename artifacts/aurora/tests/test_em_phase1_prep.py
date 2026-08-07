"""Mission 030 Phase 1 Prep — flags OFF + baseline fixtures (no product mutation)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
OBS = REPO_ROOT / "observations" / "execution_manager_impl_030"
BASELINES = OBS / "baselines"
SOT = REPO_ROOT / "artifacts" / "aurora"

EM_BOOL_FLAGS = [
    "ENABLE_EXECUTION_MANAGER_SHADOW",
    "ENABLE_EXECUTION_MANAGER",
    "ENABLE_EM_PIPELINE_BANKROLL",
    "ENABLE_EM_PIPELINE_LEARNING",
    "ENABLE_EM_PIPELINE_KNOWLEDGE",
    "ENABLE_EM_PIPELINE_LIVE",
    "ENABLE_EM_PIPELINE_ANALYZE",
    "ENABLE_EM_PIPELINE_LIVE_TEAM",
    "ENABLE_EM_PGR_01",
    "ENABLE_EM_PGR_02",
    "ENABLE_EM_PGR_03",
    "ENABLE_EM_PGR_04",
    "ENABLE_EM_PGR_05",
    "ENABLE_EM_PGR_06",
]

REQUIRED_BASELINES = [
    "appendix_a_keys.json",
    "hard_abort_blocked_payload_shape.json",
    "analyze_success_payload_keys.json",
    "live_payload_keys.json",
    "thin_payload_keys.json",
]


def _env_off(name: str) -> bool:
    return (os.environ.get(name) or "0").strip().lower() in {"0", "false", "off", ""}


@pytest.mark.parametrize("flag", EM_BOOL_FLAGS)
def test_em_flag_defaults_off(flag: str) -> None:
    assert _env_off(flag), f"{flag} must default OFF in Phase 1"


def test_em_activation_pct_default_zero() -> None:
    pct = (os.environ.get("EM_ACTIVATION_PCT") or "0").strip()
    assert pct in {"0", "0.0", ""}


def test_em_package_absent_in_phase1() -> None:
    assert not (SOT / "src" / "execution_manager").exists()


@pytest.mark.parametrize("name", REQUIRED_BASELINES)
def test_baseline_fixture_present_and_json(name: str) -> None:
    path = BASELINES / name
    assert path.is_file(), path
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)


def test_hard_abort_invariants_m001() -> None:
    data = json.loads(
        (BASELINES / "hard_abort_blocked_payload_shape.json").read_text(encoding="utf-8")
    )
    inv = data["hard_abort_invariants"]
    assert inv["fixture_quality"] == "INVALID"
    assert inv["entity_invalid"] is True
    assert inv["markets_blocked"] is True
    assert inv["best_markets"] == []
    assert inv["match_card"] is None
    mapping = data["em_mapping_prep"]
    assert mapping["ExecutionResult.status"] == "Completed"
    assert mapping["abort_reason"] == "integrity_invalid_hard_abort"


def test_fixture_quality_closed_set_l001() -> None:
    data = json.loads(
        (BASELINES / "analyze_success_payload_keys.json").read_text(encoding="utf-8")
    )
    assert set(data["fixture_quality_closed_set_plan_3_2"]) == {
        "VALID",
        "PARTIAL",
        "INVALID",
        "VALID_LOCATED",
    }


def test_sot_run_helpers_still_in_router() -> None:
    router = (SOT / "src" / "routers" / "copilot_unified_router.py").read_text(
        encoding="utf-8", errors="replace"
    )
    for needle in (
        "async def _run_analyze",
        "async def _run_live",
        "def _run_bankroll",
        "def _run_learning",
        "def _run_knowledge",
        "def _save_analysis_context",
    ):
        assert needle in router
    integrity = (SOT / "src" / "core" / "fixture_integrity.py").read_text(
        encoding="utf-8", errors="replace"
    )
    assert "def blocked_integrity_payload" in integrity


def test_legacy_copilot_engine_present_residual() -> None:
    assert (SOT / "src" / "core" / "copilot_engine.py").is_file()
