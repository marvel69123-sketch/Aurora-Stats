"""Pipeline handlers package (Phase 2 stubs + Phase 4 Stage 1–4 extractions)."""

from __future__ import annotations

from src.execution_manager.pipelines.analyze import run_analyze, run_analyze_stub
from src.execution_manager.pipelines.live import run_live, run_live_stub
from src.execution_manager.pipelines.live_team_analyze import (
    run_live_team_analyze,
    run_live_team_analyze_stub,
)
from src.execution_manager.pipelines.thin_reports import (
    run_bankroll,
    run_bankroll_stub,
    run_knowledge,
    run_knowledge_stub,
    run_learning,
    run_learning_stub,
)

__all__ = [
    "run_analyze",
    "run_analyze_stub",
    "run_bankroll",
    "run_bankroll_stub",
    "run_knowledge",
    "run_knowledge_stub",
    "run_learning",
    "run_learning_stub",
    "run_live",
    "run_live_stub",
    "run_live_team_analyze",
    "run_live_team_analyze_stub",
]
