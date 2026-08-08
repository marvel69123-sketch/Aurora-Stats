"""
LANGGRAPH-STATE-POC-001 — Adapter between legacy ctx and SportTopicState.

Phase 1:
  - shadow_from_ctx: build STS from CSL / last_* / SRF (read-only, no writes)
  - compare_shadow: divergence dict for logs

Phase 2 / Mission 016 Phase 3 SHADOW MODE:
  - ENABLE_LANGGRAPH_STATE_SHADOW (default OFF) — log-only compare
  - maybe_shadow_compare (Path A): capture OLD from ctx, run isolated NEW, log only
  - ingress_order_shadow_compare (Path B): post-SLL pre-CSL observe-only; Appendix B ready
  - Never writes live ctx / CSL / production memory. Never alters Aurora decisions.
  - Shadow ≠ ENABLE_LANGGRAPH_STATE (production write path stays OFF by default)

Does NOT become the sole writer. Does NOT route responses through LangGraph.
REGRA 23: zero user impact while Shadow Mode is active.
"""

from __future__ import annotations

import logging
from typing import Any

from src.conversation.sport_topic_state import (
    SportTopicState,
    langgraph_state_enabled,
    langgraph_state_shadow_enabled,
)

logger = logging.getLogger(__name__)

__all__ = [
    "langgraph_state_enabled",
    "langgraph_state_shadow_enabled",
    "shadow_from_ctx",
    "compare_shadow",
    "legacy_snapshot",
    "legacy_intent",
    "maybe_shadow_log",
    "maybe_shadow_compare",
    "ingress_order_shadow_compare",
    "infer_contamination_locus",
    "teams_norm",
    "expected_ingress_teams",
]


def teams_norm(teams: Any) -> list[str]:
    """Lowercased stripped team labels for compare."""
    if not isinstance(teams, (list, tuple)):
        return []
    return [str(x).strip().lower() for x in teams if isinstance(x, str) and x.strip()]


def expected_ingress_teams(
    message: str,
    sll_clubs: list[str] | None = None,
) -> list[str]:
    """
    Expected post-boundary subject teams at Path B ingress (message / SLL clubs).
    Used for Appendix B IO-S3 — NOT OLD vs NEW lag.
    """
    if sll_clubs:
        return [c for c in sll_clubs if isinstance(c, str) and c.strip()]
    try:
        from src.conversation.topic_boundary_v2 import (
            current_message_entities,
            extract_fixture_phrase,
        )

        clubs = current_message_entities(message or "", None)
        if clubs:
            return list(clubs)
        fx = extract_fixture_phrase(message or "")
        if fx:
            # Fixture phrase already parsed into entities above when possible;
            # fall back to splitting on x/X when entities empty.
            parts = [p.strip() for p in fx.replace("×", " x ").split(" x ") if p.strip()]
            if len(parts) >= 2:
                return parts[:2]
    except Exception:
        pass
    return []


def legacy_intent(ctx: dict[str, Any] | None) -> str | None:
    """Read-only intent signal from CSL / last_intent / sport_intents."""
    if not isinstance(ctx, dict):
        return None
    csl = ctx.get("csl")
    if isinstance(csl, dict) and isinstance(csl.get("last_intent"), str) and csl["last_intent"].strip():
        return csl["last_intent"].strip()
    for key in ("last_intent", "sport_intent"):
        v = ctx.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    si = ctx.get("sport_intents")
    if isinstance(si, dict) and isinstance(si.get("intent"), str) and si["intent"].strip():
        return si["intent"].strip()
    return None


def legacy_snapshot(ctx: dict[str, Any] | None) -> dict[str, Any]:
    """Read-only projection of legacy multi-writer subject fields."""
    if not isinstance(ctx, dict):
        return {
            "episode_id": None,
            "fixture": None,
            "teams": [],
            "subject": None,
            "topic": None,
            "owner": None,
            "date_context": None,
            "followup_context": {},
            "boundary_reason": None,
            "intent": None,
        }

    teams: list[str] = []
    fixture: str | None = None
    episode_id: str | None = None
    topic: str | None = None
    date_context: str | None = None
    owner: str | None = None
    boundary_reason: str | None = None
    followup_context: dict[str, Any] = {}

    csl = ctx.get("csl")
    if isinstance(csl, dict):
        for t in csl.get("teams") or []:
            if isinstance(t, str) and t.strip():
                teams.append(t.strip())
        fx = csl.get("fixture")
        if isinstance(fx, str) and fx.strip():
            fixture = fx.strip()
        if csl.get("episode_id"):
            episode_id = str(csl["episode_id"])
        if isinstance(csl.get("topic"), str):
            topic = csl["topic"]
        if isinstance(csl.get("date_context"), str):
            date_context = csl["date_context"]

    home = ctx.get("last_home")
    away = ctx.get("last_away")
    if isinstance(home, str) and home.strip() and home.strip() not in teams:
        teams.append(home.strip())
    if isinstance(away, str) and away.strip() and away.strip() not in teams:
        teams.append(away.strip())
    for key in ("last_match", "last_fixture"):
        v = ctx.get(key)
        if isinstance(v, str) and v.strip():
            if not fixture:
                fixture = v.strip()
            break

    srf = ctx.get("sport_referent_frame")
    if isinstance(srf, dict):
        label = srf.get("fixture_label") or srf.get("fixture")
        if isinstance(label, str) and label.strip() and not fixture:
            fixture = label.strip()
        for key in ("home", "away", "focus_team"):
            v = srf.get(key)
            if isinstance(v, str) and v.strip() and v.strip() not in teams:
                teams.append(v.strip())

    if ctx.get("episode_id") and not episode_id:
        episode_id = str(ctx["episode_id"])

    boundary_reason = None
    for key in ("boundary_reason", "topic_boundary_reason"):
        v = ctx.get(key)
        if isinstance(v, str) and v.strip():
            boundary_reason = v.strip()
            break
    tb = ctx.get("topic_boundary_v2")
    if isinstance(tb, dict) and isinstance(tb.get("reason"), str) and not boundary_reason:
        boundary_reason = tb["reason"]

    owner = None
    for key in ("last_turn_owner", "last_response_owner"):
        v = ctx.get(key)
        if isinstance(v, str) and v.strip():
            owner = v.strip()
            break

    cont = ctx.get("conversation_continuity")
    if isinstance(cont, dict):
        followup_context["continuity_mode"] = cont.get("mode")
        followup_context["continuity_fixture"] = cont.get("fixture") or cont.get("last_fixture")
    if ctx.get("ci_pending") is not None:
        followup_context["ci_pending"] = bool(ctx.get("ci_pending"))

    subject = fixture or (teams[0] if teams else None)
    return {
        "episode_id": episode_id,
        "fixture": fixture,
        "teams": teams[:4],
        "subject": subject,
        "topic": topic,
        "owner": owner,
        "date_context": date_context,
        "followup_context": followup_context,
        "boundary_reason": boundary_reason,
        "intent": legacy_intent(ctx),
        "subject_generation": int(ctx.get("subject_generation") or 0),
    }


def shadow_from_ctx(ctx: dict[str, Any] | None) -> SportTopicState:
    """
    Build SportTopicState from existing CSL / last_* / SRF without writing ctx.
    """
    snap = legacy_snapshot(ctx)
    return SportTopicState.from_dict(snap)


def compare_shadow(
    legacy: dict[str, Any] | SportTopicState | None,
    sts: SportTopicState | dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Divergence dict for logs (fixture/teams/episode/topic/boundary).

    Returns {"divergent": bool, "fields": {field: {"legacy": ..., "sts": ...}}}
    """
    if isinstance(legacy, SportTopicState):
        leg = legacy.to_dict()
    elif isinstance(legacy, dict):
        leg = dict(legacy)
    else:
        leg = {}

    if isinstance(sts, SportTopicState):
        right = sts.to_dict()
    elif isinstance(sts, dict):
        right = dict(sts)
    else:
        right = {}

    fields: dict[str, Any] = {}
    for key in ("episode_id", "fixture", "teams", "subject", "topic", "boundary_reason"):
        lv = leg.get(key)
        rv = right.get(key)
        if key == "teams":
            lv_n = [str(x).strip().lower() for x in (lv or []) if isinstance(x, str)]
            rv_n = [str(x).strip().lower() for x in (rv or []) if isinstance(x, str)]
            if lv_n != rv_n:
                fields[key] = {"legacy": lv, "sts": rv}
        else:
            lvs = (str(lv).strip().lower() if lv is not None else "")
            rvs = (str(rv).strip().lower() if rv is not None else "")
            if lvs != rvs:
                fields[key] = {"legacy": lv, "sts": rv}

    return {
        "divergent": bool(fields),
        "fields": fields,
        "legacy_fixture": leg.get("fixture"),
        "sts_fixture": right.get("fixture"),
    }


def _intent_from_route(route: str, reason: str) -> str:
    """Projected intent label for NEW_STATE (graph decision, not RS)."""
    if route == "keep_followup":
        return "followup_compare"
    if route == "apply_boundary":
        return "fixture_compare"
    if reason in {"seed_subject", "same_fixture_restated", "overlap_ok"}:
        return "fixture_compare"
    return "fixture_compare" if route == "apply_subject" else "unknown"


def infer_contamination_locus(
    message: str,
    old: dict[str, Any],
    new: dict[str, Any],
) -> str | None:
    """
    Heuristic contamination locus for Phase 2 shadow (no live ctx commit).

    (1) before_langgraph — OLD already wrong vs this turn's stated fixture
        (e.g. message Liverpool×Chelsea but OLD still Flamengo×Palmeiras).
        Soft-FU with a contaminated OLD also lands here: graph keep cannot heal
        a prior wrong subject that entered via multi-writer lag.

    (2) inside_state_layer — message states a fixture and NEW (post-graph
        isolated commit) is still wrong vs that fixture.

    (3) after_state_commit — N/A for Phase 2 live ctx (we never write back).
        Reserved if isolated post-graph NEW is wrong for a soft-FU that should
        have kept a *correct* prior (graph keep failed). Treated as inside for
        fixture-stated turns; for soft-FU keep-fail → after_state_commit on
        the isolated STS only.
    """
    try:
        from src.conversation.topic_boundary_v2 import (
            _SOFT_FOLLOWUP,
            _fixtures_equivalent,
            extract_fixture_phrase,
        )
    except Exception:
        return None

    msg_fx = extract_fixture_phrase(message or "")
    old_fx = old.get("fixture") if isinstance(old.get("fixture"), str) else None
    new_fx = new.get("fixture") if isinstance(new.get("fixture"), str) else None

    if msg_fx:
        new_ok = bool(new_fx) and _fixtures_equivalent(msg_fx, new_fx)
        old_ok = bool(old_fx) and _fixtures_equivalent(msg_fx, old_fx)
        if not new_ok:
            return "inside_state_layer"
        if not old_ok:
            return "before_langgraph"
        return None

    # Soft FU / no fixture phrase: expect NEW to keep OLD subject.
    soft = bool(_SOFT_FOLLOWUP.search(message or "")) or len((message or "").split()) <= 6
    if soft and old_fx and new_fx and not _fixtures_equivalent(old_fx, new_fx):
        # Isolated commit dropped prior — Phase 2 "after simulated commit"
        return "after_state_commit"
    return None


def maybe_shadow_compare(
    message: str,
    ctx: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """
    Path A — legacy-position shadow (POC): fail-open, read-only / side-effect-log-only.

    When ENABLE_LANGGRAPH_STATE_SHADOW is ON:
      1. Capture OLD_STATE from ctx (CSL / last_* / SRF / episode / intent)
      2. Run LangGraph STS update on an isolated copy (force=True; never writes ctx)
      3. Log OLD vs NEW + contamination_locus
      4. Return compare dict for tests (does not attach to ctx by default)

    When shadow flag OFF: return None (no-op).
    Does NOT require ENABLE_LANGGRAPH_STATE. Does NOT change message/payload/response.
    """
    if not langgraph_state_shadow_enabled():
        return None
    try:
        from src.conversation.langgraph_state_graph import (
            classify_turn,
            langgraph_package_available,
            process_sport_state_turn,
        )

        old_snap = legacy_snapshot(ctx)
        old_sts = SportTopicState.from_dict(old_snap)
        isolated = SportTopicState.from_dict(old_sts.to_dict())

        route, reason = classify_turn(message or "", isolated)
        new_sts = process_sport_state_turn(
            message or "",
            isolated,
            force=True,
            prefer_sequential=not langgraph_package_available(),
        )
        new_snap = new_sts.to_dict()
        new_intent = _intent_from_route(route, reason)
        old_intent = old_snap.get("intent")

        locus = infer_contamination_locus(message or "", old_snap, new_snap)
        diff = compare_shadow(old_snap, new_sts)

        result: dict[str, Any] = {
            "old": {
                "fixture": old_snap.get("fixture"),
                "episode": old_snap.get("episode_id"),
                "intent": old_intent,
                "teams": list(old_snap.get("teams") or []),
            },
            "new": {
                "fixture": new_snap.get("fixture"),
                "episode": new_snap.get("episode_id"),
                "intent": new_intent,
                "teams": list(new_snap.get("teams") or []),
                "boundary_reason": new_snap.get("boundary_reason"),
                "turn_route": route,
                "decision_reason": reason,
            },
            "divergent": bool(diff.get("divergent")),
            "fields": diff.get("fields") or {},
            "contamination_locus": locus,
            "message": message or "",
            "shadow_only": True,
            "shadow_path": "A_legacy_position",
            "production_write_enabled": langgraph_state_enabled(),
        }

        logger.info(
            "[AUDIT] LANGGRAPH_SHADOW OLD_STATE={fixture=%r episode=%r intent=%r teams=%r} "
            "NEW_STATE={fixture=%r episode=%r intent=%r teams=%r route=%s} "
            "divergent=%s contamination_locus=%s",
            result["old"]["fixture"],
            result["old"]["episode"],
            result["old"]["intent"],
            result["old"]["teams"],
            result["new"]["fixture"],
            result["new"]["episode"],
            result["new"]["intent"],
            result["new"]["teams"],
            route,
            result["divergent"],
            locus,
        )
        return result
    except Exception as exc:
        logger.warning("maybe_shadow_compare fail-open: %s", exc)
        return None


def ingress_order_shadow_compare(
    message: str,
    ctx: dict[str, Any] | None,
    *,
    sll_clubs: list[str] | None = None,
    force: bool = False,
    expected_teams: list[str] | None = None,
) -> dict[str, Any] | None:
    """
    Path B — P2 ingress-order experiment (Spec §9.2 / Appendix B).

    Locus: post-SLL **pre-CSL**. Observe-only; never mutates live ctx / CSL /
    production memory; never alters message, payload, or user-facing response.

    Gate: ENABLE_LANGGRAPH_STATE_SHADOW (or force for unit/harness tests).
    Fail-open. Production write stays OFF. Sole Writer stays OFF.

    Appendix B divergence classes (IO-S3/IO-S4):
      - subject_teams_mismatch: NEW teams ≠ expected ingress subject (not OLD lag)
      - soft_fu_on_contaminated_prior: soft keep that preserves contaminated OLD
        while NEW wrongly diverges from a stated expected subject
    """
    if not force and not langgraph_state_shadow_enabled():
        return None
    try:
        from src.conversation.langgraph_state_graph import (
            classify_turn,
            langgraph_package_available,
            process_sport_state_turn,
        )
        from src.conversation.topic_boundary_v2 import current_message_entities

        # Prefer explicit SLL clubs when provided (ingress-order contract).
        clubs = list(sll_clubs) if sll_clubs is not None else current_message_entities(
            message or "", None
        )
        expected = (
            list(expected_teams)
            if expected_teams is not None
            else expected_ingress_teams(message or "", clubs)
        )

        # OLD at ingress: prefer raw last_*/SRF without assuming CSL already wrote.
        old_snap = legacy_snapshot(ctx)
        old_sts = SportTopicState.from_dict(old_snap)
        isolated = SportTopicState.from_dict(old_sts.to_dict())

        route, reason = classify_turn(message or "", isolated)
        new_sts = process_sport_state_turn(
            message or "",
            isolated,
            force=True,
            prefer_sequential=not langgraph_package_available(),
        )
        new_snap = new_sts.to_dict()
        locus = infer_contamination_locus(message or "", old_snap, new_snap)
        diff = compare_shadow(old_snap, new_sts)

        # Appendix B classes — IO-S3 uses NEW vs expected, not OLD vs NEW lag.
        divergence_classes: list[str] = []
        is_switch_turn = route == "apply_boundary" or reason in {
            "new_fixture",
            "new_fixture_no_prior_label",
            "low_entity_overlap",
            "seed_subject",
        }
        new_teams = teams_norm(new_snap.get("teams"))
        exp_teams = teams_norm(expected)
        if is_switch_turn and exp_teams:
            # Pass if every expected label appears in NEW (order-insensitive;
            # single-team Inter partial may seed one club).
            if not all(any(e in n or n in e for n in new_teams) for e in exp_teams):
                # Also accept exact set equality after fold.
                if set(exp_teams) != set(new_teams):
                    # Soft match: require at least one expected club in NEW for
                    # multi-club; for single expected require membership.
                    if len(exp_teams) == 1:
                        if not any(exp_teams[0] in n or n in exp_teams[0] for n in new_teams):
                            divergence_classes.append("subject_teams_mismatch")
                    else:
                        overlap = set(exp_teams) & set(new_teams)
                        if len(overlap) < min(2, len(exp_teams)):
                            divergence_classes.append("subject_teams_mismatch")

        soft_reasons = {"soft_followup_same_episode", "soft_team_in_episode", "no_current_entities"}
        soft_contaminated = (
            reason in soft_reasons
            and route == "keep_followup"
            and locus == "before_langgraph"
            and bool(diff.get("divergent"))
        )
        # Explicit fail class when soft keep retains OLD while expected ingress
        # subject (from prior switch evidence) differs — harness may pass expected.
        if (
            reason in soft_reasons
            and route == "keep_followup"
            and exp_teams
            and new_teams
            and set(exp_teams) != set(new_teams)
            and not all(any(e in n or n in e for n in new_teams) for e in exp_teams)
        ):
            soft_contaminated = True
        if soft_contaminated:
            divergence_classes.append("soft_fu_on_contaminated_prior")

        result: dict[str, Any] = {
            "shadow_path": "B_ingress_order",
            "locus_design": "post_sll_pre_csl",
            "sll_clubs": clubs,
            "expected_teams": expected,
            "is_switch_turn": bool(is_switch_turn),
            "old": {
                "fixture": old_snap.get("fixture"),
                "episode": old_snap.get("episode_id"),
                "teams": list(old_snap.get("teams") or []),
                "subject_generation": old_snap.get("subject_generation", 0),
            },
            "new": {
                "fixture": new_snap.get("fixture"),
                "episode": new_snap.get("episode_id"),
                "teams": list(new_snap.get("teams") or []),
                "boundary_reason": new_snap.get("boundary_reason"),
                "turn_route": route,
                "decision_reason": reason,
                "subject_generation": new_snap.get("subject_generation", 0),
            },
            "divergent": bool(diff.get("divergent")),
            "fields": diff.get("fields") or {},
            "contamination_locus": locus,
            "divergence_classes": divergence_classes,
            "message": message or "",
            "shadow_only": True,
            "production_write_enabled": langgraph_state_enabled(),
            "appendix_b_ready": True,
        }
        logger.info(
            "[AUDIT] INGRESS_ORDER_SHADOW path=B divergent=%s locus=%s classes=%s "
            "switch=%s write=%s",
            result["divergent"],
            locus,
            divergence_classes,
            is_switch_turn,
            result["production_write_enabled"],
        )
        return result
    except Exception as exc:
        logger.warning("ingress_order_shadow_compare fail-open: %s", exc)
        return None


def maybe_shadow_log(ctx: dict[str, Any] | None, sts: SportTopicState | None = None) -> dict[str, Any] | None:
    """
    Legacy Phase 1 helper (ENABLE_LANGGRAPH_STATE). Prefer maybe_shadow_compare
    for Phase 2 shadow. Safe no-op when production flag off. Does not mutate ctx.
    """
    if not langgraph_state_enabled():
        return None
    try:
        shadow = sts if isinstance(sts, SportTopicState) else shadow_from_ctx(ctx)
        legacy = legacy_snapshot(ctx)
        diff = compare_shadow(legacy, shadow)
        if diff.get("divergent"):
            logger.info(
                "langgraph_state_poc shadow divergence fields=%s legacy_fx=%r sts_fx=%r",
                list((diff.get("fields") or {}).keys()),
                diff.get("legacy_fixture"),
                diff.get("sts_fixture"),
            )
        else:
            logger.debug("langgraph_state_poc shadow ok fixture=%r", shadow.fixture)
        return diff
    except Exception as exc:
        logger.warning("maybe_shadow_log fail-open: %s", exc)
        return None
