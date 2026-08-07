"""
Execution Manager — Phase 2 Infrastructure scaffolding.

Inert contracts, Step Runner skeleton, ports, and flag controller.
Defaults OFF. Not wired into the mega-router (Phase 3+).
"""

from __future__ import annotations

from src.execution_manager.contracts import (
    ANALYZE_FROZEN_ENGINE_ORDER,
    AbortReason,
    ExecutionMode,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    FixtureQuality,
    PipelineId,
    StepStatus,
    StepTrace,
)
from src.execution_manager.flags import (
    IllegalEmFlagMatrixError,
    assert_legal_em_flag_matrix,
    em_flag_snapshot,
    em_flags_all_off,
)
from src.execution_manager.step_runner import ExecutionManager, StepRunner

__all__ = [
    "ANALYZE_FROZEN_ENGINE_ORDER",
    "AbortReason",
    "ExecutionManager",
    "ExecutionMode",
    "ExecutionRequest",
    "ExecutionResult",
    "ExecutionStatus",
    "FixtureQuality",
    "IllegalEmFlagMatrixError",
    "PipelineId",
    "StepRunner",
    "StepStatus",
    "StepTrace",
    "assert_legal_em_flag_matrix",
    "em_flag_snapshot",
    "em_flags_all_off",
]
