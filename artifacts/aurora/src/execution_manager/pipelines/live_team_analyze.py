"""live_team_analyze composite stub (T0–T1) — Phase 2 scaffolding."""

from __future__ import annotations

from src.execution_manager.contracts import (
    LIVE_TEAM_STEP_ORDER,
    ExecutionMode,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    StepStatus,
    StepTrace,
)
from src.execution_manager.observability import emit
from src.execution_manager.pipelines.analyze import run_analyze_stub
from src.execution_manager.ports import PortBundle


def run_live_team_analyze_stub(
    request: ExecutionRequest, ports: PortBundle
) -> ExecutionResult:
    traces: list[StepTrace] = []
    emit("em.run.started", run_id=request.run_id, pipeline_id="live_team_analyze")

    # T0 — Tool Use live list search via FetchLiveFeed port (inert).
    emit("em.step.started", step_id="search_live_for_team")
    feed = ports.fetch_live_feed.fetch()
    traces.append(
        StepTrace(step_id="search_live_for_team", status=StepStatus.COMPLETED)
    )
    emit("em.step.completed", step_id="search_live_for_team")

    # T1 — delegate analyze with prefer_live=True (same Step Runner path).
    emit("em.step.started", step_id="delegate_analyze")
    child_flags = dict(request.flags or {})
    child_flags["prefer_live"] = True
    child = ExecutionRequest(
        run_id=f"{request.run_id}:analyze",
        pipeline_id="analyze",
        session_id=request.session_id,
        mode=request.mode if isinstance(request.mode, ExecutionMode) else request.mode,
        entities=dict(request.entities or {}),
        flags=child_flags,
        budget_token=request.budget_token,
        read_projections=request.read_projections,
        timeout_ms=request.timeout_ms,
        trace_parent=request.trace_parent,
    )
    analyze_result = run_analyze_stub(child, ports)
    traces.append(StepTrace(step_id="delegate_analyze", status=StepStatus.COMPLETED))
    emit("em.step.completed", step_id="delegate_analyze")

    assert [t.step_id for t in traces] == list(LIVE_TEAM_STEP_ORDER)
    result = ExecutionResult(
        run_id=request.run_id,
        pipeline_id="live_team_analyze",
        status=analyze_result.status,
        payload={
            "stub": True,
            "live_feed": feed,
            "analyze": analyze_result.payload,
        },
        step_traces=traces + list(analyze_result.step_traces),
        abort_reason=analyze_result.abort_reason,
        fixture_quality=analyze_result.fixture_quality,
        diagnostics={"stub": True, "child_run_id": child.run_id},
    )
    emit("em.run.completed", run_id=request.run_id, pipeline_id="live_team_analyze")
    return result
