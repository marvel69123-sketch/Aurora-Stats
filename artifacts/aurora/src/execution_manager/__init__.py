"""
Execution Manager — Phase 2/3 scaffolding + Phase 4 Progressive Extraction.

Contracts, Step Runner, ports, flag controller, Shadow Mode (observe-only),
thin-report (E1), live (E2), analyze (E3), and live_team_analyze (E4)
progressive extraction behind DEFAULT OFF flags.
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
    analyze_pipeline_extraction_enabled,
    assert_legal_em_flag_matrix,
    em_flag_snapshot,
    em_flags_all_off,
    live_pipeline_extraction_enabled,
    live_team_pipeline_extraction_enabled,
    pipeline_enabled,
    rollback_em_all_off,
    rollback_em_shadow_off,
    rollback_em_sole_path_off,
    shadow_enabled,
    thin_pipeline_extraction_enabled,
)
from src.execution_manager.router_shim import (
    em_analyze_from_fixture,
    em_analyze_or_legacy,
    em_live_from_feed,
    em_live_or_legacy,
    em_live_team_from_feed,
    em_live_team_or_legacy,
    em_thin_or_legacy,
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
    "analyze_pipeline_extraction_enabled",
    "assert_legal_em_flag_matrix",
    "em_analyze_from_fixture",
    "em_analyze_or_legacy",
    "em_flag_snapshot",
    "em_flags_all_off",
    "em_live_from_feed",
    "em_live_or_legacy",
    "em_live_team_from_feed",
    "em_live_team_or_legacy",
    "em_thin_or_legacy",
    "live_pipeline_extraction_enabled",
    "live_team_pipeline_extraction_enabled",
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
