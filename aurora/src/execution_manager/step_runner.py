"""
Step Runner core + ExecutionManager façade.

Phase 3: shadow_compare is observe-only dual-run vs a provided legacy payload.
Phase 4 Stage 1: thin report pipelines are real handlers; Router shims gate
them behind DEFAULT OFF flags.
Phase 4 Stage 2: live pipeline is a real handler; Router async shim gates
it behind ENABLE_EM_PIPELINE_LIVE (DEFAULT OFF).
Phase 4 Stage 3: analyze pipeline is a real handler; Router async shim gates
it behind ENABLE_EM_PIPELINE_ANALYZE (DEFAULT OFF). Soft-try / CM eligibility
remain Orchestration. Match-card attach remains Router-only.
Phase 4 Stage 4: live_team_analyze composite is a real handler; Router async
shim gates it behind ENABLE_EM_PIPELINE_LIVE_TEAM (DEFAULT OFF).
Production primary path remains legacy when flags OFF.
"""

from __future__ import annotations

from typing import Any

from src.execution_manager.contracts import (
    ExecutionMode,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    PipelineId,
)
from src.execution_manager.observability import emit
from src.execution_manager.ports import PortBundle
from src.execution_manager.registry import ensure_default_registrations, get_pipeline


class StepRunner:
    """Sequential Step Runner — dispatches to registered pipeline handlers."""

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
                pipeline_id=str(
                    pipeline_id.value if isinstance(pipeline_id, PipelineId) else pipeline_id
                ),
                status=ExecutionStatus.FAILED,
                payload={"error": "unknown_pipeline", "pipeline_id": str(pipeline_id)},
                diagnostics={"stub": True},
            )
        return handler(request, self.ports)


class ExecutionManager:
    """
    Spec §4.1 conceptual API.

    `run` executes EM pipelines (thin = Stage 1; live = Stage 2; analyze = Stage 3;
    live_team_analyze = Stage 4).
    `shadow_compare` observes EM vs a legacy payload — never replaces primary.
    """

    def __init__(self, ports: PortBundle | None = None) -> None:
        self._runner = StepRunner(ports=ports)
        self.ports = self._runner.ports

    def run(self, request: ExecutionRequest) -> ExecutionResult:
        return self._runner.run(request)

    def shadow_compare(
        self,
        request: ExecutionRequest,
        *,
        legacy_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Observe-only dual-run (Phase 3).

        When legacy_payload is provided, compare Appendix A keys vs EM shadow run.
        When omitted, still run EM in shadow mode and return a wired observe meta
        (parity deferred — no legacy peer). Never writes CM. Never replaces primary.
        """
        from src.execution_manager.shadow import (
            ShadowCompareResult,
            project_em_result,
            shadow_compare as _shadow_compare,
        )

        shadow_req = ExecutionRequest(
            run_id=request.run_id,
            pipeline_id=request.pipeline_id,
            session_id=request.session_id,
            mode=ExecutionMode.SHADOW,
            entities=dict(request.entities or {}),
            flags=dict(request.flags or {}),
            budget_token=request.budget_token,
            read_projections=request.read_projections,
            timeout_ms=request.timeout_ms,
            trace_parent=request.trace_parent,
        )
        pipeline_id = str(shadow_req.normalized_pipeline_id().value)

        if legacy_payload is None:
            try:
                em_result = self.run(shadow_req)
                meta = ShadowCompareResult(
                    run_id=shadow_req.run_id,
                    pipeline_id=pipeline_id,
                    parity=False,
                    soft_noise_diffs=[
                        {
                            "key": "legacy_payload",
                            "legacy": None,
                            "em": "present",
                            "class": "no_legacy_peer",
                        }
                    ],
                    cm_eligibility="NO",
                    shadow_only=True,
                    primary_replaced=False,
                    wired=True,
                    stub=False,
                    em_result=em_result,
                    em_projection=project_em_result(em_result),
                )
                emit(
                    "em.shadow.diff",
                    run_id=shadow_req.run_id,
                    pipeline_id=pipeline_id,
                    wired=True,
                    no_legacy_peer=True,
                    cm_eligibility="NO",
                    shadow_only=True,
                )
                return meta.as_dict()
            except Exception as exc:
                emit(
                    "em.shadow.diff",
                    run_id=shadow_req.run_id,
                    fail_open=True,
                    shadow_error=str(exc),
                    cm_eligibility="NO",
                )
                return ShadowCompareResult(
                    run_id=shadow_req.run_id,
                    pipeline_id=pipeline_id,
                    parity=False,
                    shadow_error=f"{type(exc).__name__}: {exc}",
                    fail_open=True,
                    cm_eligibility="NO",
                    shadow_only=True,
                    primary_replaced=False,
                    wired=True,
                ).as_dict()

        result = _shadow_compare(
            pipeline_id=pipeline_id,
            legacy_payload=legacy_payload,
            session_id=shadow_req.session_id,
            entities=shadow_req.entities,
            flags=shadow_req.flags,
            run_id=shadow_req.run_id,
            ports=self.ports,
            em=self,
        )
        return result.as_dict()
