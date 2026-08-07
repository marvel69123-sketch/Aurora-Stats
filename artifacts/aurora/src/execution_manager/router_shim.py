"""
Router-facing Progressive Extraction shims (Phase 4).

Kept outside copilot_unified_router imports so harnesses can exercise the
shim without FastAPI. Router calls these helpers; legacy bodies stay in Router.
Match-card attachment is Router-only (never imported here).
"""

from __future__ import annotations

import logging
import secrets
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


def em_thin_or_legacy(
    pipeline_id: str,
    legacy_fn: Callable[[], dict[str, Any]],
    *,
    entities: dict[str, Any] | None = None,
    session_id: str = "",
) -> dict[str, Any]:
    """
    Phase 4 Stage 1 — Progressive Extraction E1 (thin reports).

    DEFAULT OFF → legacy `_run_bankroll` / `_run_learning` / `_run_knowledge`.
    Flag ON → EM thin path; fail-open fallback to legacy.
    Live / analyze / live_team are NOT gated here.
    """
    try:
        from src.execution_manager.flags import thin_pipeline_extraction_enabled

        if not thin_pipeline_extraction_enabled(pipeline_id):
            return legacy_fn()

        from src.execution_manager.contracts import (
            ExecutionMode,
            ExecutionRequest,
            ExecutionStatus,
        )
        from src.execution_manager.ports import PortBundle, ProductionDbReadPort
        from src.execution_manager.step_runner import ExecutionManager

        em = ExecutionManager(ports=PortBundle(db=ProductionDbReadPort()))
        result = em.run(
            ExecutionRequest(
                run_id=secrets.token_hex(8),
                pipeline_id=pipeline_id,
                session_id=session_id or "",
                mode=ExecutionMode.PRIMARY,
                entities=dict(entities or {}),
            )
        )
        if result.status == ExecutionStatus.COMPLETED and isinstance(result.payload, dict):
            return result.payload
        logger.warning(
            "copilot: EM thin %s incomplete (status=%s) — fallback legacy",
            pipeline_id,
            getattr(result.status, "value", result.status),
        )
        return legacy_fn()
    except Exception as exc:
        logger.warning(
            "copilot: EM thin %s failed (%s) — fallback legacy",
            pipeline_id,
            exc,
        )
        return legacy_fn()


def em_live_from_feed(
    feed: dict[str, Any],
    *,
    session_id: str = "",
    entities: dict[str, Any] | None = None,
    flags: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Sync EM live run with a prefetched feed (async shim / harness).

    Returns payload dict on success, or None for fail-open caller fallback.
    Does NOT attach match cards (Router post-EM).
    """
    from src.execution_manager.contracts import (
        ExecutionMode,
        ExecutionRequest,
        ExecutionStatus,
    )
    from src.execution_manager.ports import (
        PortBundle,
        PrefetchedLiveFeed,
        ProductionLiveEnginePort,
    )
    from src.execution_manager.step_runner import ExecutionManager

    em = ExecutionManager(
        ports=PortBundle(
            fetch_live_feed=PrefetchedLiveFeed(response=dict(feed or {})),
            engine=ProductionLiveEnginePort(),
        )
    )
    result = em.run(
        ExecutionRequest(
            run_id=secrets.token_hex(8),
            pipeline_id="live",
            session_id=session_id or "",
            mode=ExecutionMode.PRIMARY,
            entities=dict(entities or {}),
            flags=dict(flags or {}),
        )
    )
    if result.status == ExecutionStatus.COMPLETED and isinstance(result.payload, dict):
        return result.payload
    logger.warning(
        "copilot: EM live incomplete (status=%s)",
        getattr(result.status, "value", result.status),
    )
    return None


async def em_live_or_legacy(
    legacy_fn: Callable[[], Awaitable[dict[str, Any]]],
    *,
    entities: dict[str, Any] | None = None,
    session_id: str = "",
) -> dict[str, Any]:
    """
    Phase 4 Stage 2 — Progressive Extraction E2 (live).

    DEFAULT OFF → legacy `_run_live`.
    Flag ON → prefetch live feed + EM live path; fail-open fallback to legacy.
    Analyze / live_team are NOT gated here.
    Match-card attachment is the caller's responsibility (Router).
    """
    try:
        from src.execution_manager.flags import live_pipeline_extraction_enabled

        if not live_pipeline_extraction_enabled():
            return await legacy_fn()

        from src.routers.live import _build_live_response

        feed = await _build_live_response()
        payload = em_live_from_feed(
            feed if isinstance(feed, dict) else {"matches": []},
            session_id=session_id,
            entities=entities,
        )
        if payload is not None:
            fixtures = []
            if isinstance(feed, dict):
                fixtures = list(feed.get("matches") or [])
            payload = dict(payload)
            payload["_em_live_fixtures"] = fixtures
            return payload
        logger.warning("copilot: EM live incomplete — fallback legacy")
        return await legacy_fn()
    except Exception as exc:
        logger.warning("copilot: EM live failed (%s) — fallback legacy", exc)
        return await legacy_fn()
