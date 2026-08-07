"""
Mission 016 Phase 2 — C17 Minimal Commit Orchestrator (P3 Commit Host).

Phase 4 Sole-Writer Funnel may authorize invoke via S2_FUNNEL / funnel stage
(REGRA 24) in addition to force=True. Production LangGraph write (P4 host / C1)
remains OFF; when ENABLE_LANGGRAPH_STATE is ON, C17 skips (no dual host).

Same semantic edges as P4 LangGraph host:
  init_load → classify → {apply_boundary|keep_followup|apply_subject} → Commit Gate
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.conversation.episode_transition import (
    EpisodeTransition,
    EpisodeTransitionDecision,
    select_apply_node,
)
from src.conversation.migration_flag_controller import (
    get_migration_stage,
    production_write_active,
    sts_funnel_boundary_enabled,
)
from src.conversation.sport_topic_state import (
    SportTopicState,
    langgraph_state_enabled,
)
from src.conversation.sts_checkpoint import (
    get_checkpoint_store,
    hydrate_sts_from_checkpoint,
)
from src.conversation.sts_commit_gate import (
    CommitEvent,
    CommitGateResult,
    run_commit_gate,
)
from src.conversation.thread_identity import (
    SessionIdentityError,
    map_session_to_thread_id,
)
from src.conversation.topic_boundary_v2 import (
    current_message_entities,
    extract_fixture_phrase,
)

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorResult:
    sts: SportTopicState
    decision: EpisodeTransitionDecision | None = None
    apply_node: str | None = None
    commit: CommitGateResult | None = None
    thread_id: str | None = None
    skipped: bool = False
    skipped_reason: str | None = None
    hydrate_meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sts": self.sts.to_dict(),
            "decision": self.decision.to_dict() if self.decision else None,
            "apply_node": self.apply_node,
            "commit": self.commit.to_dict() if self.commit else None,
            "thread_id": self.thread_id,
            "skipped": self.skipped,
            "skipped_reason": self.skipped_reason,
            "hydrate_meta": self.hydrate_meta,
            "migration_stage": get_migration_stage().value,
            "production_write_active": production_write_active(),
        }


def _events_for_node(
    node: str,
    decision: EpisodeTransitionDecision,
    message: str,
) -> list[CommitEvent]:
    clubs = list((decision.current_entities or {}).get("clubs") or [])
    fx = (decision.current_entities or {}).get("fixture_label")
    if not clubs:
        clubs = current_message_entities(message or "", None)
    if not fx:
        fx = extract_fixture_phrase(message or "")

    if node == "apply_boundary":
        return [
            CommitEvent(
                kind="boundary_clear_replace",
                reason=decision.reason,
                teams=list(clubs or []),
                fixture=fx if isinstance(fx, str) else None,
                require_os_scg=True,
            )
        ]
    if node == "keep_followup":
        return [
            CommitEvent(
                kind="keep_followup",
                reason=decision.reason or "soft_followup_same_episode",
                followup_stamp={"armed": True},
            )
        ]
    # apply_subject
    teams = list(clubs or [])
    fixture = fx if isinstance(fx, str) else None
    if not fixture and len(teams) >= 2:
        fixture = f"{teams[0]} x {teams[1]}"
    topic = "comparison" if len(teams) >= 2 else ("calendar" if teams else None)
    return [
        CommitEvent(
            kind="replace_subject",
            reason=decision.reason or "apply_subject",
            teams=teams,
            fixture=fixture,
            topic=topic,
            subject=fixture or (teams[0] if teams else None),
        )
    ]


def init_load(
    *,
    thread_id: str | None = None,
    sts: SportTopicState | dict[str, Any] | None = None,
    hydrate_from_checkpoint: bool = False,
) -> tuple[SportTopicState, dict[str, Any]]:
    """Edge: init_load — hydrate STS from arg or checkpoint (cold empty on miss)."""
    meta: dict[str, Any] = {}
    if hydrate_from_checkpoint and thread_id:
        loaded, meta = hydrate_sts_from_checkpoint(thread_id, get_checkpoint_store())
        if sts is None:
            return loaded, meta
    if isinstance(sts, SportTopicState):
        return SportTopicState.from_dict(sts.to_dict()), meta
    if isinstance(sts, dict):
        return SportTopicState.from_dict(sts), meta
    return SportTopicState(), meta


def classify(message: str, sts: SportTopicState) -> EpisodeTransitionDecision:
    """Edge: classify — typed EpisodeTransitionDecision (Appendix A consumer)."""
    return EpisodeTransition.decide(message or "", sts)


def invoke_minimal_commit_orchestrator(
    message: str,
    sts: SportTopicState | dict[str, Any] | None = None,
    *,
    session_id: str | None = None,
    thread_id: str | None = None,
    force: bool = False,
    persist_checkpoint: bool = False,
    hydrate_from_checkpoint: bool = False,
) -> OrchestratorResult:
    """
    C17 invoke — same order as LangGraph host.

    Activation gates:
      - Default: skip (no-op) unless force=True OR future funnel stage authorizes.
      - langgraph_state_enabled (P4) does NOT route here; P4 uses C1.
      - Phase 2: production paths must call with flags OFF → skipped unless force.

    Dual-orchestration ban: this is the sole P3 host; do not invent a peer path.
    """
    stage = get_migration_stage()
    # Phase 4: force (tests) OR S2_FUNNEL OR progressive funnel stage-1 boundary.
    funnel_stage1 = False
    try:
        from src.conversation.sole_writer_funnel import get_funnel_pct

        funnel_stage1 = get_funnel_pct() >= 1 and sts_funnel_boundary_enabled()
    except Exception:
        funnel_stage1 = False
    allowed = force or stage.value == "S2_FUNNEL" or funnel_stage1
    # Never allow silent activation via ENABLE_LANGGRAPH_STATE alone (that's C1).
    if langgraph_state_enabled() and not force:
        # P4 write path belongs to LangGraph host — C17 must not dual-commit.
        current = (
            sts
            if isinstance(sts, SportTopicState)
            else SportTopicState.from_dict(sts if isinstance(sts, dict) else None)
        )
        return OrchestratorResult(
            sts=current,
            skipped=True,
            skipped_reason="p4_langgraph_host_owns_write_use_c1",
        )

    if not allowed:
        current = (
            sts
            if isinstance(sts, SportTopicState)
            else SportTopicState.from_dict(sts if isinstance(sts, dict) else None)
        )
        return OrchestratorResult(
            sts=current,
            skipped=True,
            skipped_reason="flags_off_orchestrator_noop",
        )

    tid = thread_id
    if tid is None and session_id is not None:
        try:
            tid = map_session_to_thread_id(session_id)
        except SessionIdentityError as exc:
            current = (
                sts
                if isinstance(sts, SportTopicState)
                else SportTopicState.from_dict(sts if isinstance(sts, dict) else None)
            )
            return OrchestratorResult(
                sts=current,
                skipped=True,
                skipped_reason=f"session_identity:{exc.reason}",
            )

    # 1) init_load
    loaded, hydrate_meta = init_load(
        thread_id=tid,
        sts=sts,
        hydrate_from_checkpoint=hydrate_from_checkpoint,
    )

    # 2) classify
    decision = classify(message or "", loaded)

    # 3) Appendix A route
    node = select_apply_node(decision)

    # 4) pending events → Commit Gate stages
    events = _events_for_node(node, decision, message or "")
    commit = run_commit_gate(
        loaded,
        events,
        thread_id=tid,
        persist=bool(persist_checkpoint and tid),
        apply_projections=False,
        run_os_scg=False,
    )

    return OrchestratorResult(
        sts=commit.sts,
        decision=decision,
        apply_node=node,
        commit=commit,
        thread_id=tid,
        skipped=False,
        hydrate_meta=hydrate_meta,
    )


# Alias matching Spec naming
MinimalCommitOrchestrator = invoke_minimal_commit_orchestrator
