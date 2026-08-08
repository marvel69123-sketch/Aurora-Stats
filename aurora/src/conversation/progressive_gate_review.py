"""
Mission 016 Phase 5 — Progressive Gate Review (REGRA 25) — PGR-01..PGR-06.

Each activation increase is an independent gate. This module operationalizes:

  PGR-01 → STAGE1_BOUNDARY_1PCT (1%)
  PGR-02 → STAGE2_ANALYZE_5PCT (5%)
  PGR-03 → STAGE3_NOTE_10PCT (10%)
  PGR-04 → STAGE4_25PCT (25%)
  PGR-05 → STAGE5_50PCT (50%)
  PGR-06 → STAGE6_100PCT (100%)

PGR-01..PGR-06 are authorized as independent gates (one gate per mission
decision). No auto-advance. Phase 6 Stabilization (Mission 016) is complete
as observability posture only — does NOT enable ENABLE_LANGGRAPH_STATE /
definitive Activation (Mission 017 Acceptance pending).

Repo default: all PGR gates OFF. Operators enable PGR-01..PGR-06 explicitly
via env. Mirror drift remains OPEN — PGR gates are controlled/gated
enablement of authorized stages behind flags (not full-env production
Activation). ENABLE_LANGGRAPH_STATE stays OFF. Legacy writers remain present.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Literal

logger = logging.getLogger(__name__)

PGRId = Literal["PGR-01", "PGR-02", "PGR-03", "PGR-04", "PGR-05", "PGR-06"]

# REGRA 25 ladder — PGR-01..PGR-05 unlockable this mission (one gate per decision).
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
        "authorized_this_mission": True,
    },
    {
        "id": "PGR-03",
        "pct": 10,
        "stage_name": "STAGE3_NOTE_10PCT",
        "env_enable": "AURORA_PGR_03_ENABLE",
        "authorized_this_mission": True,
    },
    {
        "id": "PGR-04",
        "pct": 25,
        "stage_name": "STAGE4_25PCT",
        "env_enable": "AURORA_PGR_04_ENABLE",
        "authorized_this_mission": True,
    },
    {
        "id": "PGR-05",
        "pct": 50,
        "stage_name": "STAGE5_50PCT",
        "env_enable": "AURORA_PGR_05_ENABLE",
        "authorized_this_mission": True,
    },
    {
        "id": "PGR-06",
        "pct": 100,
        "stage_name": "STAGE6_100PCT",
        "env_enable": "AURORA_PGR_06_ENABLE",
        "authorized_this_mission": True,
    },
)

PGR01_ID = "PGR-01"
PGR01_PCT = 1
PGR01_STAGE = "STAGE1_BOUNDARY_1PCT"
_ENV_PGR_01 = "AURORA_PGR_01_ENABLE"

PGR02_ID = "PGR-02"
PGR02_PCT = 5
PGR02_STAGE = "STAGE2_ANALYZE_5PCT"
_ENV_PGR_02 = "AURORA_PGR_02_ENABLE"

PGR03_ID = "PGR-03"
PGR03_PCT = 10
PGR03_STAGE = "STAGE3_NOTE_10PCT"
_ENV_PGR_03 = "AURORA_PGR_03_ENABLE"

PGR04_ID = "PGR-04"
PGR04_PCT = 25
PGR04_STAGE = "STAGE4_25PCT"
_ENV_PGR_04 = "AURORA_PGR_04_ENABLE"

PGR05_ID = "PGR-05"
PGR05_PCT = 50
PGR05_STAGE = "STAGE5_50PCT"
_ENV_PGR_05 = "AURORA_PGR_05_ENABLE"

PGR06_ID = "PGR-06"
PGR06_PCT = 100
PGR06_STAGE = "STAGE6_100PCT"
_ENV_PGR_06 = "AURORA_PGR_06_ENABLE"

# Highest gate authorized without a new PO mission (REGRA 27 — this commit = PGR-06).
AUTHORIZED_HIGHEST_GATE = PGR06_ID
AUTHORIZED_OPERATIONAL_MAX_PCT = PGR06_PCT

_metrics_lock = threading.Lock()
_METRICS: dict[str, int] = {
    "pgr01_armed": 0,
    "pgr01_blocked_missing_flag": 0,
    "pgr01_rollback": 0,
    "pgr02_armed": 0,
    "pgr02_blocked_missing_flag": 0,
    "pgr02_rollback": 0,
    "pgr03_armed": 0,
    "pgr03_blocked_missing_flag": 0,
    "pgr03_rollback": 0,
    "pgr04_armed": 0,
    "pgr04_blocked_missing_flag": 0,
    "pgr04_rollback": 0,
    "pgr05_armed": 0,
    "pgr05_blocked_missing_flag": 0,
    "pgr05_rollback": 0,
    "pgr06_armed": 0,
    "pgr06_blocked_missing_flag": 0,
    "pgr06_rollback": 0,
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


def pgr02_enable_flag() -> bool:
    """True when operator set AURORA_PGR_02_ENABLE (independent REGRA 25 gate)."""
    return _flag_truthy(_ENV_PGR_02)


def pgr03_enable_flag() -> bool:
    """True when operator set AURORA_PGR_03_ENABLE (independent REGRA 25 gate)."""
    return _flag_truthy(_ENV_PGR_03)


def pgr04_enable_flag() -> bool:
    """True when operator set AURORA_PGR_04_ENABLE (independent REGRA 25 gate)."""
    return _flag_truthy(_ENV_PGR_04)


def pgr05_enable_flag() -> bool:
    """True when operator set AURORA_PGR_05_ENABLE (independent REGRA 25 gate)."""
    return _flag_truthy(_ENV_PGR_05)


def pgr06_enable_flag() -> bool:
    """True when operator set AURORA_PGR_06_ENABLE (independent REGRA 25 gate)."""
    return _flag_truthy(_ENV_PGR_06)


def pgr_gate_definition(gate_id: str) -> dict[str, Any] | None:
    for row in PGR_LADDER:
        if row["id"] == gate_id:
            return dict(row)
    return None


def higher_pgr_gate_attempted() -> bool:
    """
    True if any PGR above the authorized highest gate is armed.

    After PGR-06 mission: ladder ends at PGR-06; no higher PGR env exists.
    PGR-06 itself is authorized and does not count as "higher".
    """
    past_authorized = False
    for row in PGR_LADDER:
        if row["id"] == AUTHORIZED_HIGHEST_GATE:
            past_authorized = True
            continue
        if not past_authorized:
            continue
        if _flag_truthy(str(row["env_enable"])):
            return True
    return False


def assert_no_higher_pgr_gates(*, bump: bool = True) -> bool:
    """
    Fail-closed helper: gates above AUTHORIZED_HIGHEST_GATE must not unlock.
    Returns True when safe (no higher-than-PGR-06 gates armed).
    """
    if higher_pgr_gate_attempted():
        if bump:
            _bump("pgr_higher_gate_blocked")
        logger.warning(
            "[AUDIT] PGR higher_gate_blocked — only PGR-01..PGR-06 authorized "
            "(Phase 6 Stabilization not started)"
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


def pgr02_armed() -> bool:
    """
    PGR-02 operator arming flag only (does not alone activate the 5% path).

    Full live activation also requires funnel pct=5 + analyze funnel flag
    (see sole_writer_funnel / require_pgr02_for_stage2).
    """
    if higher_pgr_gate_attempted():
        _bump("pgr_higher_gate_blocked")
        return False
    return pgr02_enable_flag()


def pgr03_armed() -> bool:
    """
    PGR-03 operator arming flag only (does not alone activate the 10% path).

    Full live activation also requires funnel pct=10 + note subject guards
    (see sole_writer_funnel / require_pgr03_for_stage3).
    """
    if higher_pgr_gate_attempted():
        _bump("pgr_higher_gate_blocked")
        return False
    return pgr03_enable_flag()


def pgr04_armed() -> bool:
    """
    PGR-04 operator arming flag only (does not alone activate the 25% path).

    Full live activation also requires funnel pct=25 + note subject guards
    (and prior funnel path flags) — see sole_writer_funnel / require_pgr04_for_stage4.
    """
    if higher_pgr_gate_attempted():
        _bump("pgr_higher_gate_blocked")
        return False
    return pgr04_enable_flag()


def pgr05_armed() -> bool:
    """
    PGR-05 operator arming flag only (does not alone activate the 50% path).

    Full live activation also requires funnel pct=50 + note subject guards
    (and prior funnel path flags) — see sole_writer_funnel / require_pgr05_for_stage5.
    """
    if higher_pgr_gate_attempted():
        _bump("pgr_higher_gate_blocked")
        return False
    return pgr05_enable_flag()


def pgr06_armed() -> bool:
    """
    PGR-06 operator arming flag only (does not alone activate the 100% path).

    Full live activation also requires funnel pct=100 + note subject guards
    (and prior funnel path flags) — see sole_writer_funnel / require_pgr06_for_stage6.
    """
    if higher_pgr_gate_attempted():
        _bump("pgr_higher_gate_blocked")
        return False
    return pgr06_enable_flag()


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


def require_pgr02_for_stage2(*, force: bool = False) -> bool:
    """
    Independent gate check for STAGE2_ANALYZE_5PCT live path.

    force=True: tests may bypass PGR arming (canary/ownership unit tests).
    """
    if force:
        return True
    if not assert_no_higher_pgr_gates():
        return False
    if not pgr02_enable_flag():
        _bump("pgr02_blocked_missing_flag")
        logger.info(
            "[AUDIT] PGR-02 blocked_missing_flag — set %s=1 with PO approval "
            "to arm STAGE2_ANALYZE_5PCT",
            _ENV_PGR_02,
        )
        return False
    _bump("pgr02_armed")
    return True


def require_pgr03_for_stage3(*, force: bool = False) -> bool:
    """
    Independent gate check for STAGE3_NOTE_10PCT live path.

    force=True: tests may bypass PGR arming (canary/ownership unit tests).
    """
    if force:
        return True
    if not assert_no_higher_pgr_gates():
        return False
    if not pgr03_enable_flag():
        _bump("pgr03_blocked_missing_flag")
        logger.info(
            "[AUDIT] PGR-03 blocked_missing_flag — set %s=1 with PO approval "
            "to arm STAGE3_NOTE_10PCT",
            _ENV_PGR_03,
        )
        return False
    _bump("pgr03_armed")
    return True


def require_pgr04_for_stage4(*, force: bool = False) -> bool:
    """
    Independent gate check for STAGE4_25PCT live path.

    force=True: tests may bypass PGR arming (canary/ownership unit tests).
    """
    if force:
        return True
    if not assert_no_higher_pgr_gates():
        return False
    if not pgr04_enable_flag():
        _bump("pgr04_blocked_missing_flag")
        logger.info(
            "[AUDIT] PGR-04 blocked_missing_flag — set %s=1 with PO approval "
            "to arm STAGE4_25PCT",
            _ENV_PGR_04,
        )
        return False
    _bump("pgr04_armed")
    return True


def require_pgr05_for_stage5(*, force: bool = False) -> bool:
    """
    Independent gate check for STAGE5_50PCT live path.

    force=True: tests may bypass PGR arming (canary/ownership unit tests).
    """
    if force:
        return True
    if not assert_no_higher_pgr_gates():
        return False
    if not pgr05_enable_flag():
        _bump("pgr05_blocked_missing_flag")
        logger.info(
            "[AUDIT] PGR-05 blocked_missing_flag — set %s=1 with PO approval "
            "to arm STAGE5_50PCT",
            _ENV_PGR_05,
        )
        return False
    _bump("pgr05_armed")
    return True


def require_pgr06_for_stage6(*, force: bool = False) -> bool:
    """
    Independent gate check for STAGE6_100PCT live path.

    force=True: tests may bypass PGR arming (canary/ownership unit tests).
    """
    if force:
        return True
    if not assert_no_higher_pgr_gates():
        return False
    if not pgr06_enable_flag():
        _bump("pgr06_blocked_missing_flag")
        logger.info(
            "[AUDIT] PGR-06 blocked_missing_flag — set %s=1 with PO approval "
            "to arm STAGE6_100PCT",
            _ENV_PGR_06,
        )
        return False
    _bump("pgr06_armed")
    return True


def rollback_pgr01_to_off() -> dict[str, Any]:
    """
    Fail-safe rollback for PGR-01: clear PGR-01 enable + funnel pct → 0%.

    Does not touch shadow flags. Does not enable higher gates.
    Does not clear PGR-02/PGR-03/PGR-04 enable (caller may use dedicated helpers).
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


def rollback_pgr02_to_off() -> dict[str, Any]:
    """
    Fail-safe rollback for PGR-02: clear PGR-02 enable + funnel pct → 0%.

    Prefer clear rollback_to_off. Prior gate PGR-01 remains available to re-arm
    independently (set AURORA_PGR_01_ENABLE + pct=1 + boundary flag).
    Does not touch shadow flags. Does not enable PGR-05+.
    """
    os.environ.pop(_ENV_PGR_02, None)
    try:
        from src.conversation.sole_writer_funnel import rollback_funnel_to_off

        rollback_funnel_to_off()
    except Exception as exc:
        os.environ.pop("AURORA_SOLE_WRITER_FUNNEL_PCT", None)
        logger.warning("[AUDIT] PGR-02 rollback funnel helper skipped (%s)", exc)
    _bump("pgr02_rollback")
    logger.warning("[AUDIT] PGR-02 rollback_to_off pct=0 pgr02=OFF (PGR-01 still available)")
    return pgr_flag_snapshot()


def rollback_pgr03_to_off() -> dict[str, Any]:
    """
    Fail-safe rollback for PGR-03: clear PGR-03 enable + funnel pct → 0%.

    Prefer clear rollback_to_off. Prior gates PGR-01/PGR-02 remain available to
    re-arm independently. Does not touch shadow flags. Does not enable PGR-05+.
    """
    os.environ.pop(_ENV_PGR_03, None)
    try:
        from src.conversation.sole_writer_funnel import rollback_funnel_to_off

        rollback_funnel_to_off()
    except Exception as exc:
        os.environ.pop("AURORA_SOLE_WRITER_FUNNEL_PCT", None)
        logger.warning("[AUDIT] PGR-03 rollback funnel helper skipped (%s)", exc)
    _bump("pgr03_rollback")
    logger.warning(
        "[AUDIT] PGR-03 rollback_to_off pct=0 pgr03=OFF "
        "(PGR-01/PGR-02 still available)"
    )
    return pgr_flag_snapshot()


def rollback_pgr04_to_off() -> dict[str, Any]:
    """
    Fail-safe rollback for PGR-04: clear PGR-04 enable + funnel pct → 0%.

    Prefer clear rollback_to_off. Prior gates PGR-01/PGR-02/PGR-03 remain
    available to re-arm independently. Does not touch shadow flags. Does not
    enable PGR-06+.
    """
    os.environ.pop(_ENV_PGR_04, None)
    try:
        from src.conversation.sole_writer_funnel import rollback_funnel_to_off

        rollback_funnel_to_off()
    except Exception as exc:
        os.environ.pop("AURORA_SOLE_WRITER_FUNNEL_PCT", None)
        logger.warning("[AUDIT] PGR-04 rollback funnel helper skipped (%s)", exc)
    _bump("pgr04_rollback")
    logger.warning(
        "[AUDIT] PGR-04 rollback_to_off pct=0 pgr04=OFF "
        "(PGR-01/PGR-02/PGR-03 still available)"
    )
    return pgr_flag_snapshot()


def rollback_pgr05_to_off() -> dict[str, Any]:
    """
    Fail-safe rollback for PGR-05: clear PGR-05 enable + funnel pct → 0%.

    Prefer clear rollback_to_off. Prior gates PGR-01/PGR-02/PGR-03/PGR-04 remain
    available to re-arm independently. Does not touch shadow flags. Does not
    enable Phase 6 Stabilization.
    """
    os.environ.pop(_ENV_PGR_05, None)
    try:
        from src.conversation.sole_writer_funnel import rollback_funnel_to_off

        rollback_funnel_to_off()
    except Exception as exc:
        os.environ.pop("AURORA_SOLE_WRITER_FUNNEL_PCT", None)
        logger.warning("[AUDIT] PGR-05 rollback funnel helper skipped (%s)", exc)
    _bump("pgr05_rollback")
    logger.warning(
        "[AUDIT] PGR-05 rollback_to_off pct=0 pgr05=OFF "
        "(PGR-01/PGR-02/PGR-03/PGR-04 still available)"
    )
    return pgr_flag_snapshot()


def rollback_pgr06_to_off() -> dict[str, Any]:
    """
    Fail-safe rollback for PGR-06: clear PGR-06 enable + funnel pct → 0%.

    Prefer clear rollback_to_off. Prior gates PGR-01..PGR-05 remain available to
    re-arm independently. Does not touch shadow flags. Does not start Phase 6.
    """
    os.environ.pop(_ENV_PGR_06, None)
    try:
        from src.conversation.sole_writer_funnel import rollback_funnel_to_off

        rollback_funnel_to_off()
    except Exception as exc:
        os.environ.pop("AURORA_SOLE_WRITER_FUNNEL_PCT", None)
        logger.warning("[AUDIT] PGR-06 rollback funnel helper skipped (%s)", exc)
    _bump("pgr06_rollback")
    logger.warning(
        "[AUDIT] PGR-06 rollback_to_off pct=0 pgr06=OFF "
        "(PGR-01/PGR-02/PGR-03/PGR-04/PGR-05 still available)"
    )
    return pgr_flag_snapshot()


def operator_enable_pgr01_instructions() -> str:
    """Operator runbook snippet for PGR-01 (documentation / snapshot)."""
    return (
        "# PGR-01 (1% / STAGE1_BOUNDARY_1PCT) — controlled gated enablement\n"
        "# Repo default remains OFF. Mirror drift OPEN ⇒ not full-env Activation.\n"
        "set AURORA_PGR_01_ENABLE=1\n"
        "set AURORA_SOLE_WRITER_FUNNEL_PCT=1\n"
        "set ENABLE_STS_WRITE_FUNNEL_BOUNDARY=1\n"
        "set ENABLE_LANGGRAPH_STATE=0\n"
        "# Do NOT set AURORA_SOLE_WRITER_FUNNEL_PCT=100 without AURORA_PGR_06_ENABLE\n"
        "# Do NOT set AURORA_FUNNEL_PO_STAGE_UNLOCK unless PO approved >100%\n"
        "# Phase 6 Stabilization is NOT started by this gate\n"
        "#\n"
        "# Instant rollback:\n"
        "#   unset AURORA_PGR_01_ENABLE\n"
        "#   unset AURORA_SOLE_WRITER_FUNNEL_PCT\n"
        "#   OR call rollback_pgr01_to_off()\n"
    )


def operator_enable_pgr02_instructions() -> str:
    """Operator runbook snippet for PGR-02 (documentation / snapshot)."""
    return (
        "# PGR-02 (5% / STAGE2_ANALYZE_5PCT) — controlled gated enablement\n"
        "# Repo default remains OFF. Mirror drift OPEN ⇒ not full-env Activation.\n"
        "set AURORA_PGR_02_ENABLE=1\n"
        "set AURORA_SOLE_WRITER_FUNNEL_PCT=5\n"
        "set ENABLE_STS_WRITE_FUNNEL_BOUNDARY=1\n"
        "set ENABLE_STS_WRITE_FUNNEL_ANALYZE=1\n"
        "set ENABLE_LANGGRAPH_STATE=0\n"
        "# Optional: keep PGR-01 armed for prior-gate coherence / rollback ladder\n"
        "# set AURORA_PGR_01_ENABLE=1\n"
        "# Do NOT set AURORA_SOLE_WRITER_FUNNEL_PCT=100 without AURORA_PGR_06_ENABLE\n"
        "# Do NOT set AURORA_FUNNEL_PO_STAGE_UNLOCK unless PO approved >100%\n"
        "# Phase 6 Stabilization is NOT started by this gate\n"
        "# Do NOT set pct > 100 without higher PO unlock\n"
        "#\n"
        "# Instant rollback to OFF:\n"
        "#   unset AURORA_PGR_02_ENABLE\n"
        "#   unset AURORA_SOLE_WRITER_FUNNEL_PCT\n"
        "#   OR call rollback_pgr02_to_off()\n"
        "#\n"
        "# Re-arm prior gate only (PGR-01 / 1%):\n"
        "#   unset AURORA_PGR_02_ENABLE\n"
        "#   set AURORA_PGR_01_ENABLE=1\n"
        "#   set AURORA_SOLE_WRITER_FUNNEL_PCT=1\n"
        "#   set ENABLE_STS_WRITE_FUNNEL_BOUNDARY=1\n"
        "#   unset ENABLE_STS_WRITE_FUNNEL_ANALYZE  (optional)\n"
    )


def operator_enable_pgr03_instructions() -> str:
    """Operator runbook snippet for PGR-03 (documentation / snapshot)."""
    return (
        "# PGR-03 (10% / STAGE3_NOTE_10PCT) — controlled gated enablement\n"
        "# Repo default remains OFF. Mirror drift OPEN ⇒ not full-env Activation.\n"
        "set AURORA_PGR_03_ENABLE=1\n"
        "set AURORA_SOLE_WRITER_FUNNEL_PCT=10\n"
        "set ENABLE_STS_WRITE_FUNNEL_BOUNDARY=1\n"
        "set ENABLE_STS_WRITE_FUNNEL_ANALYZE=1\n"
        "set ENABLE_STS_NOTE_SUBJECT_GUARDS=1\n"
        "set ENABLE_LANGGRAPH_STATE=0\n"
        "# Optional: keep prior gates armed for coherence / rollback ladder\n"
        "# set AURORA_PGR_01_ENABLE=1\n"
        "# set AURORA_PGR_02_ENABLE=1\n"
        "# Do NOT set AURORA_SOLE_WRITER_FUNNEL_PCT=100 without AURORA_PGR_06_ENABLE\n"
        "# Do NOT set AURORA_FUNNEL_PO_STAGE_UNLOCK unless PO approved >100%\n"
        "# Phase 6 Stabilization is NOT started by this gate\n"
        "# Do NOT set pct > 100 without higher PO unlock\n"
        "#\n"
        "# Instant rollback to OFF:\n"
        "#   unset AURORA_PGR_03_ENABLE\n"
        "#   unset AURORA_SOLE_WRITER_FUNNEL_PCT\n"
        "#   OR call rollback_pgr03_to_off()\n"
        "#\n"
        "# Re-arm prior gate only (PGR-02 / 5%):\n"
        "#   unset AURORA_PGR_03_ENABLE\n"
        "#   set AURORA_PGR_02_ENABLE=1\n"
        "#   set AURORA_SOLE_WRITER_FUNNEL_PCT=5\n"
        "#   set ENABLE_STS_WRITE_FUNNEL_BOUNDARY=1\n"
        "#   set ENABLE_STS_WRITE_FUNNEL_ANALYZE=1\n"
        "#   unset ENABLE_STS_NOTE_SUBJECT_GUARDS  (optional)\n"
        "#\n"
        "# Re-arm prior gate only (PGR-01 / 1%):\n"
        "#   unset AURORA_PGR_03_ENABLE\n"
        "#   unset AURORA_PGR_02_ENABLE\n"
        "#   set AURORA_PGR_01_ENABLE=1\n"
        "#   set AURORA_SOLE_WRITER_FUNNEL_PCT=1\n"
        "#   set ENABLE_STS_WRITE_FUNNEL_BOUNDARY=1\n"
    )


def operator_enable_pgr04_instructions() -> str:
    """Operator runbook snippet for PGR-04 (documentation / snapshot)."""
    return (
        "# PGR-04 ONLY (25% / STAGE4_25PCT) — controlled gated enablement\n"
        "# Repo default remains OFF. Mirror drift OPEN ⇒ not full-env Activation.\n"
        "# STAGE4 raises canary %; same funnel paths as STAGE3 (boundary+analyze+note).\n"
        "set AURORA_PGR_04_ENABLE=1\n"
        "set AURORA_SOLE_WRITER_FUNNEL_PCT=25\n"
        "set ENABLE_STS_WRITE_FUNNEL_BOUNDARY=1\n"
        "set ENABLE_STS_WRITE_FUNNEL_ANALYZE=1\n"
        "set ENABLE_STS_NOTE_SUBJECT_GUARDS=1\n"
        "set ENABLE_LANGGRAPH_STATE=0\n"
        "# Optional: keep prior gates armed for coherence / rollback ladder\n"
        "# set AURORA_PGR_01_ENABLE=1\n"
        "# set AURORA_PGR_02_ENABLE=1\n"
        "# set AURORA_PGR_03_ENABLE=1\n"
        "# Do NOT set AURORA_SOLE_WRITER_FUNNEL_PCT=100 without AURORA_PGR_06_ENABLE\n"
        "# Do NOT set AURORA_FUNNEL_PO_STAGE_UNLOCK unless PO approved >100%\n"
        "# Phase 6 Stabilization is NOT started by this gate\n"
        "# Do NOT set pct > 100 without higher PO unlock\n"
        "#\n"
        "# Instant rollback to OFF:\n"
        "#   unset AURORA_PGR_04_ENABLE\n"
        "#   unset AURORA_SOLE_WRITER_FUNNEL_PCT\n"
        "#   OR call rollback_pgr04_to_off()\n"
        "#\n"
        "# Re-arm prior gate only (PGR-03 / 10%):\n"
        "#   unset AURORA_PGR_04_ENABLE\n"
        "#   set AURORA_PGR_03_ENABLE=1\n"
        "#   set AURORA_SOLE_WRITER_FUNNEL_PCT=10\n"
        "#   set ENABLE_STS_WRITE_FUNNEL_BOUNDARY=1\n"
        "#   set ENABLE_STS_WRITE_FUNNEL_ANALYZE=1\n"
        "#   set ENABLE_STS_NOTE_SUBJECT_GUARDS=1\n"
        "#\n"
        "# Re-arm prior gate only (PGR-02 / 5%):\n"
        "#   unset AURORA_PGR_04_ENABLE\n"
        "#   unset AURORA_PGR_03_ENABLE\n"
        "#   set AURORA_PGR_02_ENABLE=1\n"
        "#   set AURORA_SOLE_WRITER_FUNNEL_PCT=5\n"
        "#   set ENABLE_STS_WRITE_FUNNEL_BOUNDARY=1\n"
        "#   set ENABLE_STS_WRITE_FUNNEL_ANALYZE=1\n"
    )


def operator_enable_pgr05_instructions() -> str:
    """Operator runbook snippet for PGR-05 (documentation / snapshot)."""
    return (
        "# PGR-05 ONLY (50% / STAGE5_50PCT) — controlled gated enablement\n"
        "# Repo default remains OFF. Mirror drift OPEN ⇒ not full-env Activation.\n"
        "# STAGE5 raises canary %; same funnel paths as STAGE4 (boundary+analyze+note).\n"
        "set AURORA_PGR_05_ENABLE=1\n"
        "set AURORA_SOLE_WRITER_FUNNEL_PCT=50\n"
        "set ENABLE_STS_WRITE_FUNNEL_BOUNDARY=1\n"
        "set ENABLE_STS_WRITE_FUNNEL_ANALYZE=1\n"
        "set ENABLE_STS_NOTE_SUBJECT_GUARDS=1\n"
        "set ENABLE_LANGGRAPH_STATE=0\n"
        "# Optional: keep prior gates armed for coherence / rollback ladder\n"
        "# set AURORA_PGR_01_ENABLE=1\n"
        "# set AURORA_PGR_02_ENABLE=1\n"
        "# set AURORA_PGR_03_ENABLE=1\n"
        "# set AURORA_PGR_04_ENABLE=1\n"
        "# Do NOT set AURORA_SOLE_WRITER_FUNNEL_PCT=100 without AURORA_PGR_06_ENABLE\n"
        "# Do NOT set AURORA_FUNNEL_PO_STAGE_UNLOCK unless PO approved >100%\n"
        "# Phase 6 Stabilization is NOT started by this gate\n"
        "# Do NOT set pct > 100 without higher PO unlock\n"
        "#\n"
        "# Instant rollback to OFF:\n"
        "#   unset AURORA_PGR_05_ENABLE\n"
        "#   unset AURORA_SOLE_WRITER_FUNNEL_PCT\n"
        "#   OR call rollback_pgr05_to_off()\n"
        "#\n"
        "# Re-arm prior gate only (PGR-04 / 25%):\n"
        "#   unset AURORA_PGR_05_ENABLE\n"
        "#   set AURORA_PGR_04_ENABLE=1\n"
        "#   set AURORA_SOLE_WRITER_FUNNEL_PCT=25\n"
        "#   set ENABLE_STS_WRITE_FUNNEL_BOUNDARY=1\n"
        "#   set ENABLE_STS_WRITE_FUNNEL_ANALYZE=1\n"
        "#   set ENABLE_STS_NOTE_SUBJECT_GUARDS=1\n"
        "#\n"
        "# Re-arm prior gate only (PGR-03 / 10%):\n"
        "#   unset AURORA_PGR_05_ENABLE\n"
        "#   unset AURORA_PGR_04_ENABLE\n"
        "#   set AURORA_PGR_03_ENABLE=1\n"
        "#   set AURORA_SOLE_WRITER_FUNNEL_PCT=10\n"
        "#   set ENABLE_STS_WRITE_FUNNEL_BOUNDARY=1\n"
        "#   set ENABLE_STS_WRITE_FUNNEL_ANALYZE=1\n"
        "#   set ENABLE_STS_NOTE_SUBJECT_GUARDS=1\n"
    )


def operator_enable_pgr06_instructions() -> str:
    """Operator runbook snippet for PGR-06 (documentation / snapshot)."""
    return (
        "# PGR-06 ONLY (100% / STAGE6_100PCT) — controlled gated enablement\n"
        "# Repo default remains OFF. Mirror drift OPEN ⇒ not full-env Activation.\n"
        "# STAGE6 raises canary % to 100%; same funnel paths as STAGE5 "
        "(boundary+analyze+note).\n"
        "# Legacy writers remain present when OFF / not selected.\n"
        "# Phase 6 Stabilization COMPLETE (Mission 016) — validation only.\n"
        "# Definitive Activation / ENABLE_LANGGRAPH_STATE=ON blocked until\n"
        "# Mission 017 Final Acceptance + mirror drift closure (FINDING-024).\n"
        "set AURORA_PGR_06_ENABLE=1\n"
        "set AURORA_SOLE_WRITER_FUNNEL_PCT=100\n"
        "set ENABLE_STS_WRITE_FUNNEL_BOUNDARY=1\n"
        "set ENABLE_STS_WRITE_FUNNEL_ANALYZE=1\n"
        "set ENABLE_STS_NOTE_SUBJECT_GUARDS=1\n"
        "set ENABLE_LANGGRAPH_STATE=0\n"
        "# Optional: keep prior gates armed for coherence / rollback ladder\n"
        "# set AURORA_PGR_01_ENABLE=1\n"
        "# set AURORA_PGR_02_ENABLE=1\n"
        "# set AURORA_PGR_03_ENABLE=1\n"
        "# set AURORA_PGR_04_ENABLE=1\n"
        "# set AURORA_PGR_05_ENABLE=1\n"
        "# Do NOT set ENABLE_LANGGRAPH_STATE=1 (definitive Activation)\n"
        "# Do NOT set AURORA_FUNNEL_PO_STAGE_UNLOCK unless PO approved >100%\n"
        "#\n"
        "# Instant rollback to OFF:\n"
        "#   unset AURORA_PGR_06_ENABLE\n"
        "#   unset AURORA_SOLE_WRITER_FUNNEL_PCT\n"
        "#   OR call rollback_pgr06_to_off()\n"
        "#\n"
        "# Re-arm prior gate only (PGR-05 / 50%):\n"
        "#   unset AURORA_PGR_06_ENABLE\n"
        "#   set AURORA_PGR_05_ENABLE=1\n"
        "#   set AURORA_SOLE_WRITER_FUNNEL_PCT=50\n"
        "#   set ENABLE_STS_WRITE_FUNNEL_BOUNDARY=1\n"
        "#   set ENABLE_STS_WRITE_FUNNEL_ANALYZE=1\n"
        "#   set ENABLE_STS_NOTE_SUBJECT_GUARDS=1\n"
        "#\n"
        "# Re-arm prior gate only (PGR-04 / 25%):\n"
        "#   unset AURORA_PGR_06_ENABLE\n"
        "#   unset AURORA_PGR_05_ENABLE\n"
        "#   set AURORA_PGR_04_ENABLE=1\n"
        "#   set AURORA_SOLE_WRITER_FUNNEL_PCT=25\n"
        "#   set ENABLE_STS_WRITE_FUNNEL_BOUNDARY=1\n"
        "#   set ENABLE_STS_WRITE_FUNNEL_ANALYZE=1\n"
        "#   set ENABLE_STS_NOTE_SUBJECT_GUARDS=1\n"
    )


def _active_gate_id() -> str:
    if higher_pgr_gate_attempted():
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
    if pgr01_enable_flag():
        return "PGR-01"
    return "NONE"


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
    # Lazy import avoids migration_flag_controller ↔ progressive_gate_review cycle.
    from src.conversation.migration_flag_controller import assess_cm_mirror_drift

    return {
        "active_gate": _active_gate_id(),
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
        "authorized_highest_gate": AUTHORIZED_HIGHEST_GATE,
        "authorized_operational_max_pct": AUTHORIZED_OPERATIONAL_MAX_PCT,
        # No auto-advance beyond PGR ladder into definitive Activation.
        "higher_gates_locked": True,
        "higher_gate_attempted": higher_pgr_gate_attempted(),
        "auto_advance": False,
        # Mission 016 Phase 6 Stabilization complete (observability); write still OFF.
        "phase6_not_started": False,
        "phase6_stabilization_complete": True,
        "definitive_activation_not_started": True,
        "pgr02_not_started": False,
        "pgr03_not_started": False,
        "pgr04_not_started": False,
        "pgr05_not_started": False,
        "pgr06_not_started": False,
        "gates": gates,
        "metrics": pgr_metrics_snapshot(),
        "operator_enable_runbook": operator_enable_pgr06_instructions(),
        "operator_enable_pgr01_runbook": operator_enable_pgr01_instructions(),
        "operator_enable_pgr02_runbook": operator_enable_pgr02_instructions(),
        "operator_enable_pgr03_runbook": operator_enable_pgr03_instructions(),
        "operator_enable_pgr04_runbook": operator_enable_pgr04_instructions(),
        "operator_enable_pgr05_runbook": operator_enable_pgr05_instructions(),
        "operator_enable_pgr06_runbook": operator_enable_pgr06_instructions(),
        # Live probe (Mission 047 / FINDING-024) — not hardcoded.
        "mirror_drift_open": assess_cm_mirror_drift()["mirror_drift_open"],
        "production_langgraph_write_required": False,
        "legacy_writers_present": True,
    }
