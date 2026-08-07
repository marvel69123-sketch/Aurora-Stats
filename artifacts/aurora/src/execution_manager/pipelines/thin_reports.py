"""Thin report pipeline stubs — Phase 2 scaffolding."""

from __future__ import annotations

from src.execution_manager.contracts import (
    THIN_BANKROLL_STEPS,
    THIN_KNOWLEDGE_STEPS,
    THIN_LEARNING_STEPS,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    StepStatus,
    StepTrace,
)
from src.execution_manager.observability import emit
from src.execution_manager.ports import PortBundle


def _thin(
    request: ExecutionRequest,
    ports: PortBundle,
    *,
    pipeline_id: str,
    steps: tuple[str, ...],
    assembler: str,
) -> ExecutionResult:
    traces: list[StepTrace] = []
    emit("em.run.started", run_id=request.run_id, pipeline_id=pipeline_id)
    scratch: dict = {}
    for step_id in steps:
        emit("em.step.started", step_id=step_id)
        if step_id == "load_learning_stats":
            scratch["stats"] = ports.db.learning_stats()
        elif step_id == "search_knowledge_items":
            q = str((request.entities or {}).get("query") or "")
            scratch["items"] = ports.db.knowledge_search(q)
        else:
            scratch[assembler] = {"stub": True, "pipeline_id": pipeline_id}
        traces.append(StepTrace(step_id=step_id, status=StepStatus.COMPLETED))
        emit("em.step.completed", step_id=step_id)

    result = ExecutionResult(
        run_id=request.run_id,
        pipeline_id=pipeline_id,
        status=ExecutionStatus.COMPLETED,
        payload={"intent": pipeline_id, "stub": True, **scratch},
        step_traces=traces,
        diagnostics={"stub": True},
    )
    emit("em.run.completed", run_id=request.run_id, pipeline_id=pipeline_id)
    return result


def run_bankroll_stub(request: ExecutionRequest, ports: PortBundle) -> ExecutionResult:
    return _thin(
        request,
        ports,
        pipeline_id="bankroll",
        steps=THIN_BANKROLL_STEPS,
        assembler="assemble_bankroll_payload",
    )


def run_learning_stub(request: ExecutionRequest, ports: PortBundle) -> ExecutionResult:
    return _thin(
        request,
        ports,
        pipeline_id="learning",
        steps=THIN_LEARNING_STEPS,
        assembler="assemble_learning_payload",
    )


def run_knowledge_stub(request: ExecutionRequest, ports: PortBundle) -> ExecutionResult:
    return _thin(
        request,
        ports,
        pipeline_id="knowledge",
        steps=THIN_KNOWLEDGE_STEPS,
        assembler="assemble_knowledge_payload",
    )
