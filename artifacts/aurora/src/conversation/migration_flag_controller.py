"""
Mission 016 Phase 2 — Migration stage / feature-flag controller (C12).

Phase 4 extends observability for Sole-Writer Funnel progressive % (REGRA 24)
without enabling production write. Defaults remain OFF / S0_OFF.

MIGRATION_STAGE enum S0…S4_RETIRE + illegal matrix I1–I7 fail-closed asserts.
"""

from __future__ import annotations

import os
from enum import Enum
from typing import Any

from src.conversation.sport_topic_state import (
    langgraph_state_enabled,
    langgraph_state_shadow_enabled,
)

_STAGE_ENV = "AURORA_MIGRATION_STAGE"

# Conceptual funnel / sole-writer flags (Spec §8.8) — default OFF.
_FUNNEL_FLAGS = (
    "ENABLE_STS_READ_ADAPTERS",
    "ENABLE_STS_WRITE_FUNNEL_BOUNDARY",
    "ENABLE_STS_WRITE_FUNNEL_ANALYZE",
    "ENABLE_STS_PROJECTIONS_RO",
    "ENABLE_STS_SOLE_WRITER",
)

# Progressive funnel pct (REGRA 24) — default 0; PGR-04 operational max = 25.
_FUNNEL_PCT_ENV = "AURORA_SOLE_WRITER_FUNNEL_PCT"
_FUNNEL_PO_UNLOCK_ENV = "AURORA_FUNNEL_PO_STAGE_UNLOCK"  # required for pct > 25


class MigrationStage(str, Enum):
    S0_OFF = "S0_OFF"
    S1_SHADOW = "S1_SHADOW"
    S2_FUNNEL = "S2_FUNNEL"
    S3_PROD_WRITE = "S3_PROD_WRITE"
    S4_RETIRE = "S4_RETIRE"


def _flag_truthy(env_name: str) -> bool:
    raw = (os.environ.get(env_name) or "0").strip().lower()
    return raw in {"1", "true", "on", "yes"}


def sts_sole_writer_enabled() -> bool:
    return _flag_truthy("ENABLE_STS_SOLE_WRITER")


def sts_funnel_boundary_enabled() -> bool:
    return _flag_truthy("ENABLE_STS_WRITE_FUNNEL_BOUNDARY")


def sts_funnel_analyze_enabled() -> bool:
    return _flag_truthy("ENABLE_STS_WRITE_FUNNEL_ANALYZE")


def funnel_complete() -> bool:
    """P3 single-path proof gate — both boundary + analyze funnel flags."""
    return sts_funnel_boundary_enabled() and sts_funnel_analyze_enabled()


def note_subject_writers_unguarded() -> bool:
    """
    FINDING-026 residual: until Migration wires note_* guards, treat as
    unguarded when production write is requested. Infra default = True
    (unguarded) so I3 stays fail-closed if write attempted early.
    """
    # Explicit opt-in when Phase 3+ proves guards:
    if _flag_truthy("ENABLE_STS_NOTE_SUBJECT_GUARDS"):
        return False
    return True


def dual_materializers_active() -> bool:
    """
    I5: TB-V2 apply ON ∧ orchestrator/graph apply ON after cutover.
    Infra scaffolding: true only when both apply paths explicitly enabled.
    """
    tb_apply = _flag_truthy("ENABLE_TOPIC_BOUNDARY_V2") and _flag_truthy(
        "ENABLE_TB_V2_APPLY_MATERIALIZER"
    )
    host_apply = langgraph_state_enabled() or (
        get_migration_stage() in {MigrationStage.S2_FUNNEL, MigrationStage.S3_PROD_WRITE}
        and _flag_truthy("ENABLE_STS_HOST_APPLY_MATERIALIZER")
    )
    return bool(tb_apply and host_apply)


def deploy_sts_modules_present() -> bool:
    """I6 — required STS/LangGraph modules under artifacts deploy tree."""
    try:
        import src.conversation.sport_topic_state  # noqa: F401
        import src.conversation.langgraph_state_graph  # noqa: F401
        import src.conversation.minimal_commit_orchestrator  # noqa: F401

        return True
    except Exception:
        return False


def get_migration_stage() -> MigrationStage:
    """
    Resolve MIGRATION_STAGE from env, or infer from legacy flags.

    Default: S0_OFF. Never auto-promotes to S3_PROD_WRITE from env alone
    without explicit stage string (illegal matrix still asserts).
    """
    raw = (os.environ.get(_STAGE_ENV) or "").strip().upper()
    if raw:
        # Accept S0_OFF / S0 / OFF forms
        aliases = {
            "S0": MigrationStage.S0_OFF,
            "S0_OFF": MigrationStage.S0_OFF,
            "OFF": MigrationStage.S0_OFF,
            "S1": MigrationStage.S1_SHADOW,
            "S1_SHADOW": MigrationStage.S1_SHADOW,
            "SHADOW": MigrationStage.S1_SHADOW,
            "S2": MigrationStage.S2_FUNNEL,
            "S2_FUNNEL": MigrationStage.S2_FUNNEL,
            "FUNNEL": MigrationStage.S2_FUNNEL,
            "S3": MigrationStage.S3_PROD_WRITE,
            "S3_PROD_WRITE": MigrationStage.S3_PROD_WRITE,
            "PROD_WRITE": MigrationStage.S3_PROD_WRITE,
            "S4": MigrationStage.S4_RETIRE,
            "S4_RETIRE": MigrationStage.S4_RETIRE,
            "RETIRE": MigrationStage.S4_RETIRE,
        }
        if raw in aliases:
            return aliases[raw]
        try:
            return MigrationStage(raw)
        except ValueError:
            return MigrationStage.S0_OFF

    # Infer from legacy flags without enabling write.
    if langgraph_state_enabled():
        return MigrationStage.S3_PROD_WRITE
    if funnel_complete() or _flag_truthy("ENABLE_STS_WRITE_FUNNEL_BOUNDARY"):
        return MigrationStage.S2_FUNNEL
    if langgraph_state_shadow_enabled():
        return MigrationStage.S1_SHADOW
    return MigrationStage.S0_OFF


def production_write_active() -> bool:
    """True only when LangGraph production write flag is ON (must stay OFF in Phase 2)."""
    return langgraph_state_enabled()


def collect_illegal_combinations(
    *,
    langgraph_importable: bool | None = None,
) -> list[dict[str, str]]:
    """
    Evaluate illegal matrix I1–I7. Returns list of {id, detail} for violations.
    Empty list = green (fail-closed assert passes).
    """
    violations: list[dict[str, str]] = []
    write_on = langgraph_state_enabled()
    shadow_on = langgraph_state_shadow_enabled()
    sole = sts_sole_writer_enabled()

    if write_on and not sole:
        violations.append(
            {
                "id": "I1",
                "detail": "ENABLE_LANGGRAPH_STATE=ON without ENABLE_STS_SOLE_WRITER",
            }
        )
    if write_on and not funnel_complete():
        violations.append(
            {
                "id": "I2",
                "detail": "ENABLE_LANGGRAPH_STATE=ON with incomplete funnel flags",
            }
        )
    if write_on and note_subject_writers_unguarded():
        violations.append(
            {
                "id": "I3",
                "detail": "ENABLE_LANGGRAPH_STATE=ON with note_* subject writers unguarded",
            }
        )
    if write_on:
        lg_ok = langgraph_importable
        if lg_ok is None:
            try:
                from src.conversation.langgraph_state_graph import (
                    langgraph_package_available,
                )

                lg_ok = langgraph_package_available()
            except Exception:
                lg_ok = False
        # ADR-001 flip contingency not recorded in Phase 2 → missing package = I4
        if not lg_ok and not _flag_truthy("AURORA_ADR001_FLIP_CONTINGENCY_HOST"):
            violations.append(
                {
                    "id": "I4",
                    "detail": "production write ON but langgraph missing and no ADR-001 flip",
                }
            )
    if dual_materializers_active():
        violations.append(
            {
                "id": "I5",
                "detail": "dual TB-V2 apply + host apply materializers active",
            }
        )
    if write_on and not deploy_sts_modules_present():
        violations.append(
            {
                "id": "I6",
                "detail": "ENABLE_LANGGRAPH_STATE=ON but STS/LangGraph modules missing",
            }
        )
    # I7: shadow claimed as sole-writer / production write
    if shadow_on and write_on and not sole:
        violations.append(
            {
                "id": "I7",
                "detail": "shadow path co-enabled with write without sole-writer (shadow≠activation)",
            }
        )
    if shadow_on and _flag_truthy("CLAIM_SHADOW_AS_SOLE_WRITER"):
        violations.append(
            {
                "id": "I7",
                "detail": "CLAIM_SHADOW_AS_SOLE_WRITER set — shadow ≠ production write",
            }
        )
    return violations


class IllegalFlagMatrixError(RuntimeError):
    """Fail-closed boot assert for Spec §8.8 illegal combinations."""

    def __init__(self, violations: list[dict[str, str]]):
        self.violations = violations
        ids = ", ".join(v["id"] for v in violations)
        super().__init__(f"Illegal migration flag matrix: {ids}")


def assert_legal_flag_matrix(*, raise_on_illegal: bool = True) -> list[dict[str, str]]:
    """
    Boot/assert entrypoint (C12). With defaults OFF, returns [].

    Phase 2: call from tests; production boot wiring deferred to Integration.
    """
    violations = collect_illegal_combinations()
    if violations and raise_on_illegal:
        raise IllegalFlagMatrixError(violations)
    return violations


def flag_snapshot() -> dict[str, Any]:
    """Read-only observability of current flag / stage posture."""
    funnel_pct_snap: dict[str, Any] = {}
    try:
        from src.conversation.sole_writer_funnel import funnel_flag_snapshot

        funnel_pct_snap = funnel_flag_snapshot()
    except Exception:
        funnel_pct_snap = {
            "effective_pct": 0,
            "stage_name": "OFF_0",
            "phase5_not_started": True,
            "phase6_not_started": True,
            "pgr02_not_started": False,
            "pgr03_not_started": False,
            "pgr04_not_started": False,
            "pgr05_not_started": True,
        }
    pgr_snap: dict[str, Any] = {}
    try:
        from src.conversation.progressive_gate_review import pgr_flag_snapshot

        pgr_snap = pgr_flag_snapshot()
    except Exception:
        pgr_snap = {
            "active_gate": "NONE",
            "pgr01_enable": False,
            "pgr02_enable": False,
            "pgr03_enable": False,
            "pgr04_enable": False,
            "higher_gates_locked": True,
            "phase6_not_started": True,
            "pgr02_not_started": False,
            "pgr03_not_started": False,
            "pgr04_not_started": False,
            "pgr05_not_started": True,
            "mirror_drift_open": True,
        }
    return {
        "migration_stage": get_migration_stage().value,
        "ENABLE_LANGGRAPH_STATE": langgraph_state_enabled(),
        "ENABLE_LANGGRAPH_STATE_SHADOW": langgraph_state_shadow_enabled(),
        "ENABLE_STS_SOLE_WRITER": sts_sole_writer_enabled(),
        "ENABLE_STS_WRITE_FUNNEL_BOUNDARY": sts_funnel_boundary_enabled(),
        "ENABLE_STS_WRITE_FUNNEL_ANALYZE": sts_funnel_analyze_enabled(),
        "funnel_complete": funnel_complete(),
        "production_write_active": production_write_active(),
        "illegal_violations": collect_illegal_combinations(),
        "funnel_flags_default_off": {
            name: _flag_truthy(name) for name in _FUNNEL_FLAGS
        },
        "AURORA_SOLE_WRITER_FUNNEL_PCT": (os.environ.get(_FUNNEL_PCT_ENV) or "0"),
        "AURORA_FUNNEL_PO_STAGE_UNLOCK": _flag_truthy(_FUNNEL_PO_UNLOCK_ENV),
        "AURORA_PGR_01_ENABLE": _flag_truthy("AURORA_PGR_01_ENABLE"),
        "AURORA_PGR_02_ENABLE": _flag_truthy("AURORA_PGR_02_ENABLE"),
        "AURORA_PGR_03_ENABLE": _flag_truthy("AURORA_PGR_03_ENABLE"),
        "AURORA_PGR_04_ENABLE": _flag_truthy("AURORA_PGR_04_ENABLE"),
        "sole_writer_funnel": funnel_pct_snap,
        "progressive_gate_review": pgr_snap,
    }
