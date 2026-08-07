"""Pipeline stubs package (Phase 2 — scaffolding only)."""

from __future__ import annotations

from src.execution_manager.pipelines.analyze import run_analyze_stub
from src.execution_manager.pipelines.live import run_live_stub
from src.execution_manager.pipelines.live_team_analyze import run_live_team_analyze_stub
from src.execution_manager.pipelines.thin_reports import (
    run_bankroll_stub,
    run_knowledge_stub,
    run_learning_stub,
)

__all__ = [
    "run_analyze_stub",
    "run_bankroll_stub",
    "run_knowledge_stub",
    "run_learning_stub",
    "run_live_stub",
    "run_live_team_analyze_stub",
]
