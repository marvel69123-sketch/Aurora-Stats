"""
Execution Manager — Phase 3 Shadow Mode (observe-only).

Dual-run compare vs legacy unified `_run_*` payloads.
Fail-open. Never replaces primary. Never writes CM / ctx / memory.
Gated by ENABLE_EXECUTION_MANAGER_SHADOW (default OFF).
"""

from __future__ import annotations

import copy
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from src.execution_manager.contracts import (
    ANALYZE_FROZEN_ENGINE_ORDER,
    ExecutionMode,
    ExecutionRequest,
    ExecutionResult,
    PipelineId,
)
from src.execution_manager.flags import shadow_enabled
from src.execution_manager.observability import emit
from src.execution_manager.ports import PortBundle

# Spec Appendix A (CDR-M-004) — mandatory compare classes / keys.
APPENDIX_A_MANDATORY_KEYS: tuple[str, ...] = (
    "pipeline_id",
    "status",
    "abort_reason",
    "fixture_quality",
    "entity_invalid",
    "markets_blocked",
    "best_markets",
    "step_traces_engine_order",
    "a2_soft_skip_reason",
    "fixture_id",
)

# Noise allowlist — compare-tolerant (Plan §10 / Spec Appendix A).
NOISE_ALLOWLIST: frozenset[str] = frozenset(
    {
        "timestamps",
        "drs_stamp_churn",
        "non_semantic_narrative_whitespace",
        "executive_summary",
        "aurora_version",
        "brain",
        "response_metadata",
        "_audit",
        "diagnostics",
        "stub",
    }
)

# Intent → EM pipeline (unified router only — never copilot_engine).
INTENT_TO_PIPELINE: dict[str, str] = {
    "analyze_match": PipelineId.ANALYZE.value,
    "live_opportunities": PipelineId.LIVE.value,
    "bankroll_review": PipelineId.BANKROLL.value,
    "learning_recap": PipelineId.LEARNING.value,
    "knowledge_search": PipelineId.KNOWLEDGE.value,
    "live_team_analysis": PipelineId.LIVE_TEAM_ANALYZE.value,
}

_SHADOW_METRICS: dict[str, Any] = {
    "runs_shadowed": 0,
    "parity_hits": 0,
    "hard_diff_counts": 0,
    "soft_noise_diff_counts": 0,
    "shadow_errors": 0,
    "fail_open_count": 0,
    "per_pipeline": {},
    "latency_ms_sum": 0.0,
    "latency_ms_count": 0,
}


def reset_shadow_metrics() -> None:
    _SHADOW_METRICS.update(
        {
            "runs_shadowed": 0,
            "parity_hits": 0,
            "hard_diff_counts": 0,
            "soft_noise_diff_counts": 0,
            "shadow_errors": 0,
            "fail_open_count": 0,
            "per_pipeline": {},
            "latency_ms_sum": 0.0,
            "latency_ms_count": 0,
        }
    )


def shadow_metrics_snapshot() -> dict[str, Any]:
    snap = dict(_SHADOW_METRICS)
    snap["per_pipeline"] = {
        k: dict(v) for k, v in (_SHADOW_METRICS.get("per_pipeline") or {}).items()
    }
    n = int(snap.get("latency_ms_count") or 0)
    snap["latency_ms_avg"] = (
        float(snap["latency_ms_sum"]) / n if n > 0 else 0.0
    )
    runs = int(snap.get("runs_shadowed") or 0)
    hits = int(snap.get("parity_hits") or 0)
    snap["parity_rate"] = (hits / runs) if runs > 0 else None
    return snap


def _bump_pipeline(pipeline_id: str, field_name: str) -> None:
    per = _SHADOW_METRICS.setdefault("per_pipeline", {})
    bucket = per.setdefault(
        pipeline_id,
        {"runs": 0, "parity": 0, "hard_diffs": 0, "errors": 0},
    )
    bucket[field_name] = int(bucket.get(field_name) or 0) + 1


@dataclass
class ShadowCompareResult:
    """Observe-only dual-run outcome — never a production response substitute."""

    run_id: str
    pipeline_id: str
    parity: bool
    hard_diffs: list[dict[str, Any]] = field(default_factory=list)
    soft_noise_diffs: list[dict[str, Any]] = field(default_factory=list)
    shadow_error: str | None = None
    fail_open: bool = False
    cm_eligibility: str = "NO"  # Spec §4.7 / §11 — always NO in shadow
    shadow_only: bool = True
    primary_replaced: bool = False
    wired: bool = True
    stub: bool = False
    em_result: ExecutionResult | None = None
    legacy_projection: dict[str, Any] = field(default_factory=dict)
    em_projection: dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    metrics: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "pipeline_id": self.pipeline_id,
            "parity": self.parity,
            "hard_diffs": list(self.hard_diffs),
            "soft_noise_diffs": list(self.soft_noise_diffs),
            "shadow_error": self.shadow_error,
            "fail_open": self.fail_open,
            "cm_eligibility": self.cm_eligibility,
            "shadow_only": self.shadow_only,
            "primary_replaced": self.primary_replaced,
            "wired": self.wired,
            "stub": self.stub,
            "latency_ms": self.latency_ms,
            "metrics": dict(self.metrics),
            "legacy_projection": dict(self.legacy_projection),
            "em_projection": dict(self.em_projection),
        }


def resolve_pipeline_id(
    pipeline_id: str | PipelineId | None = None,
    *,
    intent: str | None = None,
) -> str | None:
    if isinstance(pipeline_id, PipelineId):
        return pipeline_id.value
    if pipeline_id:
        return str(pipeline_id)
    if intent and intent in INTENT_TO_PIPELINE:
        return INTENT_TO_PIPELINE[intent]
    return None


def project_legacy_payload(
    pipeline_id: str,
    legacy_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    """Map unified `_run_*` / orchestration payload → Appendix A compare view."""
    payload = dict(legacy_payload or {})
    ents = dict(payload.get("entities") or {})
    fixture_quality = payload.get("fixture_quality") or ents.get("fixture_quality")
    entity_invalid = ents.get("entity_invalid")
    if entity_invalid is None:
        entity_invalid = payload.get("entity_invalid")
    markets_blocked = ents.get("markets_blocked")
    if markets_blocked is None:
        markets_blocked = payload.get("markets_blocked")
    abort_reason = payload.get("abort_reason")
    if not abort_reason and (
        fixture_quality == "INVALID"
        or entity_invalid is True
        or payload.get("status") == "blocked"
    ):
        abort_reason = "integrity_invalid_hard_abort"

    # Legacy unified path does not always expose EM step_traces; leave None
    # so compare treats missing-vs-present as soft until Phase 4 extraction.
    step_order = payload.get("step_traces_engine_order")
    if step_order is None and isinstance(payload.get("engines_run"), list):
        step_order = list(payload["engines_run"])

    a2_reason = payload.get("a2_soft_skip_reason") or ents.get("a2_soft_skip_reason")
    if a2_reason is None and fixture_quality == "VALID_LOCATED":
        a2_reason = "integrity_soft_skip_fixture_located"

    status = payload.get("em_status") or payload.get("execution_status")
    if not status:
        # HTTP-compatible blocked INVALID is still a completed contract (M-001).
        if payload.get("status") == "blocked" or fixture_quality == "INVALID":
            status = "Completed"
        elif payload.get("error"):
            status = "Failed"
        else:
            status = "Completed"

    fixture_id = payload.get("fixture_id")
    if fixture_id is None:
        fixture_id = ents.get("fixture_id")

    return {
        "pipeline_id": pipeline_id,
        "status": status,
        "abort_reason": abort_reason,
        "fixture_quality": fixture_quality,
        "entity_invalid": entity_invalid,
        "markets_blocked": markets_blocked,
        "best_markets": _market_ids(payload.get("best_markets")),
        "step_traces_engine_order": step_order,
        "a2_soft_skip_reason": a2_reason,
        "fixture_id": int(fixture_id or 0) or None,
    }


def project_em_result(result: ExecutionResult) -> dict[str, Any]:
    """Map ExecutionResult → Appendix A compare view."""
    payload = dict(result.payload or {})
    ents = dict(payload.get("entities") or {})
    engine_order = [
        t.step_id
        for t in (result.step_traces or [])
        if t.step_id in ANALYZE_FROZEN_ENGINE_ORDER
    ]
    a2 = next(
        (t for t in (result.step_traces or []) if t.step_id == "integrity_gate"),
        None,
    )
    a2_reason = None
    if a2 is not None and a2.status.value == "skipped":
        a2_reason = a2.reason

    fixture_id = payload.get("fixture_id") or ents.get("fixture_id")
    return {
        "pipeline_id": str(result.pipeline_id),
        "status": result.status.value if hasattr(result.status, "value") else str(result.status),
        "abort_reason": result.abort_reason,
        "fixture_quality": result.fixture_quality or payload.get("fixture_quality"),
        "entity_invalid": ents.get("entity_invalid"),
        "markets_blocked": ents.get("markets_blocked"),
        "best_markets": _market_ids(payload.get("best_markets")),
        "step_traces_engine_order": engine_order or None,
        "a2_soft_skip_reason": a2_reason,
        "fixture_id": int(fixture_id or 0) or None,
    }


def _market_ids(markets: Any) -> list[Any]:
    if not isinstance(markets, list):
        return []
    out: list[Any] = []
    for m in markets:
        if isinstance(m, dict):
            out.append(m.get("id") or m.get("label") or m.get("market") or m)
        else:
            out.append(m)
    return out


def compare_appendix_a(
    legacy_view: dict[str, Any],
    em_view: dict[str, Any],
) -> tuple[bool, list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Compare Appendix A mandatory keys.

    Returns (parity, hard_diffs, soft_noise_diffs).
    Missing engine-order / soft-skip on legacy-only path is soft (noise) until
    Progressive Extraction exposes step_traces on the primary path.
    """
    hard: list[dict[str, Any]] = []
    soft: list[dict[str, Any]] = []

    for key in APPENDIX_A_MANDATORY_KEYS:
        lv = legacy_view.get(key)
        ev = em_view.get(key)
        if lv == ev:
            continue
        # Soft: legacy lacks step_traces / soft-skip while EM stub has them.
        if key in {"step_traces_engine_order", "a2_soft_skip_reason"} and lv is None and ev is not None:
            soft.append({"key": key, "legacy": lv, "em": ev, "class": "noise_or_pending_extraction"})
            continue
        # Soft: thin/live stubs may not populate integrity markers the same way.
        if key in {"entity_invalid", "markets_blocked", "fixture_id", "abort_reason"} and (
            lv is None or ev is None
        ):
            soft.append({"key": key, "legacy": lv, "em": ev, "class": "nullable_presence"})
            continue
        hard.append({"key": key, "legacy": lv, "em": ev, "class": "mandatory"})

    parity = len(hard) == 0
    return parity, hard, soft


def build_shadow_request(
    *,
    pipeline_id: str,
    session_id: str = "",
    entities: dict[str, Any] | None = None,
    flags: dict[str, Any] | None = None,
    run_id: str | None = None,
    legacy_payload: dict[str, Any] | None = None,
) -> ExecutionRequest:
    ents = dict(entities or {})
    payload = dict(legacy_payload or {})
    # Prefer entities already on the legacy payload when caller omitted them.
    for k in ("home", "away", "fixture_id", "fixture_quality", "query", "entity_invalid"):
        if k not in ents and k in (payload.get("entities") or {}):
            ents[k] = (payload.get("entities") or {})[k]
        if k not in ents and k in payload:
            ents[k] = payload[k]
    req_flags = dict(flags or {})
    # Derive integrity hints from legacy for stub parity (observe-only).
    fq = payload.get("fixture_quality") or ents.get("fixture_quality")
    if fq == "INVALID" and int(ents.get("fixture_id") or payload.get("fixture_id") or 0) <= 0:
        req_flags.setdefault("integrity_outcome", "HARD_ABORT")
    elif fq == "INVALID" and int(ents.get("fixture_id") or payload.get("fixture_id") or 0) > 0:
        req_flags.setdefault("named_assess_blocked", True)
    elif fq == "PARTIAL":
        req_flags.setdefault("integrity_outcome", "PARTIAL")
    elif fq in {"VALID", "VALID_LOCATED"}:
        req_flags.setdefault("integrity_outcome", "PASS" if fq == "VALID" else "SOFT_SKIP")
        if fq == "VALID_LOCATED":
            req_flags.setdefault("named_assess_blocked", True)

    return ExecutionRequest(
        run_id=run_id or f"shadow-{uuid.uuid4().hex[:12]}",
        pipeline_id=pipeline_id,
        session_id=session_id or "shadow-session",
        mode=ExecutionMode.SHADOW,
        entities=ents,
        flags=req_flags,
    )


def shadow_compare(
    *,
    pipeline_id: str,
    legacy_payload: dict[str, Any],
    session_id: str = "",
    entities: dict[str, Any] | None = None,
    flags: dict[str, Any] | None = None,
    run_id: str | None = None,
    ports: PortBundle | None = None,
    em: Any | None = None,
) -> ShadowCompareResult:
    """
    Best-effort EM run in mode=shadow + Appendix A compare.

    Never mutates legacy_payload. Never writes CM. Caller keeps primary.
    """
    started = time.perf_counter()
    # Freeze a copy so accidental EM/mutation cannot touch the production dict.
    legacy_frozen = copy.deepcopy(legacy_payload)
    request = build_shadow_request(
        pipeline_id=pipeline_id,
        session_id=session_id,
        entities=entities,
        flags=flags,
        run_id=run_id,
        legacy_payload=legacy_frozen,
    )
    try:
        if em is None:
            from src.execution_manager.step_runner import ExecutionManager

            em = ExecutionManager(ports=ports)
        em_result = em.run(request)
        legacy_view = project_legacy_payload(pipeline_id, legacy_frozen)
        em_view = project_em_result(em_result)
        parity, hard, soft = compare_appendix_a(legacy_view, em_view)
        latency_ms = (time.perf_counter() - started) * 1000.0

        _SHADOW_METRICS["runs_shadowed"] = int(_SHADOW_METRICS["runs_shadowed"]) + 1
        _bump_pipeline(pipeline_id, "runs")
        if parity:
            _SHADOW_METRICS["parity_hits"] = int(_SHADOW_METRICS["parity_hits"]) + 1
            _bump_pipeline(pipeline_id, "parity")
        if hard:
            _SHADOW_METRICS["hard_diff_counts"] = int(_SHADOW_METRICS["hard_diff_counts"]) + len(hard)
            _bump_pipeline(pipeline_id, "hard_diffs")
        if soft:
            _SHADOW_METRICS["soft_noise_diff_counts"] = (
                int(_SHADOW_METRICS["soft_noise_diff_counts"]) + len(soft)
            )
        _SHADOW_METRICS["latency_ms_sum"] = float(_SHADOW_METRICS["latency_ms_sum"]) + latency_ms
        _SHADOW_METRICS["latency_ms_count"] = int(_SHADOW_METRICS["latency_ms_count"]) + 1

        result = ShadowCompareResult(
            run_id=request.run_id,
            pipeline_id=pipeline_id,
            parity=parity,
            hard_diffs=hard,
            soft_noise_diffs=soft,
            cm_eligibility="NO",
            shadow_only=True,
            primary_replaced=False,
            wired=True,
            stub=False,
            em_result=em_result,
            legacy_projection=legacy_view,
            em_projection=em_view,
            latency_ms=latency_ms,
            metrics=shadow_metrics_snapshot(),
        )
        emit(
            "em.shadow.diff",
            run_id=result.run_id,
            pipeline_id=pipeline_id,
            parity=parity,
            hard_diff_count=len(hard),
            soft_noise_diff_count=len(soft),
            cm_eligibility="NO",
            shadow_only=True,
            primary_replaced=False,
            latency_ms=latency_ms,
        )
        return result
    except Exception as exc:  # fail-open
        latency_ms = (time.perf_counter() - started) * 1000.0
        _SHADOW_METRICS["shadow_errors"] = int(_SHADOW_METRICS["shadow_errors"]) + 1
        _SHADOW_METRICS["fail_open_count"] = int(_SHADOW_METRICS["fail_open_count"]) + 1
        _bump_pipeline(pipeline_id, "errors")
        emit(
            "em.shadow.diff",
            run_id=request.run_id,
            pipeline_id=pipeline_id,
            fail_open=True,
            shadow_error=str(exc),
            cm_eligibility="NO",
            shadow_only=True,
            primary_replaced=False,
        )
        return ShadowCompareResult(
            run_id=request.run_id,
            pipeline_id=pipeline_id,
            parity=False,
            shadow_error=f"{type(exc).__name__}: {exc}",
            fail_open=True,
            cm_eligibility="NO",
            shadow_only=True,
            primary_replaced=False,
            wired=True,
            latency_ms=latency_ms,
            metrics=shadow_metrics_snapshot(),
        )


def maybe_em_shadow_observe(
    *,
    legacy_payload: dict[str, Any] | None,
    pipeline_id: str | PipelineId | None = None,
    intent: str | None = None,
    session_id: str = "",
    entities: dict[str, Any] | None = None,
    flags: dict[str, Any] | None = None,
    force: bool = False,
    ports: PortBundle | None = None,
) -> ShadowCompareResult | None:
    """
    Router / harness entrypoint.

    OFF (default) → None (no-op).
    ON → observe-only dual-run; never returns EM as primary; never mutates
    legacy_payload / ctx (caller must not assign this result to payload).
    Fail-open on any error.
    """
    if not force and not shadow_enabled():
        return None
    if not isinstance(legacy_payload, dict):
        return None
    pid = resolve_pipeline_id(pipeline_id, intent=intent)
    if not pid:
        return None
    # Conversational intents never enter EM — resolve_pipeline_id already filters.
    try:
        # Capture identity + shallow fingerprint to prove no mutation.
        payload_id = id(legacy_payload)
        before_keys = list(legacy_payload.keys())
        before_fq = legacy_payload.get("fixture_quality")
        result = shadow_compare(
            pipeline_id=pid,
            legacy_payload=legacy_payload,
            session_id=session_id,
            entities=entities,
            flags=flags,
            ports=ports,
        )
        # Post-condition: primary dict identity + key set unchanged.
        if id(legacy_payload) != payload_id or list(legacy_payload.keys()) != before_keys:
            result.fail_open = True
            result.shadow_error = (result.shadow_error or "") + "|primary_mutated"
            _SHADOW_METRICS["fail_open_count"] = int(_SHADOW_METRICS["fail_open_count"]) + 1
        if legacy_payload.get("fixture_quality") != before_fq:
            result.fail_open = True
            result.shadow_error = (result.shadow_error or "") + "|fixture_quality_mutated"
        result.primary_replaced = False
        result.cm_eligibility = "NO"
        return result
    except Exception as exc:
        _SHADOW_METRICS["fail_open_count"] = int(_SHADOW_METRICS["fail_open_count"]) + 1
        _SHADOW_METRICS["shadow_errors"] = int(_SHADOW_METRICS["shadow_errors"]) + 1
        emit(
            "em.shadow.diff",
            fail_open=True,
            shadow_error=str(exc),
            cm_eligibility="NO",
            shadow_only=True,
            primary_replaced=False,
        )
        return ShadowCompareResult(
            run_id=f"shadow-failopen-{uuid.uuid4().hex[:8]}",
            pipeline_id=pid,
            parity=False,
            shadow_error=f"{type(exc).__name__}: {exc}",
            fail_open=True,
            cm_eligibility="NO",
            shadow_only=True,
            primary_replaced=False,
            wired=True,
        )


def cm_eligibility_for_shadow() -> str:
    """Spec §4.7 — Shadow path is always NO (never subject write)."""
    return "NO"
