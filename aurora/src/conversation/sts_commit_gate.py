"""
Mission 016 Phase 2 — STS Commit Gate stages 1–5 (C7 scaffolding).

Spec §10.3 numbered stages. Invoked only from legal Commit Host (C17 in P3;
C1 LangGraph in P4). Stage 4/5 side-effects are planned but NOT executed
against live ctx while production write / funnel flags remain OFF.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from src.conversation.sport_topic_state import SportTopicState
from src.conversation.sts_checkpoint import (
    CheckpointRecord,
    InMemoryCheckpointStore,
    build_checkpoint,
    get_checkpoint_store,
)

CommitEventKind = Literal[
    "boundary_clear_replace",
    "keep_followup",
    "replace_subject",
    "noop",
]


@dataclass
class CommitEvent:
    kind: CommitEventKind
    reason: str = ""
    teams: list[str] = field(default_factory=list)
    fixture: str | None = None
    topic: str | None = None
    subject: str | None = None
    date_context: str | None = None
    followup_stamp: dict[str, Any] = field(default_factory=dict)
    require_os_scg: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CommitGateResult:
    ok: bool
    stage_completed: int
    sts: SportTopicState
    projection_plan: dict[str, Any] = field(default_factory=dict)
    subject_generation: int = 0
    stage5_os_scg_incomplete: bool = False
    checkpoint: CheckpointRecord | None = None
    errors: list[str] = field(default_factory=list)
    write_through_applied: bool = False  # always False while flags OFF

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "stage_completed": self.stage_completed,
            "sts": self.sts.to_dict(),
            "projection_plan": self.projection_plan,
            "subject_generation": self.subject_generation,
            "stage5_os_scg_incomplete": self.stage5_os_scg_incomplete,
            "checkpoint": self.checkpoint.to_dict() if self.checkpoint else None,
            "errors": list(self.errors),
            "write_through_applied": self.write_through_applied,
        }


def _validate_events(events: list[CommitEvent]) -> list[str]:
    errors: list[str] = []
    if not events:
        errors.append("empty_events")
        return errors
    for ev in events:
        if ev.kind == "boundary_clear_replace":
            # Boundary may seed empty (degrade clear) or with teams/fixture.
            continue
        if ev.kind == "replace_subject":
            if not (ev.teams or ev.fixture or ev.subject):
                errors.append("replace_subject_missing_payload")
        if ev.kind not in {
            "boundary_clear_replace",
            "keep_followup",
            "replace_subject",
            "noop",
        }:
            errors.append(f"unknown_event_kind:{ev.kind}")
    return errors


def _apply_event_in_memory(sts: SportTopicState, ev: CommitEvent) -> None:
    if ev.kind == "noop":
        return
    if ev.kind == "boundary_clear_replace":
        sts.clear_for_new_episode(
            reason=ev.reason or "new_episode",
            seed_teams=list(ev.teams or []),
            seed_fixture=ev.fixture,
        )
        return
    if ev.kind == "keep_followup":
        fu = dict(sts.followup_context or {})
        fu.update(dict(ev.followup_stamp or {}))
        fu["last_soft_reason"] = ev.reason or fu.get("last_soft_reason")
        fu["armed"] = True
        sts.followup_context = fu
        sts.boundary_reason = ev.reason or sts.boundary_reason
        return
    if ev.kind == "replace_subject":
        sts.replace_subject(
            teams=list(ev.teams) if ev.teams else None,
            fixture=ev.fixture,
            topic=ev.topic,
            subject=ev.subject,
            date_context=ev.date_context,
            keep_episode=True,
        )
        sts.boundary_reason = ev.reason or sts.boundary_reason


def build_projection_plan(sts: SportTopicState) -> dict[str, Any]:
    """Lean projection plan for Stage 4 (not applied while writes OFF)."""
    teams = list(sts.teams or [])
    home = teams[0] if teams else None
    away = teams[1] if len(teams) > 1 else None
    gen = int(getattr(sts, "subject_generation", 0) or 0)
    return {
        "subject_generation": gen,
        "keys": {
            "last_home": home,
            "last_away": away,
            "last_match": sts.fixture,
            "last_fixture": sts.fixture,
            "episode_id": sts.episode_id,
            "csl.teams": teams,
            "csl.fixture": sts.fixture,
            "csl.episode_id": sts.episode_id,
        },
    }


def run_commit_gate(
    sts: SportTopicState,
    events: list[CommitEvent],
    *,
    thread_id: str | None = None,
    persist: bool = False,
    apply_projections: bool = False,
    run_os_scg: bool = False,
    store: InMemoryCheckpointStore | None = None,
) -> CommitGateResult:
    """
    Execute Commit Gate stages 1–5 contract.

    Defaults: persist/apply_projections/run_os_scg = False (Phase 2 scaffolding).
    When persist=True, Stage 3 writes to in-memory checkpoint store only —
    still not a production live-ctx write.
    """
    working = SportTopicState.from_dict(sts.to_dict())

    # Stage 1 — validate
    errors = _validate_events(events)
    if errors:
        return CommitGateResult(
            ok=False,
            stage_completed=0,
            sts=working,
            errors=errors,
        )

    # Stage 2 — mutate in-memory + bump subject_generation
    for ev in events:
        if ev.kind != "noop":
            _apply_event_in_memory(working, ev)
    # Bump generation once per successful Stage-2 commit unit
    if any(ev.kind != "noop" for ev in events):
        working.bump_subject_generation()

    plan = build_projection_plan(working)
    stage = 2
    checkpoint: CheckpointRecord | None = None

    # Stage 3 — checkpoint persist (optional in Phase 2)
    if persist and thread_id:
        checkpoint = build_checkpoint(thread_id, working, projection_plan=plan)
        store = store or get_checkpoint_store()
        checkpoint = store.save(checkpoint)
        stage = 3
    elif persist and not thread_id:
        return CommitGateResult(
            ok=False,
            stage_completed=2,
            sts=working,
            projection_plan=plan,
            subject_generation=working.subject_generation,
            errors=["persist_requires_thread_id"],
        )

    # Stage 4 — projection write-through (OFF in Phase 2)
    write_through = False
    if apply_projections:
        # Explicitly not mutating live ctx in Phase 2 even if asked —
        # require future funnel flag. Record plan only.
        write_through = False
        stage = max(stage, 4)

    # Stage 5 — OS/SCG required side-effects (scaffolding; D2 incomplete if forced)
    stage5_incomplete = False
    needs_os = any(ev.require_os_scg or ev.kind == "boundary_clear_replace" for ev in events)
    if run_os_scg and needs_os:
        # Phase 2: do not call OS/SCG — mark incomplete if caller forced run
        stage5_incomplete = True
        stage = 5
    elif needs_os and not run_os_scg:
        # Stages planned; OS/SCG deferred — not incomplete unless production write
        stage = max(stage, 3 if persist else 2)

    return CommitGateResult(
        ok=not stage5_incomplete,
        stage_completed=stage,
        sts=working,
        projection_plan=plan,
        subject_generation=int(working.subject_generation),
        stage5_os_scg_incomplete=stage5_incomplete,
        checkpoint=checkpoint,
        write_through_applied=write_through,
    )
