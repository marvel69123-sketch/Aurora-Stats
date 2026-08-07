"""
Execution Manager — Phase 2 Infrastructure scaffolding + Phase 3 Shadow observe.

Contracts, Step Runner skeleton, ports, flag controller, and Shadow Mode
(observe-only dual-run). Defaults OFF. Shadow never replaces production results.
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
    rollback_em_shadow_off,
    shadow_enabled,
)
from src.execution_manager.shadow import (
    APPENDIX_A_MANDATORY_KEYS,
    ShadowCompareResult,
    maybe_em_shadow_observe,
    shadow_compare,
    shadow_metrics_snapshot,
)
from src.execution_manager.step_runner import ExecutionManager, StepRunner

__all__ = [
    "ANALYZE_FROZEN_ENGINE_ORDER",
    "APPENDIX_A_MANDATORY_KEYS",
    "AbortReason",
    "ExecutionManager",
    "ExecutionMode",
    "ExecutionRequest",
    "ExecutionResult",
    "ExecutionStatus",
    "FixtureQuality",
    "IllegalEmFlagMatrixError",
    "PipelineId",
    "ShadowCompareResult",
    "StepRunner",
    "StepStatus",
    "StepTrace",
    "assert_legal_em_flag_matrix",
    "em_flag_snapshot",
    "em_flags_all_off",
    "maybe_em_shadow_observe",
    "rollback_em_shadow_off",
    "shadow_compare",
    "shadow_enabled",
    "shadow_metrics_snapshot",
]
