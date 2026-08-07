"""
Router-facing Progressive Extraction shims (Phase 4).

Kept outside copilot_unified_router imports so harnesses can exercise the
shim without FastAPI. Router calls these helpers; legacy bodies stay in Router.
"""

from __future__ import annotations

import logging
import secrets
from typing import Any, Callable

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
