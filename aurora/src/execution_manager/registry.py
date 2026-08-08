"""Pipeline stub registry — component registration scaffolding (Phase 2)."""

from __future__ import annotations

from typing import Callable

from src.execution_manager.contracts import ExecutionRequest, ExecutionResult, PipelineId
from src.execution_manager.ports import PortBundle

PipelineHandler = Callable[[ExecutionRequest, PortBundle], ExecutionResult]

_REGISTRY: dict[PipelineId, PipelineHandler] = {}


def register_pipeline(pipeline_id: PipelineId, handler: PipelineHandler) -> None:
    _REGISTRY[pipeline_id] = handler


def get_pipeline(pipeline_id: PipelineId) -> PipelineHandler | None:
    return _REGISTRY.get(pipeline_id)


def registered_pipeline_ids() -> tuple[PipelineId, ...]:
    return tuple(_REGISTRY.keys())


def clear_registry() -> None:
    _REGISTRY.clear()


def ensure_default_registrations() -> None:
    """Idempotent registration of Phase 2 pipeline stubs."""
    from src.execution_manager.pipelines import (
        run_analyze_stub,
        run_bankroll_stub,
        run_knowledge_stub,
        run_learning_stub,
        run_live_stub,
        run_live_team_analyze_stub,
    )

    mapping = {
        PipelineId.ANALYZE: run_analyze_stub,
        PipelineId.LIVE: run_live_stub,
        PipelineId.BANKROLL: run_bankroll_stub,
        PipelineId.LEARNING: run_learning_stub,
        PipelineId.KNOWLEDGE: run_knowledge_stub,
        PipelineId.LIVE_TEAM_ANALYZE: run_live_team_analyze_stub,
    }
    for pid, handler in mapping.items():
        if pid not in _REGISTRY:
            register_pipeline(pid, handler)
