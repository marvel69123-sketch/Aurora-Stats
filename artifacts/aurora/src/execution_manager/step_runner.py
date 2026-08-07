"""
Step Runner core + ExecutionManager façade (Phase 2 scaffolding).

NOT wired into copilot_unified_router. Call only from tests / future Shadow.
"""

from __future__ import annotations

from src.execution_manager.contracts import (
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    PipelineId,
)
from src.execution_manager.observability import emit
from src.execution_manager.ports import PortBundle
from src.execution_manager.registry import ensure_default_registrations, get_pipeline


class StepRunner:
    """Sequential Step Runner — dispatches to registered pipeline stubs."""

    def __init__(self, ports: PortBundle | None = None) -> None:
        self.ports = ports or PortBundle()
        ensure_default_registrations()

    def run(self, request: ExecutionRequest) -> ExecutionResult:
        pipeline_id = request.normalized_pipeline_id()
        handler = get_pipeline(pipeline_id)
        if handler is None:
            emit("em.run.failed", run_id=request.run_id, reason="unknown_pipeline")
            return ExecutionResult(
                run_id=request.run_id,
                pipeline_id=str(pipeline_id.value if isinstance(pipeline_id, PipelineId) else pipeline_id),
                status=ExecutionStatus.FAILED,
                payload={"error": "unknown_pipeline", "pipeline_id": str(pipeline_id)},
                diagnostics={"stub": True},
            )
        return handler(request, self.ports)


class ExecutionManager:
    """
    Spec §4.1 conceptual API.

    shadow_compare is a Phase 2 stub returning a placeholder — dual-run wiring
    is Phase 3 and must NOT be called from the Router yet.
    """

    def __init__(self, ports: PortBundle | None = None) -> None:
        self._runner = StepRunner(ports=ports)

    def run(self, request: ExecutionRequest) -> ExecutionResult:
        return self._runner.run(request)

    def shadow_compare(self, request: ExecutionRequest) -> dict:
        """Observe-only stub — Phase 3 will implement real dual-run compare."""
        emit("em.shadow.diff", run_id=request.run_id, stub=True, wired=False)
        return {
            "run_id": request.run_id,
            "stub": True,
            "wired": False,
            "phase": 2,
            "message": "shadow_compare scaffolding only — dual-run not armed",
        }
