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
        from src.execution_manager.flags import (
            em_pipeline_may_route,
            thin_pipeline_extraction_enabled,
        )

        extraction_on = thin_pipeline_extraction_enabled(pipeline_id)
        if not em_pipeline_may_route(extraction_on, session_id):
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
    Analyze / live_team are NOT gated here (analyze = Stage 3).
    Match-card attachment is the caller's responsibility (Router).
    """
    try:
        from src.execution_manager.flags import (
            em_pipeline_may_route,
            live_pipeline_extraction_enabled,
        )

        if not em_pipeline_may_route(live_pipeline_extraction_enabled(), session_id):
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


def em_analyze_from_fixture(
    data: dict[str, Any],
    *,
    home: str = "",
    away: str = "",
    prefer_live: bool = False,
    force_refresh: bool = False,
    session_id: str = "",
    entities: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Sync EM analyze run with a prefetched analyze_fixture payload.

    Returns payload dict on success, or None for fail-open caller fallback.
    Does NOT attach match cards (Router post-EM). Does NOT write CM.
    """
    from src.execution_manager.contracts import (
        ExecutionMode,
        ExecutionRequest,
        ExecutionStatus,
    )
    from src.execution_manager.ports import PortBundle, PrefetchedFixture
    from src.execution_manager.step_runner import ExecutionManager

    ents = dict(entities or {})
    ents.setdefault("home", home)
    ents.setdefault("away", away)
    em = ExecutionManager(
        ports=PortBundle(fetch_fixture=PrefetchedFixture(response=dict(data or {})))
    )
    result = em.run(
        ExecutionRequest(
            run_id=secrets.token_hex(8),
            pipeline_id="analyze",
            session_id=session_id or "",
            mode=ExecutionMode.PRIMARY,
            entities=ents,
            flags={
                "prefer_live": bool(prefer_live),
                "force_refresh": bool(force_refresh),
                "home": home,
                "away": away,
            },
        )
    )
    if result.status == ExecutionStatus.COMPLETED and isinstance(result.payload, dict):
        out = dict(result.payload)
        # Stash fixture data for Router match-card attach (success path only).
        if result.abort_reason != "integrity_invalid_hard_abort":
            fx = (result.diagnostics or {}).get("analyze_fixture_data")
            if isinstance(fx, dict):
                out["_em_analyze_fixture_data"] = fx
        return out
    logger.warning(
        "copilot: EM analyze incomplete (status=%s)",
        getattr(result.status, "value", result.status),
    )
    return None


async def em_analyze_or_legacy(
    legacy_fn: Callable[[], Awaitable[dict[str, Any]]],
    *,
    home: str,
    away: str,
    prefer_live: bool = False,
    force_refresh: bool = False,
    session_id: str = "",
    entities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Phase 4 Stage 3 — Progressive Extraction E3 (analyze).

    DEFAULT OFF → legacy `_run_analyze`.
    Flag ON → soft-fetch fixture + EM analyze path; fail-open fallback to legacy.
    Soft-try / post-integrity / CM eligibility remain the caller's job (§4.6–§4.7).
    Match-card attachment is the caller's responsibility (Router).
    """
    try:
        from src.execution_manager.flags import (
            analyze_pipeline_extraction_enabled,
            em_pipeline_may_route,
        )

        if not em_pipeline_may_route(analyze_pipeline_extraction_enabled(), session_id):
            return await legacy_fn()

        from src.routers.analyze import analyze_fixture

        data = await analyze_fixture(
            home=home,
            away=away,
            prefer_live=bool(prefer_live),
            soft=True,
            force_refresh=bool(force_refresh),
        )
        payload = em_analyze_from_fixture(
            data if isinstance(data, dict) else {},
            home=home,
            away=away,
            prefer_live=prefer_live,
            force_refresh=force_refresh,
            session_id=session_id,
            entities=entities,
        )
        if payload is not None:
            return payload
        logger.warning("copilot: EM analyze incomplete — fallback legacy")
        return await legacy_fn()
    except Exception as exc:
        logger.warning("copilot: EM analyze failed (%s) — fallback legacy", exc)
        return await legacy_fn()


def em_live_team_from_feed(
    feed: dict[str, Any],
    *,
    team: str = "",
    fixture_data: dict[str, Any] | None = None,
    force_refresh: bool = False,
    session_id: str = "",
    entities: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Sync EM live_team_analyze run with a prefetched live feed (+ optional fixture).

    Returns payload dict on success, or None for fail-open caller fallback.
    Does NOT attach match cards. Does NOT write CM.
    """
    from src.execution_manager.contracts import (
        ExecutionMode,
        ExecutionRequest,
        ExecutionStatus,
    )
    from src.execution_manager.ports import (
        PortBundle,
        PrefetchedFixture,
        PrefetchedLiveFeed,
    )
    from src.execution_manager.step_runner import ExecutionManager

    ents = dict(entities or {})
    if team:
        ents.setdefault("team", team)
    ports_kwargs: dict[str, Any] = {
        "fetch_live_feed": PrefetchedLiveFeed(response=dict(feed or {})),
    }
    if isinstance(fixture_data, dict):
        ports_kwargs["fetch_fixture"] = PrefetchedFixture(response=dict(fixture_data))
    em = ExecutionManager(ports=PortBundle(**ports_kwargs))
    result = em.run(
        ExecutionRequest(
            run_id=secrets.token_hex(8),
            pipeline_id="live_team_analyze",
            session_id=session_id or "",
            mode=ExecutionMode.PRIMARY,
            entities=ents,
            flags={
                "prefer_live": True,
                "force_refresh": bool(force_refresh),
                "team": team,
            },
        )
    )
    if result.status == ExecutionStatus.COMPLETED and isinstance(result.payload, dict):
        out = dict(result.payload)
        diag = result.diagnostics or {}
        if diag.get("matched"):
            out["_em_live_team_home"] = diag.get("home") or ""
            out["_em_live_team_away"] = diag.get("away") or ""
            fx = diag.get("analyze_fixture_data")
            if isinstance(fx, dict) and result.abort_reason != "integrity_invalid_hard_abort":
                out["_em_analyze_fixture_data"] = fx
        return out
    logger.warning(
        "copilot: EM live_team incomplete (status=%s)",
        getattr(result.status, "value", result.status),
    )
    return None


async def em_live_team_or_legacy(
    legacy_fn: Callable[[], Awaitable[dict[str, Any]]],
    *,
    team: str = "",
    force_refresh: bool = False,
    session_id: str = "",
    entities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Phase 4 Stage 4 — Progressive Extraction E4 (live_team_analyze).

    DEFAULT OFF → legacy live_team bridge body.
    Flag ON → prefetch live feed (+ soft fixture when matched) + EM composite;
    fail-open fallback to legacy.
    Post-integrity / CM eligibility remain the caller's job (§4.6–§4.7).
    Match-card attachment is the caller's responsibility (Router).
    """
    try:
        from src.execution_manager.flags import (
            em_pipeline_may_route,
            live_team_pipeline_extraction_enabled,
        )

        if not em_pipeline_may_route(
            live_team_pipeline_extraction_enabled(), session_id
        ):
            return await legacy_fn()

        from src.execution_manager.pipelines.live_team_analyze import (
            match_team_in_live_feed,
        )
        from src.routers.live import _build_live_response

        feed = await _build_live_response()
        feed_dict = feed if isinstance(feed, dict) else {"matches": []}
        home, away = match_team_in_live_feed(team, feed_dict)
        fixture_data: dict[str, Any] | None = None
        if home and away:
            from src.routers.analyze import analyze_fixture

            fixture_data = await analyze_fixture(
                home=home,
                away=away,
                prefer_live=True,
                soft=True,
                force_refresh=bool(force_refresh),
            )
            if not isinstance(fixture_data, dict):
                fixture_data = {}

        payload = em_live_team_from_feed(
            feed_dict,
            team=team,
            fixture_data=fixture_data,
            force_refresh=force_refresh,
            session_id=session_id,
            entities=entities,
        )
        if payload is not None:
            return payload
        logger.warning("copilot: EM live_team incomplete — fallback legacy")
        return await legacy_fn()
    except Exception as exc:
        logger.warning("copilot: EM live_team failed (%s) — fallback legacy", exc)
        return await legacy_fn()
