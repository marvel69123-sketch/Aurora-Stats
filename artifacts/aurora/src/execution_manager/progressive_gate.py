"""
Mission 037 Phase 5 — Progressive Gate Review for Execution Manager (REGRA 25).

PGR-01 ONLY (1%) authorized this mission. PGR-02..06 remain locked until PO unlock.

  PGR-01 → EM_STAGE1_SOLE_PATH_1PCT (1%)
  PGR-02 → EM_STAGE2_SOLE_PATH_5PCT (5%)   — NOT unlocked
  PGR-03 → EM_STAGE3_SOLE_PATH_10PCT (10%) — NOT unlocked
  PGR-04 → EM_STAGE4_SOLE_PATH_25PCT (25%) — NOT unlocked
  PGR-05 → EM_STAGE5_SOLE_PATH_50PCT (50%) — NOT unlocked
  PGR-06 → EM_STAGE6_SOLE_PATH_100PCT (100%) — NOT unlocked

Repo default: all EM PGR gates OFF / EM_ACTIVATION_PCT=0.
Auto-advance = False. Instant rollback restores OFF / 0%.
Does not touch CM progressive_gate_review / Tool Use / Frozen engines.
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from typing import Any, Literal

logger = logging.getLogger(__name__)

EmPgrId = Literal["PGR-01", "PGR-02", "PGR-03", "PGR-04", "PGR-05", "PGR-06"]

_ACTIVATION_PCT_ENV = "EM_ACTIVATION_PCT"

EM_PGR_LADDER: tuple[dict[str, Any], ...] = (
    {
        "id": "PGR-01",
        "pct": 1,
        "stage_name": "EM_STAGE1_SOLE_PATH_1PCT",
        "env_enable": "ENABLE_EM_PGR_01",
        "authorized_this_mission": True,
    },
    {
        "id": "PGR-02",
        "pct": 5,
        "stage_name": "EM_STAGE2_SOLE_PATH_5PCT",
        "env_enable": "ENABLE_EM_PGR_02",
        "authorized_this_mission": False,
    },
    {
        "id": "PGR-03",
        "pct": 10,
        "stage_name": "EM_STAGE3_SOLE_PATH_10PCT",
        "env_enable": "ENABLE_EM_PGR_03",
        "authorized_this_mission": False,
    },
    {
        "id": "PGR-04",
        "pct": 25,
        "stage_name": "EM_STAGE4_SOLE_PATH_25PCT",
        "env_enable": "ENABLE_EM_PGR_04",
        "authorized_this_mission": False,
    },
    {
        "id": "PGR-05",
        "pct": 50,
        "stage_name": "EM_STAGE5_SOLE_PATH_50PCT",
        "env_enable": "ENABLE_EM_PGR_05",
        "authorized_this_mission": False,
    },
    {
        "id": "PGR-06",
        "pct": 100,
        "stage_name": "EM_STAGE6_SOLE_PATH_100PCT",
        "env_enable": "ENABLE_EM_PGR_06",
        "authorized_this_mission": False,
    },
)

PGR01_ID = "PGR-01"
PGR01_PCT = 1
PGR01_STAGE = "EM_STAGE1_SOLE_PATH_1PCT"
_ENV_PGR_01 = "ENABLE_EM_PGR_01"

# Mission 037 — only PGR-01 unlocked.
AUTHORIZED_HIGHEST_GATE = PGR01_ID
AUTHORIZED_OPERATIONAL_MAX_PCT = PGR01_PCT

_EM_ACTIVATION_LADDER_PCTS: frozenset[int] = frozenset({1, 5, 10, 25, 50, 100})

_metrics_lock = threading.Lock()
_METRICS: dict[str, int] = {
    "em_pgr01_armed": 0,
    "em_pgr01_blocked_missing_flag": 0,
    "em_pgr01_rollback": 0,
    "em_pgr_higher_gate_blocked": 0,
    "em_activation_blocked_high_pct": 0,
    "em_canary_selected": 0,
    "em_canary_skipped": 0,
}


def reset_em_pgr_metrics() -> None:
    with _metrics_lock:
        for k in _METRICS:
            _METRICS[k] = 0


def em_pgr_metrics_snapshot() -> dict[str, int]:
    with _metrics_lock:
        return dict(_METRICS)


def _bump(metric: str) -> None:
    with _metrics_lock:
        _METRICS[metric] = int(_METRICS.get(metric, 0)) + 1


def _flag_truthy(env_name: str) -> bool:
    raw = (os.environ.get(env_name) or "0").strip().lower()
    return raw in {"1", "true", "on", "yes"}


def parse_em_activation_pct(raw: str | None) -> int:
    """Parse activation pct; invalid / non-ladder → 0 (fail-closed)."""
    if raw is None or not str(raw).strip():
        return 0
    try:
        val = float(str(raw).strip())
    except (TypeError, ValueError):
        return 0
    ival = int(val) if val == int(val) else -1
    if ival not in _EM_ACTIVATION_LADDER_PCTS:
        return 0
    return ival


def get_configured_em_activation_pct() -> int:
    """Raw configured EM_ACTIVATION_PCT before PGR gate (observability)."""
    return parse_em_activation_pct(os.environ.get(_ACTIVATION_PCT_ENV))


def pgr01_enable_flag() -> bool:
    """True when operator set ENABLE_EM_PGR_01."""
    return _flag_truthy(_ENV_PGR_01)


def em_pgr_gate_definition(gate_id: str) -> dict[str, Any] | None:
    for row in EM_PGR_LADDER:
        if row["id"] == gate_id:
            return dict(row)
    return None


def higher_em_pgr_gate_attempted() -> bool:
    """
    True if any PGR above AUTHORIZED_HIGHEST_GATE (PGR-01) is armed.

    Mission 037: PGR-02..06 must remain locked.
    """
    past_authorized = False
    for row in EM_PGR_LADDER:
        if row["id"] == AUTHORIZED_HIGHEST_GATE:
            past_authorized = True
            continue
        if not past_authorized:
            continue
        if _flag_truthy(str(row["env_enable"])):
            return True
    return False


def assert_no_higher_em_pgr_gates(*, bump: bool = True) -> bool:
    """Fail-closed: gates above PGR-01 must not unlock. True when safe."""
    if higher_em_pgr_gate_attempted():
        if bump:
            _bump("em_pgr_higher_gate_blocked")
        logger.warning(
            "[AUDIT] EM PGR higher_gate_blocked — only PGR-01 authorized "
            "(PGR-02+ await PO)"
        )
        return False
    return True


def require_em_pgr01(*, force: bool = False) -> bool:
    """
    Independent gate check for EM_STAGE1_SOLE_PATH_1PCT.

    force=True: tests may bypass PGR arming for isolated unit checks.
    """
    if force:
        return True
    if not assert_no_higher_em_pgr_gates():
        return False
    if not pgr01_enable_flag():
        _bump("em_pgr01_blocked_missing_flag")
        logger.info(
            "[AUDIT] EM PGR-01 blocked_missing_flag — set %s=1 with PO approval "
            "to arm EM_STAGE1_SOLE_PATH_1PCT",
            _ENV_PGR_01,
        )
        return False
    _bump("em_pgr01_armed")
    return True


def pgr01_armed() -> bool:
    """Operator arming flag only (does not alone activate sole-path traffic)."""
    if higher_em_pgr_gate_attempted():
        _bump("em_pgr_higher_gate_blocked")
        return False
    return pgr01_enable_flag()


def get_effective_em_activation_pct() -> int:
    """
    Effective progressive activation percentage for EM sole-path.

    Default 0. Mission 037:
      - configured 1% effective only when PGR-01 is armed
      - configured >1% without higher PO unlock → fail-closed 0
      - PGR-02+ armed → fail-closed 0
    """
    configured = get_configured_em_activation_pct()
    if configured <= 0:
        return 0
    if configured > AUTHORIZED_OPERATIONAL_MAX_PCT:
        _bump("em_activation_blocked_high_pct")
        logger.warning(
            "[AUDIT] EM_ACTIVATION_PCT blocked_high_pct configured=%s "
            "authorized_max=%s (PGR-01 only; await PO for PGR-02+)",
            configured,
            AUTHORIZED_OPERATIONAL_MAX_PCT,
        )
        return 0
    if higher_em_pgr_gate_attempted():
        _bump("em_pgr_higher_gate_blocked")
        return 0
    if configured == PGR01_PCT:
        if not require_em_pgr01(force=False):
            return 0
        return configured
    return 0


def em_activation_stage_name(pct: int | None = None) -> str:
    p = get_effective_em_activation_pct() if pct is None else int(pct)
    if p <= 0:
        return "OFF_0"
    if p == 1:
        return PGR01_STAGE
    if p == 5:
        return "EM_STAGE2_SOLE_PATH_5PCT"
    if p == 10:
        return "EM_STAGE3_SOLE_PATH_10PCT"
    if p == 25:
        return "EM_STAGE4_SOLE_PATH_25PCT"
    if p == 50:
        return "EM_STAGE5_SOLE_PATH_50PCT"
    if p >= 100:
        return "EM_STAGE6_SOLE_PATH_100PCT"
    return f"EM_PCT_{p}"


def in_em_canary_bucket(
    session_key: str | None,
    *,
    force: bool = False,
    pct: int | None = None,
) -> bool:
    """
    Deterministic canary selection for EM progressive %.

    force=True: tests only — treat as selected.
    """
    if force:
        return True
    effective = get_effective_em_activation_pct() if pct is None else int(pct)
    if effective <= 0:
        return False
    if effective >= 100:
        return True
    key = (session_key or "").strip() or "anonymous"
    digest = hashlib.sha256(f"aurora-em-pgr:{key}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100  # 0..99
    selected = bucket < effective
    _bump("em_canary_selected" if selected else "em_canary_skipped")
    return selected


def em_activation_posture_active() -> bool:
    """
    True when operator is attempting Progressive Activation (not Phase 4
    extraction-only force).

    Activation posture = master sole-path OR any PGR armed OR configured pct > 0.
    """
    if _flag_truthy("ENABLE_EXECUTION_MANAGER"):
        return True
    if any(_flag_truthy(str(row["env_enable"])) for row in EM_PGR_LADDER):
        return True
    return get_configured_em_activation_pct() > 0


def em_sole_path_canary_allows(
    session_key: str | None,
    *,
    force: bool = False,
) -> bool:
    """
    Progressive Activation canary gate for EM sole-path traffic.

    Requires master + effective pct (PGR-01 @ 1%) + canary bucket.
    Pipeline eligibility is checked by the caller / shim.
    """
    if force:
        return get_effective_em_activation_pct() >= 1 or require_em_pgr01(force=True)
    if not _flag_truthy("ENABLE_EXECUTION_MANAGER"):
        return False
    effective = get_effective_em_activation_pct()
    if effective <= 0:
        return False
    return in_em_canary_bucket(session_key, pct=effective)


def pipeline_may_use_em_path(
    pipeline_extraction_on: bool,
    session_key: str | None = "",
    *,
    force: bool = False,
) -> bool:
    """
    Unified shim decision:

    - Pipeline flag OFF → False (legacy).
    - Activation posture ON → require master + PGR effective pct + canary.
    - Phase 4 extraction-only (pipeline ON, no activation posture) → True (100%).
    """
    if not pipeline_extraction_on:
        return False
    if not em_activation_posture_active():
        return True
    return em_sole_path_canary_allows(session_key, force=force)


def rollback_em_pgr01_to_off() -> dict[str, Any]:
    """
    Fail-safe rollback for EM PGR-01: clear PGR-01 enable + activation pct → 0%.

    Does not touch Shadow. Does not enable PGR-02+. Does not clear pipeline flags
    (caller may use rollback_em_sole_path_off for full sole-path kill).
    """
    os.environ.pop(_ENV_PGR_01, None)
    os.environ[_ENV_PGR_01] = "0"
    os.environ.pop(_ACTIVATION_PCT_ENV, None)
    os.environ[_ACTIVATION_PCT_ENV] = "0"
    _bump("em_pgr01_rollback")
    logger.warning("[AUDIT] EM PGR-01 rollback_to_off pct=0 pgr01=OFF")
    return em_pgr_flag_snapshot()


def operator_enable_em_pgr01_instructions() -> str:
    """Operator runbook snippet for EM PGR-01."""
    return (
        "# EM PGR-01 (1% / EM_STAGE1_SOLE_PATH_1PCT) — controlled gated enablement\n"
        "# Repo default remains OFF. Shadow may stay armed independently.\n"
        "# Pipeline flags stay OFF unless intentionally included in canary scope.\n"
        "set ENABLE_EM_PGR_01=1\n"
        "set EM_ACTIVATION_PCT=1\n"
        "set ENABLE_EXECUTION_MANAGER=1\n"
        "set ENABLE_EXECUTION_MANAGER_SHADOW=1\n"
        "# Optional: arm eligible pipelines for canary sole-path (still DEFAULT OFF):\n"
        "# set ENABLE_EM_PIPELINE_ANALYZE=1\n"
        "# set ENABLE_EM_PIPELINE_LIVE=1\n"
        "# set ENABLE_EM_PIPELINE_BANKROLL=1\n"
        "# Do NOT set EM_ACTIVATION_PCT>1 without PGR-02+ PO unlock\n"
        "# Do NOT set ENABLE_EM_PGR_02..06 (locked this mission)\n"
        "# Auto-advance=False\n"
        "#\n"
        "# Instant rollback:\n"
        "#   set ENABLE_EM_PGR_01=0\n"
        "#   set EM_ACTIVATION_PCT=0\n"
        "#   OR call rollback_em_pgr01_to_off()\n"
    )


def _active_em_gate_id() -> str:
    if higher_em_pgr_gate_attempted():
        return "NONE"
    if pgr01_enable_flag() and get_effective_em_activation_pct() >= 1:
        return "PGR-01"
    if pgr01_enable_flag():
        return "PGR-01_ARMED_PCT_OFF"
    return "NONE"


def em_pgr_flag_snapshot() -> dict[str, Any]:
    """Read-only EM PGR posture for reports / Dual Reporting."""
    gates = []
    for row in EM_PGR_LADDER:
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
    effective = get_effective_em_activation_pct()
    return {
        "active_gate": _active_em_gate_id(),
        "pgr01_enable": pgr01_enable_flag(),
        "pgr01_pct": PGR01_PCT,
        "pgr01_stage": PGR01_STAGE,
        "configured_pct": get_configured_em_activation_pct(),
        "effective_pct": effective,
        "stage_name": em_activation_stage_name(effective),
        "authorized_highest_gate": AUTHORIZED_HIGHEST_GATE,
        "authorized_operational_max_pct": AUTHORIZED_OPERATIONAL_MAX_PCT,
        "higher_gates_locked": True,
        "higher_gate_attempted": higher_em_pgr_gate_attempted(),
        "auto_advance": False,
        "pgr02_not_started": True,
        "pgr03_not_started": True,
        "pgr04_not_started": True,
        "pgr05_not_started": True,
        "pgr06_not_started": True,
        "phase6_stabilization_not_started": True,
        "gates": gates,
        "metrics": em_pgr_metrics_snapshot(),
        "operator_enable_pgr01_runbook": operator_enable_em_pgr01_instructions(),
        "rollback_possible": True,
        "shadow_independent": True,
    }
