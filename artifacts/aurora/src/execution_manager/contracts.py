"""
EM contracts / DTOs (Spec v1.1 §4 + Plan §3 hygiene).

Inert typed models only — no I/O, no Router coupling, no CM writes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PipelineId(str, Enum):
    ANALYZE = "analyze"
    LIVE = "live"
    BANKROLL = "bankroll"
    LEARNING = "learning"
    KNOWLEDGE = "knowledge"
    LIVE_TEAM_ANALYZE = "live_team_analyze"


class ExecutionMode(str, Enum):
    PRIMARY = "primary"
    SHADOW = "shadow"
    DRY_RUN = "dry_run"


class ExecutionStatus(str, Enum):
    """Closed Result status enum (Spec §4.3) — terminal only."""

    COMPLETED = "Completed"
    FAILED = "Failed"
    INTERRUPTED = "Interrupted"


class FixtureQuality(str, Enum):
    """Closed set Plan §3.2 (CDR2-L-001)."""

    VALID = "VALID"
    PARTIAL = "PARTIAL"
    INVALID = "INVALID"
    VALID_LOCATED = "VALID_LOCATED"


class StepStatus(str, Enum):
    PENDING = "pending"
    STARTED = "started"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"
    TERMINAL_GATE = "terminal_gate"


class AbortReason(str, Enum):
    INTEGRITY_INVALID_HARD_ABORT = "integrity_invalid_hard_abort"


# Frozen A3–A10 engine order snapshot (Spec §5.2 — ARCHITECTURAL DECISION REQUIRED to change).
ANALYZE_FROZEN_ENGINE_ORDER: tuple[str, ...] = (
    "methodology",  # A3
    "learning",  # A4
    "confidence",  # A5
    "market",  # A6
    "methodology_v1",  # A7
    "decision_center",  # A8
    "knowledge_consult",  # A9
    "intelligence",  # A10
)

ANALYZE_STEP_ORDER: tuple[str, ...] = (
    "budget_check",  # A0
    "fetch_fixture",  # A1
    "integrity_gate",  # A2
    *ANALYZE_FROZEN_ENGINE_ORDER,
    "partial_inference_assembly",  # A11
    "structured_payload",  # A12
    "match_card_fields",  # A13
)

LIVE_STEP_ORDER: tuple[str, ...] = (
    "budget_check",  # L0
    "fetch_live_feed",  # L1
    "live_intelligence",  # L2
    "structured_payload",  # L3
    "match_card_fields",  # L4
)

LIVE_TEAM_STEP_ORDER: tuple[str, ...] = (
    "search_live_for_team",  # T0
    "delegate_analyze",  # T1
)

THIN_BANKROLL_STEPS: tuple[str, ...] = (
    "load_learning_stats",
    "assemble_bankroll_payload",
)
THIN_LEARNING_STEPS: tuple[str, ...] = (
    "load_learning_stats",
    "assemble_learning_payload",
)
THIN_KNOWLEDGE_STEPS: tuple[str, ...] = (
    "search_knowledge_items",
    "assemble_knowledge_payload",
)


@dataclass(frozen=True)
class StepTrace:
    step_id: str
    status: StepStatus
    duration_ms: float = 0.0
    reason: str | None = None
    error: str | None = None


@dataclass
class ExecutionRequest:
    run_id: str
    pipeline_id: PipelineId | str
    session_id: str
    mode: ExecutionMode | str = ExecutionMode.PRIMARY
    entities: dict[str, Any] = field(default_factory=dict)
    flags: dict[str, Any] = field(default_factory=dict)
    budget_token: Any | None = None
    read_projections: dict[str, Any] | None = None
    timeout_ms: int | None = None
    trace_parent: str | None = None

    def normalized_pipeline_id(self) -> PipelineId:
        if isinstance(self.pipeline_id, PipelineId):
            return self.pipeline_id
        return PipelineId(str(self.pipeline_id))

    def normalized_mode(self) -> ExecutionMode:
        if isinstance(self.mode, ExecutionMode):
            return self.mode
        return ExecutionMode(str(self.mode))


@dataclass
class ExecutionResult:
    run_id: str
    pipeline_id: str
    status: ExecutionStatus
    payload: dict[str, Any] = field(default_factory=dict)
    step_traces: list[StepTrace] = field(default_factory=list)
    abort_reason: str | None = None
    fixture_quality: str | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)
    shadow_meta: dict[str, Any] | None = None


def blocked_integrity_payload_stub(
    *,
    home: str = "",
    away: str = "",
) -> dict[str, Any]:
    """
    Inert HARD-ABORT payload shape ≡ Phase 1 baseline blocked_integrity contract.

    Does not import fixture_integrity (keeps EM package boundary clean in Infra).
    """
    return {
        "intent": "analyze_match",
        "entities": {
            "home": home,
            "away": away,
            "fixture_status": "NOT_FOUND",
            "fixture_quality": FixtureQuality.INVALID.value,
            "fixture_found": False,
            "entity_invalid": True,
            "markets_blocked": True,
            "market_generation_enabled": False,
            "entity_match_score": 0.0,
        },
        "match": {"home": home, "away": away},
        "status": "blocked",
        "is_live": False,
        "minute": None,
        "fixture_status": "NOT_FOUND",
        "fixture_quality": FixtureQuality.INVALID.value,
        "fixture_found": False,
        "_audit": {"source": "execution_manager.stub", "hard_abort": True},
        "executive_summary": "Análise bloqueada por integridade (HARD-ABORT stub).",
        "best_markets": [],
        "confidence": None,
        "risk": None,
        "bankroll_recommendation": {"no_bet": True},
        "positive_factors": [],
        "negative_factors": [],
        "historical_references": [],
        "knowledge_notes": [],
        "final_recommendation": None,
        "aurora_version": None,
        "brain": None,
        "match_card": None,
        "response_metadata": {"header_blocked": True},
    }
