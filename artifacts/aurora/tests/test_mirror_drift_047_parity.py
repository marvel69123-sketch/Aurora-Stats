"""
Mission 047 — Mirror Drift parity probe.

Proves:
  - Deploy SoT remains artifacts/aurora/
  - CM + EM required modules present under aurora/ mirror
  - assess_*_mirror_drift() reports RESOLVED (not OPEN)
  - Critical runtime files byte-match SoT ↔ mirror
  - Defaults remain OFF (no flag arming in this mission)
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from src.conversation.migration_flag_controller import (
    _CM_MIRROR_MODULES,
    assess_cm_mirror_drift,
)
from src.execution_manager.flags import (
    _EM_MIRROR_MODULES,
    assess_em_mirror_drift,
    em_flags_all_off,
)


_CRITICAL_RELATIVE = (
    "src/routers/copilot_unified_router.py",
    "src/core/copilot_engine.py",
    "src/core/nl_router.py",
    "src/routers/analyze.py",
    "src/core/fixture_status.py",
    "src/execution_manager/__init__.py",
    "src/execution_manager/flags.py",
    "src/conversation/sport_topic_state.py",
    "src/conversation/migration_flag_controller.py",
)


def _repo_root() -> Path:
    # artifacts/aurora/tests/this_file.py → parents[3] = repo root
    return Path(__file__).resolve().parents[3]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_047_em_mirror_probe_resolved():
    probe = assess_em_mirror_drift()
    assert probe["deploy_sot"] == "artifacts/aurora/"
    assert probe["mirror_path"] == "aurora/"
    assert probe["mirror_drift_open"] is False
    assert probe["disposition"] == "RESOLVED"
    assert probe["missing_in_mirror"] == []
    assert probe["missing_in_sot"] == []
    assert list(probe["required_em_modules"]) == list(_EM_MIRROR_MODULES)


def test_047_cm_mirror_probe_resolved():
    probe = assess_cm_mirror_drift()
    assert probe["deploy_sot"] == "artifacts/aurora/"
    assert probe["mirror_path"] == "aurora/"
    assert probe["mirror_drift_open"] is False
    assert probe["disposition"] == "RESOLVED"
    assert probe["missing_in_mirror"] == []
    assert probe["missing_in_sot"] == []
    assert list(probe["required_cm_modules"]) == list(_CM_MIRROR_MODULES)


def test_047_critical_files_byte_match():
    root = _repo_root()
    sot = root / "artifacts" / "aurora"
    mirror = root / "aurora"
    for rel in _CRITICAL_RELATIVE:
        a = sot / rel
        b = mirror / rel
        assert a.is_file(), f"missing SoT {rel}"
        assert b.is_file(), f"missing mirror {rel}"
        assert _sha256(a) == _sha256(b), f"content drift: {rel}"


def test_047_em_pipelines_present_in_mirror():
    root = _repo_root()
    mirror_pipelines = root / "aurora" / "src" / "execution_manager" / "pipelines"
    for name in (
        "__init__.py",
        "analyze.py",
        "analyze_production.py",
        "live.py",
        "live_team_analyze.py",
        "thin_reports.py",
    ):
        assert (mirror_pipelines / name).is_file(), f"missing pipeline {name}"


def test_047_defaults_remain_off():
    assert em_flags_all_off() is True


def test_047_deploy_artifact_toml_points_at_sot():
    root = _repo_root()
    toml = root / "artifacts" / "api-server" / ".replit-artifact" / "artifact.toml"
    text = toml.read_text(encoding="utf-8")
    assert "artifacts/aurora" in text
    assert "aurora/start.sh" not in text or "artifacts/aurora/start.sh" in text
