"""
Execution Manager — Phase 2/3 scaffolding + Phase 4 Stage 1 thin extraction.

Contracts, Step Runner, ports, flag controller, Shadow Mode (observe-only),
and thin-report progressive extraction behind DEFAULT OFF pipeline flags.
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
    pipeline_enabled,
    rollback_em_all_off,
    rollback_em_shadow_off,
    rollback_em_sole_path_off,
    shadow_enabled,
    thin_pipeline_extraction_enabled,
)
from src.execution_manager.router_shim import em_thin_or_legacy
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
    "em_thin_or_legacy",
    "maybe_em_shadow_observe",
    "pipeline_enabled",
    "rollback_em_all_off",
    "rollback_em_shadow_off",
    "rollback_em_sole_path_off",
    "shadow_compare",
    "shadow_enabled",
    "shadow_metrics_snapshot",
    "thin_pipeline_extraction_enabled",
]
