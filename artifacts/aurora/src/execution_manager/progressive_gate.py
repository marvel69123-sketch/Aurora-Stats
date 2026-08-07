"""
Mission 042 Phase 5 — Progressive Gate Review for Execution Manager (REGRA 25).

PGR-06 ONLY (100%) authorized this mission (final PGR ladder rung).
PGR-01 (1%), PGR-02 (5%), PGR-03 (10%), PGR-04 (25%), and PGR-05 (50%) remain
re-armable when PGR-06 is off. Stabilization / Final Acceptance NOT started.

  PGR-01 → EM_STAGE1_SOLE_PATH_1PCT (1%)   — still available
  PGR-02 → EM_STAGE2_SOLE_PATH_5PCT (5%)   — still available
  PGR-03 → EM_STAGE3_SOLE_PATH_10PCT (10%) — still available
  PGR-04 → EM_STAGE4_SOLE_PATH_25PCT (25%) — still available
  PGR-05 → EM_STAGE5_SOLE_PATH_50PCT (50%) — still available
  PGR-06 → EM_STAGE6_SOLE_PATH_100PCT (100%) — authorized this mission

Repo default: all EM PGR gates OFF / EM_ACTIVATION_PCT=0 (even at 100% capability).
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
        "authorized_this_mission": True,
    },
    {
        "id": "PGR-03",
        "pct": 10,
        "stage_name": "EM_STAGE3_SOLE_PATH_10PCT",
        "env_enable": "ENABLE_EM_PGR_03",
        "authorized_this_mission": True,
    },
    {
        "id": "PGR-04",
        "pct": 25,
        "stage_name": "EM_STAGE4_SOLE_PATH_25PCT",
        "env_enable": "ENABLE_EM_PGR_04",
        "authorized_this_mission": True,
    },
    {
        "id": "PGR-05",
        "pct": 50,
        "stage_name": "EM_STAGE5_SOLE_PATH_50PCT",
        "env_enable": "ENABLE_EM_PGR_05",
        "authorized_this_mission": True,
    },
    {
        "id": "PGR-06",
        "pct": 100,
        "stage_name": "EM_STAGE6_SOLE_PATH_100PCT",
        "env_enable": "ENABLE_EM_PGR_06",
        "authorized_this_mission": True,
    },
)

PGR01_ID = "PGR-01"
PGR01_PCT = 1
PGR01_STAGE = "EM_STAGE1_SOLE_PATH_1PCT"
_ENV_PGR_01 = "ENABLE_EM_PGR_01"

PGR02_ID = "PGR-02"
PGR02_PCT = 5
PGR02_STAGE = "EM_STAGE2_SOLE_PATH_5PCT"
_ENV_PGR_02 = "ENABLE_EM_PGR_02"

PGR03_ID = "PGR-03"
PGR03_PCT = 10
PGR03_STAGE = "EM_STAGE3_SOLE_PATH_10PCT"
_ENV_PGR_03 = "ENABLE_EM_PGR_03"

PGR04_ID = "PGR-04"
PGR04_PCT = 25
PGR04_STAGE = "EM_STAGE4_SOLE_PATH_25PCT"
_ENV_PGR_04 = "ENABLE_EM_PGR_04"

PGR05_ID = "PGR-05"
PGR05_PCT = 50
PGR05_STAGE = "EM_STAGE5_SOLE_PATH_50PCT"
_ENV_PGR_05 = "ENABLE_EM_PGR_05"

PGR06_ID = "PGR-06"
PGR06_PCT = 100
PGR06_STAGE = "EM_STAGE6_SOLE_PATH_100PCT"
_ENV_PGR_06 = "ENABLE_EM_PGR_06"

# Mission 042 — PGR-01..PGR-06 unlocked; operational max = 100%.
AUTHORIZED_HIGHEST_GATE = PGR06_ID
AUTHORIZED_OPERATIONAL_MAX_PCT = PGR06_PCT

_EM_ACTIVATION_LADDER_PCTS: frozenset[int] = frozenset({1, 5, 10, 25, 50, 100})

_metrics_lock = threading.Lock()
_METRICS: dict[str, int] = {
    "em_pgr01_armed": 0,
    "em_pgr01_blocked_missing_flag": 0,
    "em_pgr01_rollback": 0,
    "em_pgr02_armed": 0,
    "em_pgr02_blocked_missing_flag": 0,
    "em_pgr02_rollback": 0,
    "em_pgr03_armed": 0,
    "em_pgr03_blocked_missing_flag": 0,
    "em_pgr03_rollback": 0,
    "em_pgr04_armed": 0,
    "em_pgr04_blocked_missing_flag": 0,
    "em_pgr04_rollback": 0,
    "em_pgr05_armed": 0,
    "em_pgr05_blocked_missing_flag": 0,
    "em_pgr05_rollback": 0,
    "em_pgr06_armed": 0,
    "em_pgr06_blocked_missing_flag": 0,
    "em_pgr06_rollback": 0,
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


def pgr02_enable_flag() -> bool:
    """True when operator set ENABLE_EM_PGR_02."""
    return _flag_truthy(_ENV_PGR_02)


def pgr03_enable_flag() -> bool:
    """True when operator set ENABLE_EM_PGR_03."""
    return _flag_truthy(_ENV_PGR_03)


def pgr04_enable_flag() -> bool:
    """True when operator set ENABLE_EM_PGR_04."""
    return _flag_truthy(_ENV_PGR_04)


def pgr05_enable_flag() -> bool:
    """True when operator set ENABLE_EM_PGR_05."""
    return _flag_truthy(_ENV_PGR_05)


def pgr06_enable_flag() -> bool:
    """True when operator set ENABLE_EM_PGR_06."""
    return _flag_truthy(_ENV_PGR_06)


def em_pgr_gate_definition(gate_id: str) -> dict[str, Any] | None:
    for row in EM_PGR_LADDER:
        if row["id"] == gate_id:
            return dict(row)
    return None


def higher_em_pgr_gate_attempted() -> bool:
    """
    True if any PGR above AUTHORIZED_HIGHEST_GATE (PGR-06) is armed.

    Mission 042: ladder ends at PGR-06; no higher PGR env exists.
    PGR-06 itself is authorized and does not count as "higher".
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
    """Fail-closed: gates above PGR-06 must not unlock. True when safe."""
    if higher_em_pgr_gate_attempted():
        if bump:
            _bump("em_pgr_higher_gate_blocked")
        logger.warning(
            "[AUDIT] EM PGR higher_gate_blocked — only PGR-01..PGR-06 authorized "
            "(Stabilization await PO)"
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


def require_em_pgr02(*, force: bool = False) -> bool:
    """
    Independent gate check for EM_STAGE2_SOLE_PATH_5PCT.

    force=True: tests may bypass PGR arming for isolated unit checks.
    """
    if force:
        return True
    if not assert_no_higher_em_pgr_gates():
        return False
    if not pgr02_enable_flag():
        _bump("em_pgr02_blocked_missing_flag")
        logger.info(
            "[AUDIT] EM PGR-02 blocked_missing_flag — set %s=1 with PO approval "
            "to arm EM_STAGE2_SOLE_PATH_5PCT",
            _ENV_PGR_02,
        )
        return False
    _bump("em_pgr02_armed")
    return True


def require_em_pgr03(*, force: bool = False) -> bool:
    """
    Independent gate check for EM_STAGE3_SOLE_PATH_10PCT.

    force=True: tests may bypass PGR arming for isolated unit checks.
    """
    if force:
        return True
    if not assert_no_higher_em_pgr_gates():
        return False
    if not pgr03_enable_flag():
        _bump("em_pgr03_blocked_missing_flag")
        logger.info(
            "[AUDIT] EM PGR-03 blocked_missing_flag — set %s=1 with PO approval "
            "to arm EM_STAGE3_SOLE_PATH_10PCT",
            _ENV_PGR_03,
        )
        return False
    _bump("em_pgr03_armed")
    return True


def require_em_pgr04(*, force: bool = False) -> bool:
    """
    Independent gate check for EM_STAGE4_SOLE_PATH_25PCT.

    force=True: tests may bypass PGR arming for isolated unit checks.
    """
    if force:
        return True
    if not assert_no_higher_em_pgr_gates():
        return False
    if not pgr04_enable_flag():
        _bump("em_pgr04_blocked_missing_flag")
        logger.info(
            "[AUDIT] EM PGR-04 blocked_missing_flag — set %s=1 with PO approval "
            "to arm EM_STAGE4_SOLE_PATH_25PCT",
            _ENV_PGR_04,
        )
        return False
    _bump("em_pgr04_armed")
    return True


def require_em_pgr05(*, force: bool = False) -> bool:
    """
    Independent gate check for EM_STAGE5_SOLE_PATH_50PCT.

    force=True: tests may bypass PGR arming for isolated unit checks.
    """
    if force:
        return True
    if not assert_no_higher_em_pgr_gates():
        return False
    if not pgr05_enable_flag():
        _bump("em_pgr05_blocked_missing_flag")
        logger.info(
            "[AUDIT] EM PGR-05 blocked_missing_flag — set %s=1 with PO approval "
            "to arm EM_STAGE5_SOLE_PATH_50PCT",
            _ENV_PGR_05,
        )
        return False
    _bump("em_pgr05_armed")
    return True


def require_em_pgr06(*, force: bool = False) -> bool:
    """
    Independent gate check for EM_STAGE6_SOLE_PATH_100PCT.

    force=True: tests may bypass PGR arming for isolated unit checks.
    """
    if force:
        return True
    if not assert_no_higher_em_pgr_gates():
        return False
    if not pgr06_enable_flag():
        _bump("em_pgr06_blocked_missing_flag")
        logger.info(
            "[AUDIT] EM PGR-06 blocked_missing_flag — set %s=1 with PO approval "
            "to arm EM_STAGE6_SOLE_PATH_100PCT",
            _ENV_PGR_06,
        )
        return False
    _bump("em_pgr06_armed")
    return True


def pgr01_armed() -> bool:
    """Operator arming flag only (does not alone activate sole-path traffic)."""
    if higher_em_pgr_gate_attempted():
        _bump("em_pgr_higher_gate_blocked")
        return False
    return pgr01_enable_flag()


def pgr02_armed() -> bool:
    """Operator arming flag only (does not alone activate sole-path traffic)."""
    if higher_em_pgr_gate_attempted():
        _bump("em_pgr_higher_gate_blocked")
        return False
    return pgr02_enable_flag()


def pgr03_armed() -> bool:
    """Operator arming flag only (does not alone activate sole-path traffic)."""
    if higher_em_pgr_gate_attempted():
        _bump("em_pgr_higher_gate_blocked")
        return False
    return pgr03_enable_flag()


def pgr04_armed() -> bool:
    """Operator arming flag only (does not alone activate sole-path traffic)."""
    if higher_em_pgr_gate_attempted():
        _bump("em_pgr_higher_gate_blocked")
        return False
    return pgr04_enable_flag()


def pgr05_armed() -> bool:
    """Operator arming flag only (does not alone activate sole-path traffic)."""
    if higher_em_pgr_gate_attempted():
        _bump("em_pgr_higher_gate_blocked")
        return False
    return pgr05_enable_flag()


def pgr06_armed() -> bool:
    """Operator arming flag only (does not alone activate sole-path traffic)."""
    if higher_em_pgr_gate_attempted():
        _bump("em_pgr_higher_gate_blocked")
        return False
    return pgr06_enable_flag()


def get_effective_em_activation_pct() -> int:
    """
    Effective progressive activation percentage for EM sole-path.

    Default 0. Mission 042:
      - configured 1% effective only when PGR-01 is armed
      - configured 5% effective only when PGR-02 is armed
      - configured 10% effective only when PGR-03 is armed
      - configured 25% effective only when PGR-04 is armed
      - configured 50% effective only when PGR-05 is armed
      - configured 100% effective only when PGR-06 is armed
      - configured >100% without higher PO unlock → fail-closed 0
    """
    configured = get_configured_em_activation_pct()
    if configured <= 0:
        return 0
    if configured > AUTHORIZED_OPERATIONAL_MAX_PCT:
        _bump("em_activation_blocked_high_pct")
        logger.warning(
            "[AUDIT] EM_ACTIVATION_PCT blocked_high_pct configured=%s "
            "authorized_max=%s (PGR-06 max 100%%; Stabilization await PO)",
            configured,
            AUTHORIZED_OPERATIONAL_MAX_PCT,
        )
        return 0
    if higher_em_pgr_gate_attempted():
        _bump("em_pgr_higher_gate_blocked")
        return 0
    if configured == PGR06_PCT:
        if not require_em_pgr06(force=False):
            return 0
        return configured
    if configured == PGR05_PCT:
        if not require_em_pgr05(force=False):
            return 0
        return configured
    if configured == PGR04_PCT:
        if not require_em_pgr04(force=False):
            return 0
        return configured
    if configured == PGR03_PCT:
        if not require_em_pgr03(force=False):
            return 0
        return configured
    if configured == PGR02_PCT:
        if not require_em_pgr02(force=False):
            return 0
        return configured
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
        return PGR02_STAGE
    if p == 10:
        return PGR03_STAGE
    if p == 25:
        return PGR04_STAGE
    if p == 50:
        return PGR05_STAGE
    if p >= 100:
        return PGR06_STAGE
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

    Requires master + effective pct (PGR-01 @ 1%, PGR-02 @ 5%, PGR-03 @ 10%,
    PGR-04 @ 25%, PGR-05 @ 50%, or PGR-06 @ 100%) + canary bucket. Pipeline
    eligibility is checked by the caller / shim.
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


def rollback_em_pgr02_to_off() -> dict[str, Any]:
    """
    Fail-safe rollback for EM PGR-02: clear PGR-02 enable + activation pct → 0%.

    Prefer clear rollback_to_off. Prior gate PGR-01 remains available to re-arm
    independently (ENABLE_EM_PGR_01 + EM_ACTIVATION_PCT=1 + master).
    Does not touch Shadow. Does not enable PGR-03+.
    """
    os.environ.pop(_ENV_PGR_02, None)
    os.environ[_ENV_PGR_02] = "0"
    os.environ.pop(_ACTIVATION_PCT_ENV, None)
    os.environ[_ACTIVATION_PCT_ENV] = "0"
    _bump("em_pgr02_rollback")
    logger.warning(
        "[AUDIT] EM PGR-02 rollback_to_off pct=0 pgr02=OFF (PGR-01 still available)"
    )
    return em_pgr_flag_snapshot()


def rollback_em_pgr03_to_off() -> dict[str, Any]:
    """
    Fail-safe rollback for EM PGR-03: clear PGR-03 enable + activation pct → 0%.

    Prefer clear rollback_to_off. Prior gates PGR-01/PGR-02 remain available to
    re-arm independently. Does not touch Shadow. Does not enable PGR-04+.
    """
    os.environ.pop(_ENV_PGR_03, None)
    os.environ[_ENV_PGR_03] = "0"
    os.environ.pop(_ACTIVATION_PCT_ENV, None)
    os.environ[_ACTIVATION_PCT_ENV] = "0"
    _bump("em_pgr03_rollback")
    logger.warning(
        "[AUDIT] EM PGR-03 rollback_to_off pct=0 pgr03=OFF "
        "(PGR-01/PGR-02 still available)"
    )
    return em_pgr_flag_snapshot()


def rollback_em_pgr04_to_off() -> dict[str, Any]:
    """
    Fail-safe rollback for EM PGR-04: clear PGR-04 enable + activation pct → 0%.

    Prefer clear rollback_to_off. Prior gates PGR-01/PGR-02/PGR-03 remain available
    to re-arm independently. Does not touch Shadow. Does not enable PGR-05+.
    """
    os.environ.pop(_ENV_PGR_04, None)
    os.environ[_ENV_PGR_04] = "0"
    os.environ.pop(_ACTIVATION_PCT_ENV, None)
    os.environ[_ACTIVATION_PCT_ENV] = "0"
    _bump("em_pgr04_rollback")
    logger.warning(
        "[AUDIT] EM PGR-04 rollback_to_off pct=0 pgr04=OFF "
        "(PGR-01/PGR-02/PGR-03 still available)"
    )
    return em_pgr_flag_snapshot()


def rollback_em_pgr05_to_off() -> dict[str, Any]:
    """
    Fail-safe rollback for EM PGR-05: clear PGR-05 enable + activation pct → 0%.

    Prefer clear rollback_to_off. Prior gates PGR-01..PGR-04 remain available to
    re-arm independently. Does not touch Shadow. Does not enable PGR-06.
    """
    os.environ.pop(_ENV_PGR_05, None)
    os.environ[_ENV_PGR_05] = "0"
    os.environ.pop(_ACTIVATION_PCT_ENV, None)
    os.environ[_ACTIVATION_PCT_ENV] = "0"
    _bump("em_pgr05_rollback")
    logger.warning(
        "[AUDIT] EM PGR-05 rollback_to_off pct=0 pgr05=OFF "
        "(PGR-01/PGR-02/PGR-03/PGR-04 still available)"
    )
    return em_pgr_flag_snapshot()


def rollback_em_pgr06_to_off() -> dict[str, Any]:
    """
    Fail-safe rollback for EM PGR-06: clear PGR-06 enable + activation pct → 0%.

    Prefer clear rollback_to_off. Prior gates PGR-01..PGR-05 remain available to
    re-arm independently. Does not touch Shadow. Does not start Stabilization.
    """
    os.environ.pop(_ENV_PGR_06, None)
    os.environ[_ENV_PGR_06] = "0"
    os.environ.pop(_ACTIVATION_PCT_ENV, None)
    os.environ[_ACTIVATION_PCT_ENV] = "0"
    _bump("em_pgr06_rollback")
    logger.warning(
        "[AUDIT] EM PGR-06 rollback_to_off pct=0 pgr06=OFF "
        "(PGR-01/PGR-02/PGR-03/PGR-04/PGR-05 still available)"
    )
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
        "# Do NOT set EM_ACTIVATION_PCT>1 without matching PGR armed\n"
        "# PGR-06 is independent — arm separately for 100%\n"
        "# Auto-advance=False; Stabilization not started\n"
        "#\n"
        "# Instant rollback:\n"
        "#   set ENABLE_EM_PGR_01=0\n"
        "#   set EM_ACTIVATION_PCT=0\n"
        "#   OR call rollback_em_pgr01_to_off()\n"
    )


def operator_enable_em_pgr02_instructions() -> str:
    """Operator runbook snippet for EM PGR-02."""
    return (
        "# EM PGR-02 (5% / EM_STAGE2_SOLE_PATH_5PCT) — controlled gated enablement\n"
        "# Repo default remains OFF. Shadow may stay armed independently.\n"
        "# Pipeline flags stay OFF unless intentionally included in canary scope.\n"
        "set ENABLE_EM_PGR_02=1\n"
        "set EM_ACTIVATION_PCT=5\n"
        "set ENABLE_EXECUTION_MANAGER=1\n"
        "set ENABLE_EXECUTION_MANAGER_SHADOW=1\n"
        "# Optional: arm eligible pipelines for canary sole-path (still DEFAULT OFF):\n"
        "# set ENABLE_EM_PIPELINE_ANALYZE=1\n"
        "# set ENABLE_EM_PIPELINE_LIVE=1\n"
        "# set ENABLE_EM_PIPELINE_BANKROLL=1\n"
        "# Do NOT set EM_ACTIVATION_PCT>5 without matching PGR armed\n"
        "# PGR-06 is independent — arm separately for 100%\n"
        "# Auto-advance=False; Stabilization not started\n"
        "#\n"
        "# Instant rollback:\n"
        "#   set ENABLE_EM_PGR_02=0\n"
        "#   set EM_ACTIVATION_PCT=0\n"
        "#   OR call rollback_em_pgr02_to_off()\n"
        "#\n"
        "# Re-arm prior gate only (PGR-01 / 1%):\n"
        "#   set ENABLE_EM_PGR_02=0\n"
        "#   set ENABLE_EM_PGR_01=1\n"
        "#   set EM_ACTIVATION_PCT=1\n"
        "#   set ENABLE_EXECUTION_MANAGER=1\n"
    )


def operator_enable_em_pgr03_instructions() -> str:
    """Operator runbook snippet for EM PGR-03."""
    return (
        "# EM PGR-03 (10% / EM_STAGE3_SOLE_PATH_10PCT) — controlled gated enablement\n"
        "# Repo default remains OFF. Shadow may stay armed independently.\n"
        "# Pipeline flags stay OFF unless intentionally included in canary scope.\n"
        "set ENABLE_EM_PGR_03=1\n"
        "set EM_ACTIVATION_PCT=10\n"
        "set ENABLE_EXECUTION_MANAGER=1\n"
        "set ENABLE_EXECUTION_MANAGER_SHADOW=1\n"
        "# Optional: arm eligible pipelines for canary sole-path (still DEFAULT OFF):\n"
        "# set ENABLE_EM_PIPELINE_ANALYZE=1\n"
        "# set ENABLE_EM_PIPELINE_LIVE=1\n"
        "# set ENABLE_EM_PIPELINE_BANKROLL=1\n"
        "# Do NOT set EM_ACTIVATION_PCT>10 without matching PGR armed\n"
        "# PGR-06 is independent — arm separately for 100%\n"
        "# Auto-advance=False; Stabilization not started\n"
        "#\n"
        "# Instant rollback:\n"
        "#   set ENABLE_EM_PGR_03=0\n"
        "#   set EM_ACTIVATION_PCT=0\n"
        "#   OR call rollback_em_pgr03_to_off()\n"
        "#\n"
        "# Re-arm prior gate only (PGR-02 / 5%):\n"
        "#   set ENABLE_EM_PGR_03=0\n"
        "#   set ENABLE_EM_PGR_02=1\n"
        "#   set EM_ACTIVATION_PCT=5\n"
        "#   set ENABLE_EXECUTION_MANAGER=1\n"
        "#\n"
        "# Re-arm prior gate only (PGR-01 / 1%):\n"
        "#   set ENABLE_EM_PGR_03=0\n"
        "#   set ENABLE_EM_PGR_01=1\n"
        "#   set EM_ACTIVATION_PCT=1\n"
        "#   set ENABLE_EXECUTION_MANAGER=1\n"
    )


def operator_enable_em_pgr04_instructions() -> str:
    """Operator runbook snippet for EM PGR-04."""
    return (
        "# EM PGR-04 (25% / EM_STAGE4_SOLE_PATH_25PCT) — controlled gated enablement\n"
        "# Repo default remains OFF. Shadow may stay armed independently.\n"
        "# Pipeline flags stay OFF unless intentionally included in canary scope.\n"
        "set ENABLE_EM_PGR_04=1\n"
        "set EM_ACTIVATION_PCT=25\n"
        "set ENABLE_EXECUTION_MANAGER=1\n"
        "set ENABLE_EXECUTION_MANAGER_SHADOW=1\n"
        "# Optional: arm eligible pipelines for canary sole-path (still DEFAULT OFF):\n"
        "# set ENABLE_EM_PIPELINE_ANALYZE=1\n"
        "# set ENABLE_EM_PIPELINE_LIVE=1\n"
        "# set ENABLE_EM_PIPELINE_BANKROLL=1\n"
        "# Do NOT set EM_ACTIVATION_PCT>25 without matching PGR armed\n"
        "# PGR-06 is independent — arm separately for 100%\n"
        "# Auto-advance=False; Stabilization not started\n"
        "#\n"
        "# Instant rollback:\n"
        "#   set ENABLE_EM_PGR_04=0\n"
        "#   set EM_ACTIVATION_PCT=0\n"
        "#   OR call rollback_em_pgr04_to_off()\n"
        "#\n"
        "# Re-arm prior gate only (PGR-03 / 10%):\n"
        "#   set ENABLE_EM_PGR_04=0\n"
        "#   set ENABLE_EM_PGR_03=1\n"
        "#   set EM_ACTIVATION_PCT=10\n"
        "#   set ENABLE_EXECUTION_MANAGER=1\n"
        "#\n"
        "# Re-arm prior gate only (PGR-02 / 5%):\n"
        "#   set ENABLE_EM_PGR_04=0\n"
        "#   set ENABLE_EM_PGR_02=1\n"
        "#   set EM_ACTIVATION_PCT=5\n"
        "#   set ENABLE_EXECUTION_MANAGER=1\n"
        "#\n"
        "# Re-arm prior gate only (PGR-01 / 1%):\n"
        "#   set ENABLE_EM_PGR_04=0\n"
        "#   set ENABLE_EM_PGR_01=1\n"
        "#   set EM_ACTIVATION_PCT=1\n"
        "#   set ENABLE_EXECUTION_MANAGER=1\n"
    )


def operator_enable_em_pgr05_instructions() -> str:
    """Operator runbook snippet for EM PGR-05."""
    return (
        "# EM PGR-05 (50% / EM_STAGE5_SOLE_PATH_50PCT) — controlled gated enablement\n"
        "# Repo default remains OFF. Shadow may stay armed independently.\n"
        "# Pipeline flags stay OFF unless intentionally included in canary scope.\n"
        "set ENABLE_EM_PGR_05=1\n"
        "set EM_ACTIVATION_PCT=50\n"
        "set ENABLE_EXECUTION_MANAGER=1\n"
        "set ENABLE_EXECUTION_MANAGER_SHADOW=1\n"
        "# Optional: arm eligible pipelines for canary sole-path (still DEFAULT OFF):\n"
        "# set ENABLE_EM_PIPELINE_ANALYZE=1\n"
        "# set ENABLE_EM_PIPELINE_LIVE=1\n"
        "# set ENABLE_EM_PIPELINE_BANKROLL=1\n"
        "# Do NOT set EM_ACTIVATION_PCT=100 without ENABLE_EM_PGR_06\n"
        "# PGR-06 is independent — arm separately for 100%\n"
        "# Auto-advance=False; Stabilization not started\n"
        "#\n"
        "# Instant rollback:\n"
        "#   set ENABLE_EM_PGR_05=0\n"
        "#   set EM_ACTIVATION_PCT=0\n"
        "#   OR call rollback_em_pgr05_to_off()\n"
        "#\n"
        "# Re-arm prior gate only (PGR-04 / 25%):\n"
        "#   set ENABLE_EM_PGR_05=0\n"
        "#   set ENABLE_EM_PGR_04=1\n"
        "#   set EM_ACTIVATION_PCT=25\n"
        "#   set ENABLE_EXECUTION_MANAGER=1\n"
        "#\n"
        "# Re-arm prior gate only (PGR-03 / 10%):\n"
        "#   set ENABLE_EM_PGR_05=0\n"
        "#   set ENABLE_EM_PGR_03=1\n"
        "#   set EM_ACTIVATION_PCT=10\n"
        "#   set ENABLE_EXECUTION_MANAGER=1\n"
        "#\n"
        "# Re-arm prior gate only (PGR-02 / 5%):\n"
        "#   set ENABLE_EM_PGR_05=0\n"
        "#   set ENABLE_EM_PGR_02=1\n"
        "#   set EM_ACTIVATION_PCT=5\n"
        "#   set ENABLE_EXECUTION_MANAGER=1\n"
        "#\n"
        "# Re-arm prior gate only (PGR-01 / 1%):\n"
        "#   set ENABLE_EM_PGR_05=0\n"
        "#   set ENABLE_EM_PGR_01=1\n"
        "#   set EM_ACTIVATION_PCT=1\n"
        "#   set ENABLE_EXECUTION_MANAGER=1\n"
    )


def operator_enable_em_pgr06_instructions() -> str:
    """Operator runbook snippet for EM PGR-06."""
    return (
        "# EM PGR-06 (100% / EM_STAGE6_SOLE_PATH_100PCT) — controlled gated enablement\n"
        "# Repo default remains OFF even at 100% capability. Shadow may stay armed.\n"
        "# Pipeline flags stay OFF unless intentionally included in canary scope.\n"
        "set ENABLE_EM_PGR_06=1\n"
        "set EM_ACTIVATION_PCT=100\n"
        "set ENABLE_EXECUTION_MANAGER=1\n"
        "set ENABLE_EXECUTION_MANAGER_SHADOW=1\n"
        "# Optional: arm eligible pipelines for sole-path (still DEFAULT OFF):\n"
        "# set ENABLE_EM_PIPELINE_ANALYZE=1\n"
        "# set ENABLE_EM_PIPELINE_LIVE=1\n"
        "# set ENABLE_EM_PIPELINE_BANKROLL=1\n"
        "# Auto-advance=False; Stabilization / Final Acceptance NOT started\n"
        "#\n"
        "# Instant rollback:\n"
        "#   set ENABLE_EM_PGR_06=0\n"
        "#   set EM_ACTIVATION_PCT=0\n"
        "#   OR call rollback_em_pgr06_to_off()\n"
        "#\n"
        "# Re-arm prior gate only (PGR-05 / 50%):\n"
        "#   set ENABLE_EM_PGR_06=0\n"
        "#   set ENABLE_EM_PGR_05=1\n"
        "#   set EM_ACTIVATION_PCT=50\n"
        "#   set ENABLE_EXECUTION_MANAGER=1\n"
        "#\n"
        "# Re-arm prior gate only (PGR-04 / 25%):\n"
        "#   set ENABLE_EM_PGR_06=0\n"
        "#   set ENABLE_EM_PGR_04=1\n"
        "#   set EM_ACTIVATION_PCT=25\n"
        "#   set ENABLE_EXECUTION_MANAGER=1\n"
        "#\n"
        "# Re-arm prior gate only (PGR-03 / 10%):\n"
        "#   set ENABLE_EM_PGR_06=0\n"
        "#   set ENABLE_EM_PGR_03=1\n"
        "#   set EM_ACTIVATION_PCT=10\n"
        "#   set ENABLE_EXECUTION_MANAGER=1\n"
        "#\n"
        "# Re-arm prior gate only (PGR-02 / 5%):\n"
        "#   set ENABLE_EM_PGR_06=0\n"
        "#   set ENABLE_EM_PGR_02=1\n"
        "#   set EM_ACTIVATION_PCT=5\n"
        "#   set ENABLE_EXECUTION_MANAGER=1\n"
        "#\n"
        "# Re-arm prior gate only (PGR-01 / 1%):\n"
        "#   set ENABLE_EM_PGR_06=0\n"
        "#   set ENABLE_EM_PGR_01=1\n"
        "#   set EM_ACTIVATION_PCT=1\n"
        "#   set ENABLE_EXECUTION_MANAGER=1\n"
    )


def _active_em_gate_id() -> str:
    if higher_em_pgr_gate_attempted():
        return "NONE"
    if pgr06_enable_flag():
        return "PGR-06"
    if pgr05_enable_flag():
        return "PGR-05"
    if pgr04_enable_flag():
        return "PGR-04"
    if pgr03_enable_flag():
        return "PGR-03"
    if pgr02_enable_flag():
        return "PGR-02"
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
        "pgr02_enable": pgr02_enable_flag(),
        "pgr02_pct": PGR02_PCT,
        "pgr02_stage": PGR02_STAGE,
        "pgr03_enable": pgr03_enable_flag(),
        "pgr03_pct": PGR03_PCT,
        "pgr03_stage": PGR03_STAGE,
        "pgr04_enable": pgr04_enable_flag(),
        "pgr04_pct": PGR04_PCT,
        "pgr04_stage": PGR04_STAGE,
        "pgr05_enable": pgr05_enable_flag(),
        "pgr05_pct": PGR05_PCT,
        "pgr05_stage": PGR05_STAGE,
        "pgr06_enable": pgr06_enable_flag(),
        "pgr06_pct": PGR06_PCT,
        "pgr06_stage": PGR06_STAGE,
        "configured_pct": get_configured_em_activation_pct(),
        "effective_pct": effective,
        "stage_name": em_activation_stage_name(effective),
        "authorized_highest_gate": AUTHORIZED_HIGHEST_GATE,
        "authorized_operational_max_pct": AUTHORIZED_OPERATIONAL_MAX_PCT,
        "higher_gates_locked": True,
        "higher_gate_attempted": higher_em_pgr_gate_attempted(),
        "auto_advance": False,
        "pgr02_not_started": False,
        "pgr03_not_started": False,
        "pgr04_not_started": False,
        "pgr05_not_started": False,
        "pgr06_not_started": False,
        "phase6_stabilization_not_started": True,
        "gates": gates,
        "metrics": em_pgr_metrics_snapshot(),
        "operator_enable_pgr01_runbook": operator_enable_em_pgr01_instructions(),
        "operator_enable_pgr02_runbook": operator_enable_em_pgr02_instructions(),
        "operator_enable_pgr03_runbook": operator_enable_em_pgr03_instructions(),
        "operator_enable_pgr04_runbook": operator_enable_em_pgr04_instructions(),
        "operator_enable_pgr05_runbook": operator_enable_em_pgr05_instructions(),
        "operator_enable_pgr06_runbook": operator_enable_em_pgr06_instructions(),
        "rollback_possible": True,
        "shadow_independent": True,
    }
