"""
Analyze pipeline stub (A0–A13) — Phase 2 Infrastructure.

Wires HARD-ABORT → Completed + blocked payload (Plan §3.1 / CDR2-M-001).
Does not import Frozen engines or Router helpers.
"""

from __future__ import annotations

from typing import Any

from src.execution_manager.contracts import (
    ANALYZE_FROZEN_ENGINE_ORDER,
    ANALYZE_STEP_ORDER,
    AbortReason,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    FixtureQuality,
    StepStatus,
    StepTrace,
    blocked_integrity_payload_stub,
)
from src.execution_manager.observability import emit
from src.execution_manager.ports import PortBundle


def _entities(request: ExecutionRequest) -> dict[str, Any]:
    return dict(request.entities or {})


def _integrity_outcome(
    request: ExecutionRequest,
    fetch: dict[str, Any],
) -> str:
    """
    Stub §5.2.1 edge classifier using request.flags / entities markers.

    Outcomes: HARD_ABORT | SOFT_SKIP | PARTIAL | PASS
    """
    flags = dict(request.flags or {})
    ents = _entities(request)
    forced = str(flags.get("integrity_outcome") or "").upper()
    if forced in {"HARD_ABORT", "SOFT_SKIP", "PARTIAL", "PASS"}:
        return forced

    quality = str(
        ents.get("fixture_quality")
        or flags.get("fixture_quality")
        or fetch.get("fixture_quality")
        or ""
    ).upper()
    named_blocked = bool(
        flags.get("named_assess_blocked")
        or ents.get("entity_invalid")
        or quality == FixtureQuality.INVALID.value
    )
    fixture_id = int(fetch.get("fixture_id") or ents.get("fixture_id") or 0)
    if named_blocked and fixture_id <= 0:
        return "HARD_ABORT"
    if named_blocked and fixture_id > 0:
        return "SOFT_SKIP"
    if quality == FixtureQuality.PARTIAL.value or flags.get("partial"):
        return "PARTIAL"
    return "PASS"


def run_analyze_stub(request: ExecutionRequest, ports: PortBundle) -> ExecutionResult:
    traces: list[StepTrace] = []
    scratch: dict[str, Any] = {"entities": _entities(request)}
    emit("em.run.started", run_id=request.run_id, pipeline_id="analyze")

    # A0 budget_check
    emit("em.step.started", step_id="budget_check", run_id=request.run_id)
    may = ports.budget_gate.may_run("budget_check", request.budget_token)
    if not may:
        traces.append(
            StepTrace(
                step_id="budget_check",
                status=StepStatus.FAILED,
                reason="budget_denied",
            )
        )
        emit("em.step.failed", step_id="budget_check", reason="budget_denied")
        result = ExecutionResult(
            run_id=request.run_id,
            pipeline_id="analyze",
            status=ExecutionStatus.FAILED,
            payload={"error": "budget_denied"},
            step_traces=traces,
            diagnostics={"stub": True},
        )
        emit("em.run.failed", run_id=request.run_id)
        return result
    traces.append(StepTrace(step_id="budget_check", status=StepStatus.COMPLETED))
    emit("em.step.completed", step_id="budget_check")

    # A1 fetch_fixture
    emit("em.step.started", step_id="fetch_fixture", run_id=request.run_id)
    ents = _entities(request)
    fetch = ports.fetch_fixture.fetch(
        home=ents.get("home"),
        away=ents.get("away"),
        force_refresh=bool((request.flags or {}).get("force_refresh")),
        soft=True,
    )
    scratch["fetch"] = fetch
    traces.append(StepTrace(step_id="fetch_fixture", status=StepStatus.COMPLETED))
    emit("em.step.completed", step_id="fetch_fixture")

    # A2 integrity_gate
    emit("em.step.started", step_id="integrity_gate", run_id=request.run_id)
    outcome = _integrity_outcome(request, fetch)
    if outcome == "HARD_ABORT":
        traces.append(
            StepTrace(
                step_id="integrity_gate",
                status=StepStatus.FAILED,
                reason=AbortReason.INTEGRITY_INVALID_HARD_ABORT.value,
            )
        )
        emit(
            "em.step.failed",
            step_id="integrity_gate",
            reason=AbortReason.INTEGRITY_INVALID_HARD_ABORT.value,
        )
        payload = blocked_integrity_payload_stub(
            home=str(ents.get("home") or ""),
            away=str(ents.get("away") or ""),
        )
        # Plan §3.1: HARD-ABORT → Completed + blocked/INVALID (HTTP-compatible).
        result = ExecutionResult(
            run_id=request.run_id,
            pipeline_id="analyze",
            status=ExecutionStatus.COMPLETED,
            payload=payload,
            step_traces=traces,
            abort_reason=AbortReason.INTEGRITY_INVALID_HARD_ABORT.value,
            fixture_quality=FixtureQuality.INVALID.value,
            diagnostics={"stub": True, "integrity_outcome": outcome},
        )
        emit("em.run.completed", run_id=request.run_id, abort_reason=result.abort_reason)
        return result

    if outcome == "SOFT_SKIP":
        traces.append(
            StepTrace(
                step_id="integrity_gate",
                status=StepStatus.SKIPPED,
                reason="integrity_soft_skip_fixture_located",
            )
        )
        emit(
            "em.step.skipped",
            step_id="integrity_gate",
            reason="integrity_soft_skip_fixture_located",
        )
        scratch["fixture_quality"] = FixtureQuality.VALID_LOCATED.value
    elif outcome == "PARTIAL":
        traces.append(
            StepTrace(
                step_id="integrity_gate",
                status=StepStatus.COMPLETED,
                reason="integrity_partial_continue",
            )
        )
        emit("em.step.completed", step_id="integrity_gate", reason="partial")
        scratch["fixture_quality"] = FixtureQuality.PARTIAL.value
    else:
        traces.append(StepTrace(step_id="integrity_gate", status=StepStatus.COMPLETED))
        emit("em.step.completed", step_id="integrity_gate")
        scratch["fixture_quality"] = FixtureQuality.VALID.value

    # A3–A10 Frozen engines (order locked) via Engine.port stub
    for step_id in ANALYZE_FROZEN_ENGINE_ORDER:
        emit("em.step.started", step_id=step_id, run_id=request.run_id)
        engine_out = ports.engine.run(step_id, scratch)
        scratch[step_id] = engine_out
        traces.append(StepTrace(step_id=step_id, status=StepStatus.COMPLETED))
        emit("em.step.completed", step_id=step_id)

    # A11–A13 assembly stubs (emit fields only — no attach_match_card)
    for step_id in (
        "partial_inference_assembly",
        "structured_payload",
        "match_card_fields",
    ):
        emit("em.step.started", step_id=step_id, run_id=request.run_id)
        traces.append(StepTrace(step_id=step_id, status=StepStatus.COMPLETED))
        emit("em.step.completed", step_id=step_id)

    # Verify declared order coverage (scaffolding invariant)
    assert [t.step_id for t in traces] == list(ANALYZE_STEP_ORDER)

    fq = str(scratch.get("fixture_quality") or FixtureQuality.VALID.value)
    payload = {
        "intent": "analyze_match",
        "entities": ents,
        "fixture_quality": fq,
        "stub": True,
        "engines_run": list(ANALYZE_FROZEN_ENGINE_ORDER),
        "match_card_fields": {"emitted": True, "attached": False},
        "best_markets": [],
    }
    result = ExecutionResult(
        run_id=request.run_id,
        pipeline_id="analyze",
        status=ExecutionStatus.COMPLETED,
        payload=payload,
        step_traces=traces,
        fixture_quality=fq,
        diagnostics={"stub": True, "integrity_outcome": outcome},
    )
    emit("em.run.completed", run_id=request.run_id)
    return result
