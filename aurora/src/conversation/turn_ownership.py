"""
Phase 7.4 / 7.9-C — Turn Ownership.

ONE TURN = ONE OWNER.
A resolved response must not be rewritten (intent/meaning/context).
Polish-only layers may adjust style.

Additive. Fail-open. No new engines.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

logger = logging.getLogger(__name__)

Owner = Literal["NRE", "HCE", "META", "SPORT", "GA", "PROFILE", "EMOTIONAL", "POLISH"]

REWRITE_LOCKED_OWNERS = frozenset({"NRE", "HCE", "META", "GA", "PROFILE", "EMOTIONAL"})

# Continuity kinds owned by HCE — PIE must not reclaim
HCE_CONTINUITY_KINDS = frozenset(
    {
        "soft_followup",
        "short_sport_continue",
        "short_await_fixture",
        "await_fixture",
        "resume_await_fixture",
        "market_before_fixture",
        "short_affirm_pending",
        "short_generic_continue",
        "short_cancel",
        "memory_bankroll_pending",
        "memory_bankroll_saved",
        "memory_stake_guidance",
        "meta_question",
    }
)

NRE_SOCIAL_KINDS = frozenset(
    {
        "ack",
        "thanks",
        "farewell",
        "goodnight",
        "goodmorning",
        "goodafternoon",
        "laugh",
        "natural_social",
    }
)


def _owner_log(tag: str, payload: dict[str, Any] | None, **extra: Any) -> None:
    ents = (payload.get("entities") or {}) if isinstance(payload, dict) else {}
    fields = {
        "owner": ents.get("turn_owner") or "none",
        "locked": bool(ents.get("rewrite_locked")) if isinstance(payload, dict) else False,
        "intent": (payload.get("intent") if isinstance(payload, dict) else None),
        "assistant_kind": ents.get("assistant_kind"),
        "hce_kind": ents.get("hce_kind"),
        "emotional": ents.get("emotional_kind") or ents.get("emotional"),
        **extra,
    }
    try:
        parts = " ".join(f"{k}={v}" for k, v in fields.items() if v is not None)
        logger.warning("[%s] %s", tag, parts)
    except Exception:
        pass
    try:
        from src.conversation.pipeline_trace import trace as _ptrace

        _ptrace(tag, **{k: v for k, v in fields.items() if v is not None})
    except Exception:
        pass


def mark_owner(
    payload: dict[str, Any] | None,
    owner: Owner,
    *,
    rewrite_locked: bool | None = None,
) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    ents = dict(out.get("entities") or {})
    ents["turn_owner"] = owner
    locked = rewrite_locked if rewrite_locked is not None else owner in REWRITE_LOCKED_OWNERS
    ents["rewrite_locked"] = bool(locked)
    out["entities"] = ents
    logger.warning("[AUDIT] Ownership: owner=%s locked=%s", owner, locked)
    _owner_log("OWNER_LOCK", out, new_owner=owner)
    try:
        from src.conversation.pipeline_trace import trace_owner as _town

        _town("mark_owner", out, new_owner=owner)
    except Exception:
        pass
    return out


def get_owner(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    return (payload.get("entities") or {}).get("turn_owner")


def is_rewrite_locked(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    ents = payload.get("entities") or {}
    if ents.get("rewrite_locked"):
        return True
    owner = ents.get("turn_owner")
    return owner in REWRITE_LOCKED_OWNERS


def is_deferred_general(payload: dict[str, Any] | None) -> bool:
    """GA kind=general without hard lock — presence layers may still claim."""
    if not isinstance(payload, dict):
        return False
    if is_rewrite_locked(payload):
        return False
    if get_owner(payload):
        return False
    ents = payload.get("entities") or {}
    return bool(ents.get("general_assistant") and ents.get("assistant_kind") == "general")


def is_finalized_opinion_payload(payload: dict[str, Any] | None) -> bool:
    """
    Phase 8.4-A.5 — Natural match-opinion (or stamped final opinion) must not
    be stolen by IntelligenceFallback / competing presence layers.
    """
    if not isinstance(payload, dict):
        return False
    ents = payload.get("entities") or {}
    if not isinstance(ents, dict):
        return False
    if ents.get("final_response") or ents.get("response_owner"):
        return True
    if ents.get("turn_owner") and (
        ents.get("match_opinion_renderer")
        or ents.get("response_type") == "match_opinion"
        or ents.get("renderer_stage") == "match_opinion_renderer"
    ):
        return True
    if ents.get("match_opinion_renderer") or ents.get("response_type") == "match_opinion":
        return True
    if ents.get("renderer_stage") == "match_opinion_renderer":
        return True
    # Explicit forensic / path flags with a real body already produced
    if ents.get("team_opinion_path") or ents.get("match_opinion_import_ok"):
        summary = str(payload.get("executive_summary") or "").strip()
        if summary and summary not in {"?", "…", "..."}:
            return True
    if ents.get("renderer_stage") and str(ents.get("renderer_stage")) not in {
        "",
        "entered_team_opinion",
        "mop_wants_false",
        "match_opinion_import_fail",
    }:
        summary = str(payload.get("executive_summary") or "").strip()
        if summary:
            return True
    return False


def can_presence_claim(payload: dict[str, Any] | None) -> bool:
    """
    Phase 7.9-C: emotional / HPL / profile may claim when payload is empty
    or only a deferred GA general soft reply (not hard-locked).
    Phase 8.4-A.5: never claim over finalized Natural opinion.
    """
    if payload is None:
        return True
    if is_rewrite_locked(payload):
        return False
    if is_finalized_opinion_payload(payload):
        return False
    if get_owner(payload) in {"NRE", "HCE", "META", "EMOTIONAL", "PROFILE", "SPORT"}:
        return False
    return is_deferred_general(payload) or get_owner(payload) is None


def finalize_early_ownership(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    Assign owner after early / presence stack.
    Idempotent if already owned+locked.
    Phase 7.9-C: defer hard lock for GA assistant_kind=general so emotional/social
    can claim before late filters; call again after presence layers.
    """
    if not isinstance(payload, dict):
        return payload

    _owner_log("OWNER_BEFORE", payload)

    ents = dict(payload.get("entities") or {})
    if ents.get("turn_owner") and ents.get("rewrite_locked"):
        _owner_log("OWNER_AFTER", payload, action="keep_locked")
        return payload

    # Already owned but unlocked — re-evaluate stronger signals only
    if ents.get("turn_owner") and not ents.get("rewrite_locked"):
        pass  # fall through to possibly upgrade

    # Strong presence signals first (may upgrade deferred GA)
    if ents.get("emotional") or ents.get("emotional_kind"):
        out = mark_owner(payload, "EMOTIONAL")
        _owner_log("OWNER_AFTER", out, action="emotional")
        return out

    if ents.get("human_presence") or ents.get("social"):
        out = mark_owner(payload, "NRE")
        _owner_log("OWNER_AFTER", out, action="social_hpl")
        return out

    if ents.get("context_recovery") or ents.get("recovery_mode"):
        out = mark_owner(payload, "HCE")
        _owner_log("OWNER_AFTER", out, action="recovery")
        return out

    nre = ents.get("natural_response_v2")
    if nre in NRE_SOCIAL_KINDS or ents.get("assistant_kind") == "natural_social":
        out = mark_owner(payload, "NRE")
        _owner_log("OWNER_AFTER", out, action="nre")
        return out

    hce_kind = ents.get("hce_kind")
    if hce_kind == "meta_question":
        out = mark_owner(payload, "META")
        _owner_log("OWNER_AFTER", out, action="meta")
        return out
    if hce_kind:
        out = mark_owner(payload, "HCE")
        _owner_log("OWNER_AFTER", out, action="hce")
        return out

    if ents.get("assistant_kind") == "system" or ents.get("intent") == "identity":
        out = mark_owner(payload, "META")
        _owner_log("OWNER_AFTER", out, action="meta_system")
        return out

    if ents.get("profile_query") or ents.get("about_you"):
        out = mark_owner(payload, "PROFILE")
        _owner_log("OWNER_AFTER", out, action="profile")
        return out

    # Phase 7.9-C: defer hard lock on vague GA general — presence may still claim
    # Phase 7.9-D: forced path must NOT defer — lock immediately
    if ents.get("general_assistant") and ents.get("assistant_kind") == "general":
        if ents.get("ownership_finalize_pass") in {"presence", "forced"}:
            out = mark_owner(payload, "GA")
            _owner_log("OWNER_AFTER", out, action="ga_general_final")
            return out
        _owner_log(
            "OWNER_AFTER",
            payload,
            action="defer_ga_general",
            deferred=True,
        )
        return payload

    if ents.get("assistant_kind") == "math" or ents.get("general_assistant"):
        if ents.get("assistant_kind") == "small_talk" and not nre:
            out = mark_owner(payload, "GA")
            _owner_log("OWNER_AFTER", out, action="ga_small_talk")
            return out
        out = mark_owner(payload, "GA")
        _owner_log("OWNER_AFTER", out, action="ga")
        return out

    if ents.get("has_analysis") or payload.get("best_markets") or payload.get("is_live"):
        out = mark_owner(payload, "SPORT", rewrite_locked=False)
        _owner_log("OWNER_AFTER", out, action="sport")
        return out

    # Phase 8.4-A.5 — lock Natural match-opinion before IntelFallback / late polish
    if (
        ents.get("match_opinion_renderer")
        or ents.get("response_type") == "match_opinion"
        or ents.get("response_owner") == "match_opinion_renderer"
        or ents.get("final_response")
    ):
        out = mark_owner(payload, "SPORT", rewrite_locked=True)
        ents2 = dict((out or {}).get("entities") or {})
        ents2.setdefault("response_owner", "match_opinion_renderer")
        ents2["final_response"] = True
        if isinstance(out, dict):
            out["entities"] = ents2
        _owner_log("OWNER_AFTER", out, action="match_opinion_lock")
        return out

    if ents.get("turn_owner"):
        _owner_log("OWNER_AFTER", payload, action="keep_existing")
        return payload

    _owner_log("OWNER_AFTER", payload, action="unassigned")
    return payload


def finalize_presence_ownership(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    Second lock pass after emotional / HPL / natural / intel.
    Hard-locks deferred GA general if still unclaimed.
    """
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    ents = dict(out.get("entities") or {})
    ents["ownership_finalize_pass"] = "presence"
    out["entities"] = ents
    out = finalize_early_ownership(out)
    log_final_source(out, lock_moment="presence_pass")
    return out


def finalize_forced_ownership(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    Phase 7.9-D P1-1 — ownership for forced nonsport path.

    Always defines owner + rewrite_locked before late filters.
    Does not change reply text / intents / NRF.
    """
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    ents = dict(out.get("entities") or {})
    ents["forced_nonsport"] = True
    ents["ownership_finalize_pass"] = "forced"
    # Incomplete forced shell: ensure GA markers so finalize can assign GA
    if not ents.get("turn_owner") and not ents.get("hce_kind") and not ents.get(
        "assistant_kind"
    ):
        ents["general_assistant"] = True
        ents["assistant_kind"] = "general"
    out["entities"] = ents

    _owner_log(
        "FORCED_OWNER",
        out,
        stage="pre_lock",
        owner_initial=ents.get("turn_owner") or "none",
    )

    out = finalize_early_ownership(out) or out
    ents2 = out.get("entities") or {}
    # Safety: if still unlocked, force GA lock (forced path is past presence)
    if not ents2.get("rewrite_locked"):
        out = mark_owner(out, "GA") or out
        ents2 = out.get("entities") or {}

    _owner_log(
        "FORCED_LOCK",
        out,
        stage="locked",
        owner_final=ents2.get("turn_owner") or "none",
        locked=bool(ents2.get("rewrite_locked")),
    )
    log_final_source(out, lock_moment="forced_path")
    return out


def note_overwrite_blocked(
    payload: dict[str, Any] | None,
    *,
    layer: str,
) -> None:
    """Log which late/competing layer tried to overwrite a protected owner."""
    if not isinstance(payload, dict):
        return
    _owner_log(
        "OWNER_AFTER",
        payload,
        overwrite_blocked=layer,
        owner_protected=get_owner(payload) or "none",
        locked=is_rewrite_locked(payload),
    )


def log_final_source(
    payload: dict[str, Any] | None,
    *,
    lock_moment: str = "unknown",
) -> None:
    """Emit [FINAL_SOURCE] — owner final + when lock happened."""
    if not isinstance(payload, dict):
        _owner_log("FINAL_SOURCE", None, source="none", lock_moment=lock_moment)
        return
    ents = payload.get("entities") or {}
    source = (
        ents.get("turn_owner")
        or ents.get("emotional_kind")
        or ents.get("hce_kind")
        or ents.get("assistant_kind")
        or payload.get("intent")
        or "payload"
    )
    _owner_log(
        "FINAL_SOURCE",
        payload,
        source=source,
        owner_final=ents.get("turn_owner") or "none",
        lock_moment=lock_moment,
        locked=bool(ents.get("rewrite_locked")),
    )


def mark_sport_owner(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Sport pipeline produced the turn — style polish allowed, meaning locked lightly."""
    if not isinstance(payload, dict):
        return payload
    if is_rewrite_locked(payload):
        return payload
    return mark_owner(payload, "SPORT", rewrite_locked=False)


def should_skip_competing_social(payload: dict[str, Any] | None) -> bool:
    """HPL / Natural / IntelFallback / legacy small-talk must not steal owned turns."""
    if is_finalized_opinion_payload(payload):
        return True
    return is_rewrite_locked(payload) or get_owner(payload) in {
        "NRE",
        "HCE",
        "META",
        "GA",
        "PROFILE",
        "EMOTIONAL",
        "SPORT",
    }


def pie_allowed(payload: dict[str, Any] | None) -> bool:
    """
    PIE only on Sport-owned turns with room for style/clarity.
    Never on HCE continuity / NRE social / META.
    """
    if not isinstance(payload, dict):
        return False
    if is_rewrite_locked(payload):
        return False
    ents = payload.get("entities") or {}
    if ents.get("hce_kind") in HCE_CONTINUITY_KINDS:
        return False
    if ents.get("natural_response_v2") in NRE_SOCIAL_KINDS:
        return False
    owner = ents.get("turn_owner")
    if owner in {"NRE", "HCE", "META", "GA", "PROFILE", "EMOTIONAL"}:
        return False
    return bool(
        owner == "SPORT"
        or ents.get("has_analysis")
        or payload.get("best_markets")
        or payload.get("positive_factors")
    )
