"""
LANGGRAPH-STATE-POC-001 — Minimal LangGraph host for SportTopicState.

Holds conversational sport subject as graph state. Reuses topic_boundary_v2
detection helpers (fixture phrase, soft FU, single-team ask, Jaccard).

Phase 1: POC only. Default flag OFF. Production router NOT wired for writes.
Phase 2: shadow compare may invoke this with force=True (isolated copy only).
When langgraph is missing and flag ON: log + no-op (fail-open).
When flag OFF: fail-open no-op unless force=True (shadow / tests).

Single write path: `_commit` — all nodes mutate STS only through it.
"""

from __future__ import annotations

import logging
from typing import Any, Literal, TypedDict

from src.conversation.sport_topic_state import (
    SportTopicState,
    langgraph_state_enabled,
)
from src.conversation.topic_boundary_v2 import (
    _LOW_OVERLAP,
    _SOFT_FOLLOWUP,
    _fixtures_equivalent,
    current_message_entities,
    entity_overlap,
    extract_fixture_phrase,
    fold,
)

logger = logging.getLogger(__name__)

try:
    from langgraph.graph import END, START, StateGraph

    _LANGGRAPH_AVAILABLE = True
except Exception:  # pragma: no cover — optional dep
    END = START = StateGraph = None  # type: ignore[misc, assignment]
    _LANGGRAPH_AVAILABLE = False

RouteName = Literal["apply_boundary", "keep_followup", "apply_subject"]


class GraphSportState(TypedDict, total=False):
    """LangGraph-compatible state bag (STS fields + turn routing)."""

    sts: dict[str, Any]
    message: str
    # Named turn_route — LangGraph reserves `route` as a state key.
    turn_route: str
    last_node: str
    decision_reason: str
    skipped_reason: str | None


def langgraph_package_available() -> bool:
    return bool(_LANGGRAPH_AVAILABLE)


# ---------------------------------------------------------------------------
# Single write path
# ---------------------------------------------------------------------------


def _commit(state: GraphSportState, sts: SportTopicState, *, node: str) -> GraphSportState:
    """Sole updater — every node returns via this."""
    out: GraphSportState = dict(state)
    out["sts"] = sts.to_dict()
    out["last_node"] = node
    return out


def _sts_from_state(state: GraphSportState) -> SportTopicState:
    raw = state.get("sts")
    if isinstance(raw, dict):
        return SportTopicState.from_dict(raw)
    return SportTopicState()


# ---------------------------------------------------------------------------
# Decision (mirrors topic_boundary_v2; does NOT depend on ENABLE_TOPIC_BOUNDARY_V2)
# ---------------------------------------------------------------------------


def classify_turn(message: str, sts: SportTopicState) -> tuple[RouteName, str]:
    """
    Deterministic route for this turn.

    Returns (route, reason) inspired by detect_episode_boundary:
      - soft FU / short → keep_followup
      - new fixture / low overlap → apply_boundary
      - otherwise apply_subject (same-episode subject refresh or seed)
    """
    text = message or ""
    prior_teams = list(sts.teams or [])
    prior_fx = sts.fixture
    has_prior = bool(prior_teams or prior_fx)

    current = current_message_entities(text, None)
    new_fx = extract_fixture_phrase(text)

    if not has_prior:
        if new_fx or current:
            return "apply_subject", "seed_subject"
        return "keep_followup", "no_prior_no_entities"

    # Soft FU with no new entities → keep episode
    if not current and not new_fx:
        if _SOFT_FOLLOWUP.search(text) or len(text.split()) <= 6:
            return "keep_followup", "soft_followup_same_episode"
        return "keep_followup", "no_current_entities"

    # Brand-new fixture phrase vs prior
    if new_fx and prior_fx and not _fixtures_equivalent(new_fx, prior_fx):
        return "apply_boundary", "new_fixture"

    if new_fx and prior_teams and not prior_fx:
        ov = entity_overlap(prior_teams, current)
        if ov is None or ov < _LOW_OVERLAP:
            return "apply_boundary", "new_fixture_no_prior_label"

    ov = entity_overlap(prior_teams, current)
    if ov is not None and ov < _LOW_OVERLAP:
        return "apply_boundary", "low_entity_overlap"

    if new_fx and prior_fx and _fixtures_equivalent(new_fx, prior_fx):
        return "apply_subject", "same_fixture_restated"

    # Partial overlap (e.g. one shared club) already handled by Jaccard;
    # single-team ask with no overlap → boundary above. Same-club soft mention:
    if current and ov is not None and ov >= _LOW_OVERLAP:
        return "apply_subject", "overlap_ok"

    # Team named that is part of prior fixture (soft keep / subject refresh)
    if current and prior_teams:
        prior_folded = {fold(t) for t in prior_teams}
        if all(fold(c) in prior_folded for c in current):
            return "keep_followup", "soft_team_in_episode"

    return "apply_subject", "overlap_ok"


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def node_init_load(state: GraphSportState) -> GraphSportState:
    sts = _sts_from_state(state)
    out = _commit(state, sts, node="init_load")
    out["message"] = state.get("message") or ""
    out["skipped_reason"] = None
    return out


def node_apply_boundary(state: GraphSportState) -> GraphSportState:
    sts = _sts_from_state(state)
    message = state.get("message") or ""
    reason = state.get("decision_reason") or "new_episode"
    current = current_message_entities(message, None)
    new_fx = extract_fixture_phrase(message)
    sts.clear_for_new_episode(
        reason=reason,
        seed_teams=current,
        seed_fixture=new_fx,
    )
    out = _commit(state, sts, node="apply_boundary")
    out["decision_reason"] = reason
    return out


def node_keep_followup(state: GraphSportState) -> GraphSportState:
    sts = _sts_from_state(state)
    reason = state.get("decision_reason") or "soft_followup_same_episode"
    # Keep fixture/teams/episode; stamp followup_context only
    fu = dict(sts.followup_context or {})
    fu["last_soft_reason"] = reason
    fu["armed"] = True
    sts.followup_context = fu
    sts.boundary_reason = reason
    out = _commit(state, sts, node="keep_followup")
    out["decision_reason"] = reason
    return out


def node_apply_subject(state: GraphSportState) -> GraphSportState:
    sts = _sts_from_state(state)
    message = state.get("message") or ""
    reason = state.get("decision_reason") or "apply_subject"
    current = current_message_entities(message, None)
    new_fx = extract_fixture_phrase(message)
    teams = current or list(sts.teams)
    fixture = new_fx or sts.fixture
    if not fixture and len(teams) >= 2:
        fixture = f"{teams[0]} x {teams[1]}"
    topic = "comparison" if len(teams) >= 2 else ("calendar" if teams else sts.topic)
    sts.replace_subject(
        teams=teams,
        fixture=fixture,
        topic=topic,
        subject=fixture or (teams[0] if teams else None),
        keep_episode=True,
    )
    sts.boundary_reason = reason
    out = _commit(state, sts, node="apply_subject")
    out["decision_reason"] = reason
    return out


def node_classify(state: GraphSportState) -> GraphSportState:
    """Classify and stamp turn_route (no STS write beyond ensuring load)."""
    sts = _sts_from_state(state)
    message = state.get("message") or ""
    route, reason = classify_turn(message, sts)
    out: GraphSportState = dict(state)
    out["turn_route"] = route
    out["decision_reason"] = reason
    out["last_node"] = "classify"
    out["sts"] = sts.to_dict()
    return out


def _pick_route(state: GraphSportState) -> str:
    return state.get("turn_route") or "keep_followup"


# ---------------------------------------------------------------------------
# Graph compile + invoke
# ---------------------------------------------------------------------------

_COMPILED = None


def _build_graph():
    if not _LANGGRAPH_AVAILABLE:
        return None
    g = StateGraph(GraphSportState)
    g.add_node("init_load", node_init_load)
    g.add_node("classify", node_classify)
    g.add_node("apply_boundary", node_apply_boundary)
    g.add_node("keep_followup", node_keep_followup)
    g.add_node("apply_subject", node_apply_subject)
    g.add_edge(START, "init_load")
    g.add_edge("init_load", "classify")
    g.add_conditional_edges(
        "classify",
        _pick_route,
        {
            "apply_boundary": "apply_boundary",
            "keep_followup": "keep_followup",
            "apply_subject": "apply_subject",
        },
    )
    g.add_edge("apply_boundary", END)
    g.add_edge("keep_followup", END)
    g.add_edge("apply_subject", END)
    return g.compile()


def get_compiled_graph():
    global _COMPILED
    if not _LANGGRAPH_AVAILABLE:
        return None
    if _COMPILED is None:
        _COMPILED = _build_graph()
    return _COMPILED


def _run_sequential(state: GraphSportState) -> GraphSportState:
    """Same node pipeline without LangGraph (tests / missing package fallback)."""
    state = node_init_load(state)
    state = node_classify(state)
    route = _pick_route(state)
    if route == "apply_boundary":
        return node_apply_boundary(state)
    if route == "apply_subject":
        return node_apply_subject(state)
    return node_keep_followup(state)


def process_sport_state_turn(
    message: str,
    sts: SportTopicState | dict[str, Any] | None = None,
    *,
    force: bool = False,
    prefer_sequential: bool = False,
) -> SportTopicState:
    """
    Run one conversational turn through the STS graph.

    - Flag OFF (and not force): return input STS unchanged (fail-open).
    - Flag ON, package missing: log warning, return unchanged (no crash).
    - Flag ON (or force): update STS via single write path.

    `force=True` lets unit tests exercise the API without relying on env alone
    when the caller already set the flag; also used when sequential fallback
    is explicitly desired for debugging.
    """
    enabled = langgraph_state_enabled() or force
    if isinstance(sts, SportTopicState):
        current = sts
    elif isinstance(sts, dict):
        current = SportTopicState.from_dict(sts)
    else:
        current = SportTopicState()

    if not enabled:
        return current

    if not _LANGGRAPH_AVAILABLE and not prefer_sequential:
        logger.warning(
            "ENABLE_LANGGRAPH_STATE on but langgraph not installed — STS no-op"
        )
        return current

    initial: GraphSportState = {
        "sts": current.to_dict(),
        "message": message or "",
        "turn_route": "",
        "last_node": "",
        "decision_reason": "",
        "skipped_reason": None,
    }

    try:
        if prefer_sequential or not _LANGGRAPH_AVAILABLE:
            final = _run_sequential(initial)
        else:
            graph = get_compiled_graph()
            if graph is None:
                logger.warning("langgraph compile failed — STS no-op")
                return current
            final = graph.invoke(initial)
        return SportTopicState.from_dict(final.get("sts") if isinstance(final, dict) else None)
    except Exception as exc:
        logger.warning("process_sport_state_turn fail-open: %s", exc)
        return current
