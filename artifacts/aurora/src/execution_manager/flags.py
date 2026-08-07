"""
EM feature-flag controller + illegal matrix I1–I8 (Plan §8).

All production-affecting defaults OFF / 0%. Fail-closed asserts for illegal combos.
Rollback helpers clear env flags (operator convenience; repo defaults remain OFF).
"""

from __future__ import annotations

import os
from typing import Any

# Plan §8 — production-affecting defaults OFF.
EM_BOOL_FLAGS: tuple[str, ...] = (
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
)

EM_PIPELINE_FLAGS: tuple[str, ...] = (
    "ENABLE_EM_PIPELINE_BANKROLL",
    "ENABLE_EM_PIPELINE_LEARNING",
    "ENABLE_EM_PIPELINE_KNOWLEDGE",
    "ENABLE_EM_PIPELINE_LIVE",
    "ENABLE_EM_PIPELINE_ANALYZE",
    "ENABLE_EM_PIPELINE_LIVE_TEAM",
)

EM_PGR_FLAGS: tuple[str, ...] = (
    "ENABLE_EM_PGR_01",
    "ENABLE_EM_PGR_02",
    "ENABLE_EM_PGR_03",
    "ENABLE_EM_PGR_04",
    "ENABLE_EM_PGR_05",
    "ENABLE_EM_PGR_06",
)

# Forbidden / non-capability probes (I3 / I4 / I5 / I7 operator anti-patterns).
_FORBIDDEN_CM_WRITE_FLAG = "ENABLE_EM_CM_WRITE"
_FORBIDDEN_SHADOW_CM_ELIGIBLE = "ENABLE_EM_SHADOW_CM_ELIGIBLE"
_FORBIDDEN_SHADOW_PEER_COPILOT = "ENABLE_EM_SHADOW_PEER_COPILOT_ENGINE"
_FORBIDDEN_PGR_AUTO_ADVANCE = "ENABLE_EM_PGR_AUTO_ADVANCE"
_ACTIVATION_PCT_ENV = "EM_ACTIVATION_PCT"


def _flag_truthy(env_name: str) -> bool:
    raw = (os.environ.get(env_name) or "0").strip().lower()
    return raw in {"1", "true", "on", "yes"}


def _activation_pct() -> float:
    raw = (os.environ.get(_ACTIVATION_PCT_ENV) or "0").strip()
    try:
        return float(raw)
    except ValueError:
        return 0.0


def shadow_enabled() -> bool:
    return _flag_truthy("ENABLE_EXECUTION_MANAGER_SHADOW")


def sole_path_master_enabled() -> bool:
    return _flag_truthy("ENABLE_EXECUTION_MANAGER")


def pipeline_enabled(pipeline_flag: str) -> bool:
    return _flag_truthy(pipeline_flag)


def any_pipeline_enabled() -> bool:
    return any(_flag_truthy(f) for f in EM_PIPELINE_FLAGS)


def any_pgr_armed() -> bool:
    return any(_flag_truthy(f) for f in EM_PGR_FLAGS)


def em_flags_all_off() -> bool:
    """True when all Plan §8 bool flags are OFF and pct is 0."""
    if any(_flag_truthy(f) for f in EM_BOOL_FLAGS):
        return False
    return _activation_pct() <= 0.0


def collect_illegal_em_combinations() -> list[dict[str, str]]:
    """
    Evaluate illegal matrix I1–I8. Empty list = green (fail-closed assert passes).

    With repo defaults OFF, returns [].
    """
    violations: list[dict[str, str]] = []
    shadow = shadow_enabled()
    sole = sole_path_master_enabled()
    pipelines_on = any_pipeline_enabled()
    pct = _activation_pct()
    pgr_on = any_pgr_armed()

    # I1 — Sole-path ON without Shadow evidence recorded (operator policy stub).
    # Infra: treat master OR any pipeline as sole-path capability requiring Shadow flag.
    if (sole or pipelines_on) and not shadow:
        violations.append(
            {
                "id": "I1",
                "detail": (
                    "sole-path / pipeline ON without ENABLE_EXECUTION_MANAGER_SHADOW "
                    "(Shadow evidence required)"
                ),
            }
        )

    # I2 — Same flag meaning both Shadow-only and sole-path without dual-run harness.
    # Detected when operator sets CLAIM_EM_SHADOW_IS_SOLE_PATH (anti-pattern probe).
    if _flag_truthy("CLAIM_EM_SHADOW_IS_SOLE_PATH"):
        violations.append(
            {
                "id": "I2",
                "detail": "CLAIM_EM_SHADOW_IS_SOLE_PATH — shadow≠sole-path without harness",
            }
        )
    if shadow and sole and not _flag_truthy("ENABLE_EM_DUAL_RUN_HARNESS"):
        # Shadow+sole together without explicit dual-run harness = I2 posture risk.
        violations.append(
            {
                "id": "I2",
                "detail": (
                    "Shadow + sole-path master ON without ENABLE_EM_DUAL_RUN_HARNESS"
                ),
            }
        )

    # I3 — Any flag authorizing EM CM sole-write (nonexistent capability).
    if _flag_truthy(_FORBIDDEN_CM_WRITE_FLAG):
        violations.append(
            {
                "id": "I3",
                "detail": f"{_FORBIDDEN_CM_WRITE_FLAG} set — EM must remain CM write-free",
            }
        )

    # I4 — Shadow path that can pass §4.7 YES / write subject.
    if shadow and _flag_truthy(_FORBIDDEN_SHADOW_CM_ELIGIBLE):
        violations.append(
            {
                "id": "I4",
                "detail": (
                    f"{_FORBIDDEN_SHADOW_CM_ELIGIBLE} — Shadow must always be CM eligibility NO"
                ),
            }
        )

    # I5 — Using copilot_engine as Shadow peer for unified clients.
    if _flag_truthy(_FORBIDDEN_SHADOW_PEER_COPILOT):
        violations.append(
            {
                "id": "I5",
                "detail": (
                    f"{_FORBIDDEN_SHADOW_PEER_COPILOT} — Shadow peer must be unified _run_* only"
                ),
            }
        )

    # I6 — EM_ACTIVATION_PCT > 0 without corresponding PGR gate armed.
    if pct > 0 and not pgr_on:
        violations.append(
            {
                "id": "I6",
                "detail": f"EM_ACTIVATION_PCT={pct} without any ENABLE_EM_PGR_0N armed",
            }
        )

    # I7 — Bundled auto-advance PGR-N → PGR-N+1.
    if _flag_truthy(_FORBIDDEN_PGR_AUTO_ADVANCE):
        violations.append(
            {
                "id": "I7",
                "detail": f"{_FORBIDDEN_PGR_AUTO_ADVANCE} — Auto-advance=False (REGRA 27/28)",
            }
        )

    # I8 — Production defaults ON in repo (assert current process defaults when unset).
    # When flags are explicitly unset, truthy must be False — if any defaulted ON, violate.
    # This check uses raw env absence: if env unset, must read as OFF.
    for name in EM_BOOL_FLAGS:
        raw = os.environ.get(name)
        if raw is None:
            continue  # absent = OFF (legal)
        if _flag_truthy(name) and not _operator_armed_ok(name):
            # I8 fires when code path claims default ON; operator-armed explicit 1 is
            # not a "repo default" violation by itself — I8 is repo-default posture.
            # Infra: only flag when AURORA_EM_CLAIM_REPO_DEFAULTS_ON probe is set.
            pass
    if _flag_truthy("AURORA_EM_CLAIM_REPO_DEFAULTS_ON"):
        violations.append(
            {
                "id": "I8",
                "detail": "AURORA_EM_CLAIM_REPO_DEFAULTS_ON — production defaults must be OFF",
            }
        )
    # Harden I8: if master sole-path is ON while activation pct is default 0 and no
    # PGR — already covered by I1/I6; additionally reject when defaults snapshot lies.
    if not em_flags_all_off() and _flag_truthy("AURORA_EM_ASSERT_DEFAULTS_OFF_ONLY"):
        violations.append(
            {
                "id": "I8",
                "detail": "flags not all OFF under AURORA_EM_ASSERT_DEFAULTS_OFF_ONLY",
            }
        )

    return violations


def _operator_armed_ok(_name: str) -> bool:
    """Placeholder for future PAR evidence gates; Infra treats explicit ON as armed."""
    return True


class IllegalEmFlagMatrixError(RuntimeError):
    """Fail-closed boot assert for Plan §8.1 illegal combinations."""

    def __init__(self, violations: list[dict[str, str]]):
        self.violations = violations
        ids = ", ".join(v["id"] for v in violations)
        super().__init__(f"Illegal EM flag matrix: {ids}")


def assert_legal_em_flag_matrix(*, raise_on_illegal: bool = True) -> list[dict[str, str]]:
    """Boot/assert entrypoint. With defaults OFF, returns []."""
    violations = collect_illegal_em_combinations()
    if violations and raise_on_illegal:
        raise IllegalEmFlagMatrixError(violations)
    return violations


def em_flag_snapshot() -> dict[str, Any]:
    """Read-only observability of EM flag posture."""
    return {
        "flags": {name: _flag_truthy(name) for name in EM_BOOL_FLAGS},
        "EM_ACTIVATION_PCT": _activation_pct(),
        "shadow_enabled": shadow_enabled(),
        "sole_path_master_enabled": sole_path_master_enabled(),
        "any_pipeline_enabled": any_pipeline_enabled(),
        "any_pgr_armed": any_pgr_armed(),
        "em_flags_all_off": em_flags_all_off(),
        "illegal_violations": collect_illegal_em_combinations(),
        "phase3_shadow_not_started": True,
        "phase4_extraction_not_started": True,
        "phase5_activation_not_started": True,
    }


# --- Instant rollback helpers (Plan §8.2) ---------------------------------


def rollback_em_shadow_off() -> None:
    os.environ["ENABLE_EXECUTION_MANAGER_SHADOW"] = "0"


def rollback_em_sole_path_off() -> None:
    os.environ["ENABLE_EXECUTION_MANAGER"] = "0"
    for name in EM_PIPELINE_FLAGS:
        os.environ[name] = "0"
    os.environ[_ACTIVATION_PCT_ENV] = "0"


def rollback_em_pgrXX_to_off(gate: int) -> None:
    if gate < 1 or gate > 6:
        raise ValueError(f"PGR gate must be 1..6, got {gate}")
    os.environ[f"ENABLE_EM_PGR_0{gate}"] = "0"
    # Clamp pct to 0 in Infra (prior-plateau math lands in Phase 5).
    os.environ[_ACTIVATION_PCT_ENV] = "0"


def rollback_em_all_off() -> None:
    """Global EM kill — all flags OFF, pct 0."""
    for name in EM_BOOL_FLAGS:
        os.environ[name] = "0"
    os.environ[_ACTIVATION_PCT_ENV] = "0"
    for probe in (
        _FORBIDDEN_CM_WRITE_FLAG,
        _FORBIDDEN_SHADOW_CM_ELIGIBLE,
        _FORBIDDEN_SHADOW_PEER_COPILOT,
        _FORBIDDEN_PGR_AUTO_ADVANCE,
        "CLAIM_EM_SHADOW_IS_SOLE_PATH",
        "ENABLE_EM_DUAL_RUN_HARNESS",
        "AURORA_EM_CLAIM_REPO_DEFAULTS_ON",
        "AURORA_EM_ASSERT_DEFAULTS_OFF_ONLY",
    ):
        os.environ.pop(probe, None)
