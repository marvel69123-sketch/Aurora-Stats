"""
Mission 016 Phase 2 — Typed EpisodeTransitionDecision + Appendix A routing.

KEEP CUSTOM TRANSITION (Spec 004 v1.2 §8.4 / Appendix A). Classify emits a
typed DTO; routing is a pure total function (outcome × reason) → apply node.

Scaffolding only: does not activate production writes or replace TB-V2 apply.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Outcome = Literal["KEEP_EPISODE", "NEW_FIXTURE", "NEW_EPISODE"]
ApplyNode = Literal["apply_boundary", "keep_followup", "apply_subject"]

# Spec §8.4 closed reason set (v1.1/v1.2).
CLOSED_REASONS = frozenset(
    {
        "new_fixture",
        "soft_followup_same_episode",
        "low_entity_overlap",
        "seed_subject",
        "same_fixture_restated",
        "overlap_ok_keep",
        "explicit_new_episode",
    }
)

# Appendix A — (outcome × reason) → apply node (FINDING-013).
APPENDIX_A_ROUTE_TABLE: dict[tuple[str, str], ApplyNode] = {
    ("NEW_FIXTURE", "new_fixture"): "apply_boundary",
    ("NEW_EPISODE", "low_entity_overlap"): "apply_boundary",
    ("NEW_EPISODE", "explicit_new_episode"): "apply_boundary",
    ("KEEP_EPISODE", "soft_followup_same_episode"): "keep_followup",
    ("KEEP_EPISODE", "seed_subject"): "apply_subject",
    ("KEEP_EPISODE", "same_fixture_restated"): "apply_subject",
    ("KEEP_EPISODE", "overlap_ok_keep"): "apply_subject",
}

# POC classify_turn reason tokens → Spec closed reason (normalize before route).
_REASON_NORMALIZE: dict[str, str] = {
    "new_fixture": "new_fixture",
    "new_fixture_no_prior_label": "new_fixture",
    "low_entity_overlap": "low_entity_overlap",
    "explicit_new_episode": "explicit_new_episode",
    "soft_followup_same_episode": "soft_followup_same_episode",
    "soft_team_in_episode": "soft_followup_same_episode",
    "no_current_entities": "soft_followup_same_episode",
    "no_prior_no_entities": "soft_followup_same_episode",
    "seed_subject": "seed_subject",
    "same_fixture_restated": "same_fixture_restated",
    "overlap_ok": "overlap_ok_keep",
    "overlap_ok_keep": "overlap_ok_keep",
}

_DEGRADE_NODE: ApplyNode = "apply_boundary"
_DEGRADE_MACHINE = "safe_boundary_clear"


@dataclass
class EpisodeTransitionDecision:
    """Normative typed DTO — Spec §8.4 (ellipsis prohibited)."""

    outcome: Outcome
    reason: str
    current_entities: dict[str, Any] = field(default_factory=dict)
    prior_subject: dict[str, Any] = field(default_factory=dict)
    entity_equality: dict[str, Any] = field(default_factory=dict)
    fixture_label_canonicalization: dict[str, Any] = field(default_factory=dict)
    # Infra metadata (not Spec subject fields)
    classified: bool = True
    degrade_machine: str | None = None
    raw_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> EpisodeTransitionDecision:
        data = dict(data or {})
        outcome = data.get("outcome") or "KEEP_EPISODE"
        if outcome not in ("KEEP_EPISODE", "NEW_FIXTURE", "NEW_EPISODE"):
            outcome = "KEEP_EPISODE"
        return cls(
            outcome=outcome,  # type: ignore[arg-type]
            reason=str(data.get("reason") or "soft_followup_same_episode"),
            current_entities=dict(data.get("current_entities") or {}),
            prior_subject=dict(data.get("prior_subject") or {}),
            entity_equality=dict(data.get("entity_equality") or {}),
            fixture_label_canonicalization=dict(
                data.get("fixture_label_canonicalization") or {}
            ),
            classified=bool(data.get("classified", True)),
            degrade_machine=data.get("degrade_machine"),
            raw_reason=data.get("raw_reason"),
        )


def normalize_reason(raw_reason: str | None) -> str | None:
    """Map POC / TB-V2 reason tokens onto Spec closed set; None if unknown."""
    if not raw_reason:
        return None
    key = str(raw_reason).strip()
    if key in CLOSED_REASONS:
        return key
    return _REASON_NORMALIZE.get(key)


def outcome_for_reason(reason: str) -> Outcome:
    """Derive Spec outcome from closed reason (Appendix A rows)."""
    if reason == "new_fixture":
        return "NEW_FIXTURE"
    if reason in {"low_entity_overlap", "explicit_new_episode"}:
        return "NEW_EPISODE"
    return "KEEP_EPISODE"


def route_appendix_a(outcome: str, reason: str) -> ApplyNode | None:
    """Pure Appendix A lookup. None ⇒ unclassified (degrade)."""
    return APPENDIX_A_ROUTE_TABLE.get((outcome, reason))


def select_apply_node(decision: EpisodeTransitionDecision) -> ApplyNode:
    """
    Total function: Appendix A hit → node; unclassified → safe_boundary_clear
    path (apply_boundary) per Spec FINDING-010 / Appendix A.
    """
    node = route_appendix_a(decision.outcome, decision.reason)
    if node is not None:
        return node
    decision.classified = False
    decision.degrade_machine = _DEGRADE_MACHINE
    return _DEGRADE_NODE


def build_decision_from_classify(
    *,
    raw_route: str,
    raw_reason: str,
    message: str = "",
    clubs: list[str] | None = None,
    fixture_label: str | None = None,
    compare_signal: bool = False,
    prior_episode_id: str | None = None,
    prior_teams: list[str] | None = None,
    prior_fixture: str | None = None,
    prior_subject_generation: int = 0,
    overlap_score: float | None = None,
) -> EpisodeTransitionDecision:
    """
    Build typed EpisodeTransitionDecision from POC classify_turn outputs.

    Does not mutate STS. Does not write production subject.
    """
    closed = normalize_reason(raw_reason)
    if closed is None:
        # Unclassified → degrade DTO (Appendix A miss)
        decision = EpisodeTransitionDecision(
            outcome="NEW_EPISODE",
            reason="explicit_new_episode",
            classified=False,
            degrade_machine=_DEGRADE_MACHINE,
            raw_reason=raw_reason,
            current_entities={
                "clubs": list(clubs or []),
                "fixture_label": fixture_label,
                "compare_signal": bool(compare_signal),
            },
            prior_subject={
                "source": "STS_SNAPSHOT",
                "episode_id": prior_episode_id,
                "teams": list(prior_teams or []),
                "fixture_label": prior_fixture,
                "subject_generation": int(prior_subject_generation),
            },
            entity_equality={
                "algorithm": "CANONICAL_CLUB_SET_EQUALITY",
                "overlap_score": overlap_score,
            },
            fixture_label_canonicalization={
                "rules": "NORMALIZE_WHITESPACE|CASEFOLD|STRIP_VS_SEPARATORS",
                "canonical_label": fixture_label,
            },
        )
        return decision

    outcome = outcome_for_reason(closed)
    # Consistency check vs POC route (informational; Appendix A wins).
    _ = raw_route
    return EpisodeTransitionDecision(
        outcome=outcome,
        reason=closed,
        classified=True,
        raw_reason=raw_reason,
        current_entities={
            "clubs": list(clubs or []),
            "fixture_label": fixture_label,
            "compare_signal": bool(compare_signal),
        },
        prior_subject={
            "source": "STS_SNAPSHOT",
            "episode_id": prior_episode_id,
            "teams": list(prior_teams or []),
            "fixture_label": prior_fixture,
            "subject_generation": int(prior_subject_generation),
        },
        entity_equality={
            "algorithm": "CANONICAL_CLUB_SET_EQUALITY",
            "overlap_score": overlap_score,
        },
        fixture_label_canonicalization={
            "rules": "NORMALIZE_WHITESPACE|CASEFOLD|STRIP_VS_SEPARATORS",
            "canonical_label": fixture_label,
        },
    )


class EpisodeTransition:
    """
    C3 façade — decide() centralizes KEEP CUSTOM transition for classify.

    Production TB-V2 detect remains authoritative until Migration funnel;
    this API wraps POC classify helpers into the Spec DTO.
    """

    @staticmethod
    def decide(
        message: str,
        sts: Any,
        *,
        clubs: list[str] | None = None,
        fixture_label: str | None = None,
        compare_signal: bool = False,
        overlap_score: float | None = None,
    ) -> EpisodeTransitionDecision:
        from src.conversation.langgraph_state_graph import classify_turn
        from src.conversation.sport_topic_state import SportTopicState
        from src.conversation.topic_boundary_v2 import (
            current_message_entities,
            extract_fixture_phrase,
        )

        if isinstance(sts, SportTopicState):
            prior = sts
        elif isinstance(sts, dict):
            prior = SportTopicState.from_dict(sts)
        else:
            prior = SportTopicState()

        route, reason = classify_turn(message or "", prior)
        resolved_clubs = clubs
        if resolved_clubs is None:
            resolved_clubs = current_message_entities(message or "", None)
        resolved_fx = fixture_label
        if resolved_fx is None:
            resolved_fx = extract_fixture_phrase(message or "")

        return build_decision_from_classify(
            raw_route=route,
            raw_reason=reason,
            message=message or "",
            clubs=resolved_clubs,
            fixture_label=resolved_fx,
            compare_signal=compare_signal,
            prior_episode_id=prior.episode_id,
            prior_teams=list(prior.teams or []),
            prior_fixture=prior.fixture,
            prior_subject_generation=int(getattr(prior, "subject_generation", 0) or 0),
            overlap_score=overlap_score,
        )
