"""
Analyze pipeline — Phase 4 Progressive Extraction Stage 3 (E3).

Extracted equivalent of mega-router `_run_analyze` (soft fetch + A2 soft-analyze
integrity + Frozen A3–A10 + assembly). Match-card attachment stays Router-only.
No CM writes. Soft-try outer wrap stays Orchestration (§4.6).
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


def _is_full_fixture_payload(fetch: dict[str, Any]) -> bool:
    return (
        isinstance(fetch, dict)
        and isinstance(fetch.get("fixture"), dict)
        and isinstance(fetch.get("teams"), dict)
    )


def _integrity_outcome(
    request: ExecutionRequest,
    fetch: dict[str, Any],
) -> str:
    """
    §5.2.1 edge classifier.

    Outcomes: HARD_ABORT | SOFT_SKIP | PARTIAL | PASS

    Harness may force via request.flags. Production full payloads use SoT
    assess_named_fixture + fixture_located (alias / live-API soft-skip).
    """
    flags = dict(request.flags or {})
    ents = _entities(request)
    forced = str(flags.get("integrity_outcome") or "").upper()
    if forced in {"HARD_ABORT", "SOFT_SKIP", "PARTIAL", "PASS"}:
        return forced

    if _is_full_fixture_payload(fetch):
        is_partial = bool(fetch.get("_partial")) or (fetch.get("fixture") or {}).get(
            "id"
        ) == 0
        fixture_id_early = (fetch.get("fixture") or {}).get("id") or 0
        try:
            fixture_id_early = int(fixture_id_early or 0)
        except (TypeError, ValueError):
            fixture_id_early = 0
        fixture_located_early = (not is_partial) and fixture_id_early > 0
        home = str(ents.get("home") or flags.get("home") or "")
        away = str(ents.get("away") or flags.get("away") or "")
        try:
            from src.core.fixture_integrity import assess_named_fixture

            teams = fetch.get("teams") or {}
            hn = ((teams.get("home") or {}).get("name")) or home
            an = ((teams.get("away") or {}).get("name")) or away
            pre = assess_named_fixture(home or hn, away or an)
            if pre.is_blocked and fixture_located_early:
                return "SOFT_SKIP"
            if pre.is_blocked and not fixture_located_early:
                return "HARD_ABORT"
            if is_partial or not fixture_located_early:
                return "PARTIAL"
            return "PASS"
        except Exception:
            pass

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


def _hard_abort_payload(ents: dict[str, Any], fetch: dict[str, Any]) -> dict[str, Any]:
    """Prefer real blocked payload when assess is available; else stub shape."""
    home = str(ents.get("home") or fetch.get("home") or "")
    away = str(ents.get("away") or fetch.get("away") or "")
    if _is_full_fixture_payload(fetch):
        try:
            from src.brain import get_brain_meta
            from src.core.fixture_integrity import (
                assess_named_fixture,
                blocked_integrity_payload,
            )

            teams = fetch.get("teams") or {}
            hn = ((teams.get("home") or {}).get("name")) or home
            an = ((teams.get("away") or {}).get("name")) or away
            pre = assess_named_fixture(home or hn, away or an)
            return blocked_integrity_payload(pre, brain=get_brain_meta())
        except Exception:
            pass
    return blocked_integrity_payload_stub(home=home, away=away)


def _emit_remaining_completed(traces: list[StepTrace]) -> None:
    """Record A3–A13 as completed (engines ran inside production assemble in Frozen order)."""
    present = {t.step_id for t in traces}
    for step_id in ANALYZE_STEP_ORDER:
        if step_id in present:
            continue
        emit("em.step.started", step_id=step_id)
        traces.append(StepTrace(step_id=step_id, status=StepStatus.COMPLETED))
        emit("em.step.completed", step_id=step_id)


def run_analyze(request: ExecutionRequest, ports: PortBundle) -> ExecutionResult:
    """
    A0–A13 analyze pipeline (Plan E3).

    A13 emits match_card_fields metadata only — never calls attach_match_card.
    Soft-try / post-integrity / CM eligibility remain Orchestration (§4.6–§4.7).
    """
    traces: list[StepTrace] = []
    scratch: dict[str, Any] = {"entities": _entities(request)}
    emit("em.run.started", run_id=request.run_id, pipeline_id="analyze")
    ents = _entities(request)
    flags = dict(request.flags or {})

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
            payload={"error": "budget_denied", "intent": "analyze_match"},
            step_traces=traces,
            diagnostics={"phase4_stage3": True, "analyze": True},
        )
        emit("em.run.failed", run_id=request.run_id)
        return result
    traces.append(StepTrace(step_id="budget_check", status=StepStatus.COMPLETED))
    emit("em.step.completed", step_id="budget_check")

    # A1 fetch_fixture
    emit("em.step.started", step_id="fetch_fixture", run_id=request.run_id)
    fetch = ports.fetch_fixture.fetch(
        home=ents.get("home") or flags.get("home"),
        away=ents.get("away") or flags.get("away"),
        force_refresh=bool(flags.get("force_refresh")),
        soft=True,
    )
    scratch["fetch"] = fetch
    traces.append(StepTrace(step_id="fetch_fixture", status=StepStatus.COMPLETED))
    emit("em.step.completed", step_id="fetch_fixture")

    # A2 integrity_gate (§5.2.1)
    emit("em.step.started", step_id="integrity_gate", run_id=request.run_id)
    outcome = _integrity_outcome(request, fetch if isinstance(fetch, dict) else {})
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
        payload = _hard_abort_payload(ents, fetch if isinstance(fetch, dict) else {})
        result = ExecutionResult(
            run_id=request.run_id,
            pipeline_id="analyze",
            status=ExecutionStatus.COMPLETED,
            payload=payload,
            step_traces=traces,
            abort_reason=AbortReason.INTEGRITY_INVALID_HARD_ABORT.value,
            fixture_quality=FixtureQuality.INVALID.value,
            diagnostics={
                "phase4_stage3": True,
                "analyze": True,
                "integrity_outcome": outcome,
                "stub": not _is_full_fixture_payload(fetch if isinstance(fetch, dict) else {}),
            },
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

    # Production path — full analyze_fixture-shaped data
    if _is_full_fixture_payload(fetch if isinstance(fetch, dict) else {}):
        try:
            from src.execution_manager.pipelines.analyze_production import (
                build_analyze_payload_from_data,
            )

            home = str(ents.get("home") or flags.get("home") or "")
            away = str(ents.get("away") or flags.get("away") or "")
            prefer_live = bool(flags.get("prefer_live"))
            payload = build_analyze_payload_from_data(
                dict(fetch),
                home,
                away,
                prefer_live=prefer_live,
            )
            # Defense-in-depth HARD-ABORT from parity body
            if (
                isinstance(payload, dict)
                and payload.get("fixture_quality") == FixtureQuality.INVALID.value
                and payload.get("entities", {}).get("entity_invalid") is True
            ):
                traces[-1] = StepTrace(
                    step_id="integrity_gate",
                    status=StepStatus.FAILED,
                    reason=AbortReason.INTEGRITY_INVALID_HARD_ABORT.value,
                )
                result = ExecutionResult(
                    run_id=request.run_id,
                    pipeline_id="analyze",
                    status=ExecutionStatus.COMPLETED,
                    payload=payload,
                    step_traces=traces,
                    abort_reason=AbortReason.INTEGRITY_INVALID_HARD_ABORT.value,
                    fixture_quality=FixtureQuality.INVALID.value,
                    diagnostics={
                        "phase4_stage3": True,
                        "analyze": True,
                        "integrity_outcome": "HARD_ABORT",
                        "stub": False,
                    },
                )
                emit(
                    "em.run.completed",
                    run_id=request.run_id,
                    abort_reason=result.abort_reason,
                )
                return result

            _emit_remaining_completed(traces)
            assert [t.step_id for t in traces] == list(ANALYZE_STEP_ORDER)
            fq = str(
                payload.get("fixture_quality")
                or scratch.get("fixture_quality")
                or FixtureQuality.VALID.value
            )
            # Soft-skip culture marker on Result when A2 skipped
            if outcome == "SOFT_SKIP":
                fq = FixtureQuality.VALID_LOCATED.value
            result = ExecutionResult(
                run_id=request.run_id,
                pipeline_id="analyze",
                status=ExecutionStatus.COMPLETED,
                payload=payload,
                step_traces=traces,
                fixture_quality=fq,
                diagnostics={
                    "phase4_stage3": True,
                    "analyze": True,
                    "stub": False,
                    "integrity_outcome": outcome,
                    "match_card_fields": {"emitted": True, "attached": False},
                    "analyze_fixture_data": fetch,
                },
            )
            emit("em.run.completed", run_id=request.run_id)
            return result
        except Exception as exc:
            traces.append(
                StepTrace(
                    step_id="structured_payload",
                    status=StepStatus.FAILED,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            emit("em.step.failed", step_id="structured_payload", error=str(exc))
            emit("em.run.failed", run_id=request.run_id, pipeline_id="analyze")
            return ExecutionResult(
                run_id=request.run_id,
                pipeline_id="analyze",
                status=ExecutionStatus.FAILED,
                payload={"error": str(exc), "intent": "analyze_match"},
                step_traces=traces,
                diagnostics={"phase4_stage3": True, "analyze": True},
            )

    # Inert / harness scaffolding path (Phase 2 golden soft-analyze contracts)
    for step_id in ANALYZE_FROZEN_ENGINE_ORDER:
        emit("em.step.started", step_id=step_id, run_id=request.run_id)
        engine_out = ports.engine.run(step_id, scratch)
        scratch[step_id] = engine_out
        traces.append(StepTrace(step_id=step_id, status=StepStatus.COMPLETED))
        emit("em.step.completed", step_id=step_id)

    for step_id in (
        "partial_inference_assembly",
        "structured_payload",
        "match_card_fields",
    ):
        emit("em.step.started", step_id=step_id, run_id=request.run_id)
        traces.append(StepTrace(step_id=step_id, status=StepStatus.COMPLETED))
        emit("em.step.completed", step_id=step_id)

    assert [t.step_id for t in traces] == list(ANALYZE_STEP_ORDER)

    fq = str(scratch.get("fixture_quality") or FixtureQuality.VALID.value)
    payload = {
        "intent": "analyze_match",
        "entities": ents,
        "fixture_quality": fq if fq != FixtureQuality.VALID_LOCATED.value else "VALID",
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
        diagnostics={
            "phase4_stage3": True,
            "analyze": True,
            "stub": True,
            "integrity_outcome": outcome,
        },
    )
    emit("em.run.completed", run_id=request.run_id)
    return result


# Phase 2 registry alias (name retained for harness compatibility).
run_analyze_stub = run_analyze
