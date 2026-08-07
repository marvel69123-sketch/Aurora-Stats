"""Live pipeline stub (L0–L4) — Phase 2 scaffolding."""

from __future__ import annotations

from src.execution_manager.contracts import (
    LIVE_STEP_ORDER,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    StepStatus,
    StepTrace,
)
from src.execution_manager.observability import emit
from src.execution_manager.ports import PortBundle


def run_live_stub(request: ExecutionRequest, ports: PortBundle) -> ExecutionResult:
    traces: list[StepTrace] = []
    emit("em.run.started", run_id=request.run_id, pipeline_id="live")

    emit("em.step.started", step_id="budget_check")
    if not ports.budget_gate.may_run("budget_check", request.budget_token):
        traces.append(
            StepTrace(step_id="budget_check", status=StepStatus.FAILED, reason="budget_denied")
        )
        return ExecutionResult(
            run_id=request.run_id,
            pipeline_id="live",
            status=ExecutionStatus.FAILED,
            payload={"error": "budget_denied"},
            step_traces=traces,
            diagnostics={"stub": True},
        )
    traces.append(StepTrace(step_id="budget_check", status=StepStatus.COMPLETED))

    emit("em.step.started", step_id="fetch_live_feed")
    feed = ports.fetch_live_feed.fetch(
        force_refresh=bool((request.flags or {}).get("force_refresh"))
    )
    traces.append(StepTrace(step_id="fetch_live_feed", status=StepStatus.COMPLETED))

    emit("em.step.started", step_id="live_intelligence")
    live_out = ports.engine.run("live_intelligence", {"feed": feed})
    traces.append(StepTrace(step_id="live_intelligence", status=StepStatus.COMPLETED))

    for step_id in ("structured_payload", "match_card_fields"):
        traces.append(StepTrace(step_id=step_id, status=StepStatus.COMPLETED))

    assert [t.step_id for t in traces] == list(LIVE_STEP_ORDER)
    result = ExecutionResult(
        run_id=request.run_id,
        pipeline_id="live",
        status=ExecutionStatus.COMPLETED,
        payload={
            "intent": "live_opportunities",
            "stub": True,
            "feed": feed,
            "live_intelligence": live_out,
            "match_card_fields": {"emitted": True, "attached": False},
        },
        step_traces=traces,
        diagnostics={"stub": True},
    )
    emit("em.run.completed", run_id=request.run_id, pipeline_id="live")
    return result
