"""
Mission 016 Phase 5 — Progressive Gate Review (REGRA 25) — PGR-01 ONLY.

Each activation increase is an independent gate. This module operationalizes
the first gate only:

  PGR-01 → STAGE1_BOUNDARY_1PCT (1%)

Higher gates (PGR-02 @ 5%, PGR-03 @ 10%, …) exist as constants / labels only
and MUST remain locked this mission. No auto-advance. No Phase 6 Stabilization.

Repo default: all PGR gates OFF. Operators enable PGR-01 explicitly via env.
Mirror drift remains OPEN — PGR-01 is controlled/gated enablement of the
already-authorized 1% stage behind flags (not full-env production Activation).
ENABLE_LANGGRAPH_STATE stays OFF.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Literal

logger = logging.getLogger(__name__)

PGRId = Literal["PGR-01", "PGR-02", "PGR-03", "PGR-04", "PGR-05", "PGR-06"]

# REGRA 25 ladder — only PGR-01 is unlockable this mission.
PGR_LADDER: tuple[dict[str, Any], ...] = (
    {
        "id": "PGR-01",
        "pct": 1,
        "stage_name": "STAGE1_BOUNDARY_1PCT",
        "env_enable": "AURORA_PGR_01_ENABLE",
        "authorized_this_mission": True,
    },
    {
        "id": "PGR-02",
        "pct": 5,
        "stage_name": "STAGE2_ANALYZE_5PCT",
        "env_enable": "AURORA_PGR_02_ENABLE",
        "authorized_this_mission": False,
    },
    {
        "id": "PGR-03",
        "pct": 10,
        "stage_name": "STAGE3_NOTE_10PCT",
        "env_enable": "AURORA_PGR_03_ENABLE",
        "authorized_this_mission": False,
    },
    {
        "id": "PGR-04",
        "pct": 25,
        "stage_name": "STAGE4_25PCT",
        "env_enable": "AURORA_PGR_04_ENABLE",
        "authorized_this_mission": False,
    },
    {
        "id": "PGR-05",
        "pct": 50,
        "stage_name": "STAGE5_50PCT",
        "env_enable": "AURORA_PGR_05_ENABLE",
        "authorized_this_mission": False,
    },
    {
        "id": "PGR-06",
        "pct": 100,
        "stage_name": "STAGE6_100PCT",
        "env_enable": "AURORA_PGR_06_ENABLE",
        "authorized_this_mission": False,
    },
)

PGR01_ID = "PGR-01"
PGR01_PCT = 1
PGR01_STAGE = "STAGE1_BOUNDARY_1PCT"
_ENV_PGR_01 = "AURORA_PGR_01_ENABLE"

_metrics_lock = threading.Lock()
_METRICS: dict[str, int] = {
    "pgr01_armed": 0,
    "pgr01_blocked_missing_flag": 0,
    "pgr01_rollback": 0,
    "pgr_higher_gate_blocked": 0,
}


def reset_pgr_metrics() -> None:
    with _metrics_lock:
        for k in _METRICS:
            _METRICS[k] = 0


def pgr_metrics_snapshot() -> dict[str, int]:
    with _metrics_lock:
        return dict(_METRICS)


def _bump(metric: str) -> None:
    with _metrics_lock:
        _METRICS[metric] = int(_METRICS.get(metric, 0)) + 1


def _flag_truthy(env_name: str) -> bool:
    raw = (os.environ.get(env_name) or "0").strip().lower()
    return raw in {"1", "true", "on", "yes"}


def pgr01_enable_flag() -> bool:
    """True when operator set AURORA_PGR_01_ENABLE (independent REGRA 25 gate)."""
    return _flag_truthy(_ENV_PGR_01)


def pgr_gate_definition(gate_id: str) -> dict[str, Any] | None:
    for row in PGR_LADDER:
        if row["id"] == gate_id:
            return dict(row)
    return None


def higher_pgr_gate_attempted() -> bool:
    """True if any PGR-02+ enable env is set (must fail-closed this mission)."""
    for row in PGR_LADDER:
        if row["id"] == PGR01_ID:
            continue
        if _flag_truthy(str(row["env_enable"])):
            return True
    return False


def assert_no_higher_pgr_gates(*, bump: bool = True) -> bool:
    """
    Fail-closed helper: higher PGR enable flags must not unlock this mission.
    Returns True when safe (no higher gates armed).
    """
    if higher_pgr_gate_attempted():
        if bump:
            _bump("pgr_higher_gate_blocked")
        logger.warning(
            "[AUDIT] PGR higher_gate_blocked — only PGR-01 authorized this mission"
        )
        return False
    return True


def pgr01_armed() -> bool:
    """
    PGR-01 operator arming flag only (does not alone activate the funnel).

    Full live activation also requires funnel pct=1 + boundary funnel flag
    (see sole_writer_funnel / pgr01_activation_live).
    """
    if higher_pgr_gate_attempted():
        _bump("pgr_higher_gate_blocked")
        return False
    return pgr01_enable_flag()


def require_pgr01_for_stage1(*, force: bool = False) -> bool:
    """
    Independent gate check for STAGE1_BOUNDARY_1PCT live path.

    force=True: tests may bypass PGR arming (Phase 4 force semantics retained).
    """
    if force:
        return True
    if not assert_no_higher_pgr_gates():
        return False
    if not pgr01_enable_flag():
        _bump("pgr01_blocked_missing_flag")
        logger.info(
            "[AUDIT] PGR-01 blocked_missing_flag — set %s=1 with PO approval "
            "to arm STAGE1_BOUNDARY_1PCT",
            _ENV_PGR_01,
        )
        return False
    _bump("pgr01_armed")
    return True


def rollback_pgr01_to_off() -> dict[str, Any]:
    """
    Fail-safe rollback for PGR-01: clear PGR-01 enable + funnel pct → 0%.

    Does not touch shadow flags. Does not enable higher gates.
    """
    os.environ.pop(_ENV_PGR_01, None)
    try:
        from src.conversation.sole_writer_funnel import rollback_funnel_to_off

        rollback_funnel_to_off()
    except Exception as exc:
        os.environ.pop("AURORA_SOLE_WRITER_FUNNEL_PCT", None)
        logger.warning("[AUDIT] PGR-01 rollback funnel helper skipped (%s)", exc)
    _bump("pgr01_rollback")
    logger.warning("[AUDIT] PGR-01 rollback_to_off pct=0 pgr01=OFF")
    return pgr_flag_snapshot()


def operator_enable_pgr01_instructions() -> str:
    """Operator runbook snippet (documentation / snapshot)."""
    return (
        "# PGR-01 ONLY (1% / STAGE1_BOUNDARY_1PCT) — controlled gated enablement\n"
        "# Repo default remains OFF. Mirror drift OPEN ⇒ not full-env Activation.\n"
        "set AURORA_PGR_01_ENABLE=1\n"
        "set AURORA_SOLE_WRITER_FUNNEL_PCT=1\n"
        "set ENABLE_STS_WRITE_FUNNEL_BOUNDARY=1\n"
        "set ENABLE_LANGGRAPH_STATE=0\n"
        "# Do NOT set AURORA_PGR_02_ENABLE (or higher) — locked this mission\n"
        "# Do NOT set AURORA_FUNNEL_PO_STAGE_UNLOCK unless PO approved >1%\n"
        "#\n"
        "# Instant rollback:\n"
        "#   unset AURORA_PGR_01_ENABLE\n"
        "#   unset AURORA_SOLE_WRITER_FUNNEL_PCT\n"
        "#   OR call rollback_pgr01_to_off()\n"
    )


def pgr_flag_snapshot() -> dict[str, Any]:
    """Read-only PGR posture for reports / Validation Contract."""
    gates = []
    for row in PGR_LADDER:
        gates.append(
            {
                "id": row["id"],
                "pct": row["pct"],
                "stage_name": row["stage_name"],
                "authorized_this_mission": row["authorized_this_mission"],
                "enable_flag_on": _flag_truthy(str(row["env_enable"])),
                "env_enable": row["env_enable"],
            }
        )
    return {
        "active_gate": "PGR-01" if pgr01_enable_flag() and assert_no_higher_pgr_gates(bump=False) else "NONE",
        "pgr01_enable": pgr01_enable_flag(),
        "pgr01_pct": PGR01_PCT,
        "pgr01_stage": PGR01_STAGE,
        "higher_gates_locked": True,
        "higher_gate_attempted": higher_pgr_gate_attempted(),
        "auto_advance": False,
        "phase6_not_started": True,
        "pgr02_not_started": True,
        "gates": gates,
        "metrics": pgr_metrics_snapshot(),
        "operator_enable_runbook": operator_enable_pgr01_instructions(),
        "mirror_drift_open": True,
        "production_langgraph_write_required": False,
        "legacy_writers_present": True,
    }
