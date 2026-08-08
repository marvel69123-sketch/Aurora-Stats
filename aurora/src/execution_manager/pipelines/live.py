"""
Live pipeline — Phase 4 Progressive Extraction Stage 2 (E2).

Extracted equivalent of mega-router `_run_live` core (fetch + Frozen live
intelligence + structured payload). Match-card attachment stays Router-only
(post-EM). No CM writes. No Tool Registry.
"""

from __future__ import annotations

from typing import Any

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


def _fixtures_from_feed(feed: Any) -> list[dict[str, Any]]:
    if isinstance(feed, list):
        return list(feed)
    if not isinstance(feed, dict):
        return []
    matches = feed.get("matches")
    if isinstance(matches, list):
        return list(matches)
    fixtures = feed.get("fixtures")
    if isinstance(fixtures, list):
        return list(fixtures)
    return []


def run_live(request: ExecutionRequest, ports: PortBundle) -> ExecutionResult:
    """
    L0–L4 live pipeline (Plan E2).

    L4 emits match_card_fields metadata only — never calls attach_match_card.
    """
    traces: list[StepTrace] = []
    emit("em.run.started", run_id=request.run_id, pipeline_id="live")
    scratch: dict[str, Any] = {}
    payload: dict[str, Any] = {}

    for step_id in LIVE_STEP_ORDER:
        emit("em.step.started", step_id=step_id)
        try:
            if step_id == "budget_check":
                if not ports.budget_gate.may_run("budget_check", request.budget_token):
                    traces.append(
                        StepTrace(
                            step_id=step_id,
                            status=StepStatus.FAILED,
                            reason="budget_denied",
                        )
                    )
                    emit("em.step.failed", step_id=step_id, reason="budget_denied")
                    emit("em.run.failed", run_id=request.run_id, pipeline_id="live")
                    return ExecutionResult(
                        run_id=request.run_id,
                        pipeline_id="live",
                        status=ExecutionStatus.FAILED,
                        payload={"error": "budget_denied", "intent": "live_opportunities"},
                        step_traces=traces,
                        diagnostics={"phase4_stage2": True, "live": True},
                    )
            elif step_id == "fetch_live_feed":
                scratch["feed"] = ports.fetch_live_feed.fetch(
                    force_refresh=bool((request.flags or {}).get("force_refresh"))
                )
            elif step_id == "live_intelligence":
                scratch["live_out"] = ports.engine.run(
                    "live_intelligence",
                    {"feed": scratch.get("feed") or {}},
                )
            elif step_id == "structured_payload":
                live_out = scratch.get("live_out")
                if isinstance(live_out, dict) and live_out.get("intent") == "live_opportunities":
                    payload = dict(live_out)
                elif isinstance(live_out, dict) and "payload" in live_out:
                    inner = live_out.get("payload")
                    payload = dict(inner) if isinstance(inner, dict) else {}
                else:
                    # Inert / harness engine — assemble minimal live shape
                    feed = scratch.get("feed") or {}
                    fixtures = _fixtures_from_feed(feed)
                    payload = {
                        "intent": "live_opportunities",
                        "entities": {"live_count": len(fixtures)},
                        "match": None,
                        "status": "Live",
                        "is_live": True,
                        "minute": None,
                        "executive_summary": "",
                        "best_markets": [],
                        "confidence": {},
                        "risk": {},
                        "bankroll_recommendation": {},
                        "positive_factors": [],
                        "negative_factors": [],
                        "historical_references": [],
                        "knowledge_notes": [],
                        "final_recommendation": "",
                        "aurora_version": "Copilot v1.0",
                        "brain": {},
                        "live_intelligence": live_out,
                    }
            elif step_id == "match_card_fields":
                # Emit fields only — attach_match_card is Router post-EM (Plan §7.3).
                scratch["match_card_fields"] = {
                    "emitted": True,
                    "attached": False,
                    "fixtures_available": len(_fixtures_from_feed(scratch.get("feed"))),
                }
                if isinstance(payload, dict):
                    # Do not mutate client contract with attach; diagnostics carry meta.
                    pass

            traces.append(StepTrace(step_id=step_id, status=StepStatus.COMPLETED))
            emit("em.step.completed", step_id=step_id)
        except Exception as exc:
            traces.append(
                StepTrace(
                    step_id=step_id,
                    status=StepStatus.FAILED,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            emit("em.step.failed", step_id=step_id, error=str(exc))
            emit("em.run.failed", run_id=request.run_id, pipeline_id="live")
            return ExecutionResult(
                run_id=request.run_id,
                pipeline_id="live",
                status=ExecutionStatus.FAILED,
                payload={"error": str(exc), "intent": "live_opportunities"},
                step_traces=traces,
                diagnostics={"phase4_stage2": True, "live": True},
            )

    assert [t.step_id for t in traces] == list(LIVE_STEP_ORDER)
    fixtures = _fixtures_from_feed(scratch.get("feed"))
    result = ExecutionResult(
        run_id=request.run_id,
        pipeline_id="live",
        status=ExecutionStatus.COMPLETED,
        payload=payload,
        step_traces=traces,
        diagnostics={
            "phase4_stage2": True,
            "live": True,
            "stub": False,
            "match_card_fields": scratch.get("match_card_fields"),
            # Router may use fixtures for post-EM match card (not CM write).
            "live_fixtures": fixtures,
        },
    )
    emit("em.run.completed", run_id=request.run_id, pipeline_id="live")
    return result


# Phase 2 registry alias (name retained for harness compatibility).
run_live_stub = run_live
