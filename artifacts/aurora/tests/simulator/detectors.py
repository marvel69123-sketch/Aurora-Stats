"""
Automatic failure detectors for simulated conversations.

Heuristic only — simulation platform. Does not change Aurora engines.
"""

from __future__ import annotations

import re
from typing import Any

from tests.evals.harness import LOOP_MARKERS, _fold, detect_frustration, detect_loop

INVENTION_MARKERS = (
    "probabilidade de",
    "stake recomendado",
    "melhor mercado",
    "xg=",
    "ve +",
    "odd justa",
)

USELESS_EXACT = {"?", "…", "...", ".", "!", ""}

GA_STEAL_INTENTS = frozenset({"general_chat", "small_talk"})
SPORT_INTENTS = frozenset(
    {
        "analyze_match",
        "follow_up",
        "match_opinion",
        "assistant_capabilities",
        "live_opportunities",
    }
)


def extract_turn_obs(payload: dict[str, Any], user_message: str) -> dict[str, Any]:
    ents = payload.get("entities") or {}
    if not isinstance(ents, dict):
        ents = {}
    summary = str(payload.get("executive_summary") or "")
    return {
        "user_message": user_message,
        "intent": payload.get("intent"),
        "fixture_quality": ents.get("fixture_quality") or payload.get("fixture_quality"),
        "entity_invalid": ents.get("entity_invalid"),
        "assistant_kind": ents.get("assistant_kind"),
        "response_owner": ents.get("response_owner"),
        "overwrite_by": ents.get("overwrite_by"),
        "fallback_kind": ents.get("fallback_kind"),
        "followup_context_found": ents.get("followup_context_found"),
        "continuity_followup": ents.get("continuity_followup"),
        "pronoun_resolved": ents.get("pronoun_resolved"),
        "pronoun_fixture": ents.get("pronoun_fixture"),
        "advanced_term_detected": ents.get("advanced_term_detected"),
        "advanced_term": ents.get("advanced_term"),
        "advanced_fixture_reused": ents.get("advanced_fixture_reused"),
        "advanced_before_fallback": ents.get("advanced_before_fallback"),
        "frustration_detected": ents.get("frustration_detected"),
        "frustration_type": ents.get("frustration_type"),
        "frustration_score": ents.get("frustration_score"),
        "recovered_after_frustration": ents.get("recovered_after_frustration"),
        "recovery_turns": ents.get("recovery_turns"),
        "repair_mode": bool(ents.get("repair_mode") or ents.get("conversation_repair")),
        "capability_intent_detected": ents.get("capability_intent_detected"),
        "summary": summary,
        "summary_prefix": summary[:220].replace("\n", " | "),
        "summary_len": len(summary.strip()),
    }


def _has_context_signal(obs: dict[str, Any]) -> bool:
    return bool(
        obs.get("followup_context_found")
        or obs.get("continuity_followup")
        or obs.get("pronoun_resolved")
        or obs.get("pronoun_fixture")
        or obs.get("advanced_fixture_reused")
        or obs.get("advanced_term_detected")
        or obs.get("intent") == "follow_up"
    )


def _looks_useless(obs: dict[str, Any]) -> bool:
    text = _fold(str(obs.get("summary") or ""))
    if text in USELESS_EXACT:
        return True
    if len(text) < 12:
        return True
    if re.fullmatch(r"interessante\.?\s*\??", text):
        return True
    return False


def detect_turn_failures(
    obs: dict[str, Any],
    *,
    expect: dict[str, Any] | None,
    prior_intents: list[str],
    had_sport_context: bool,
) -> dict[str, bool]:
    """Return boolean flags for each detector on this turn."""
    expect = expect or {}
    summary = str(obs.get("summary") or "")
    intent = str(obs.get("intent") or "")
    flags = {
        "loop_detected": False,
        "context_lost": False,
        "intent_flip": False,
        "fallback_abuse": False,
        "invalid_entity": False,
        "hallucination_risk": False,
        "frustration_detected": False,
        "useless_reply": False,
    }

    # Loop
    if expect.get("no_loop") is not False:
        flags["loop_detected"] = detect_loop(summary)
        if any(m in _fold(summary) for m in LOOP_MARKERS) and intent in GA_STEAL_INTENTS:
            flags["loop_detected"] = True

    # Frustration (user-side + observability stamp)
    flags["frustration_detected"] = bool(
        obs.get("frustration_detected")
        or detect_frustration(str(obs.get("user_message") or ""))
    )

    # Context lost — sport session then short FU / pronoun without reuse
    if expect.get("context_expected") and had_sport_context:
        if not _has_context_signal(obs):
            flags["context_lost"] = True
        if expect.get("no_ga_steal") and intent in GA_STEAL_INTENTS:
            flags["context_lost"] = True
            flags["intent_flip"] = True

    # Intent flip — after sport analysis, sudden GA steal on continuity-like turn
    if had_sport_context and prior_intents:
        last = prior_intents[-1]
        if last in {"analyze_match", "follow_up"} and intent in GA_STEAL_INTENTS:
            msg = _fold(str(obs.get("user_message") or ""))
            if any(
                msg.startswith(p)
                for p in (
                    "e ",
                    "mercados",
                    "placar",
                    "estat",
                    "favorito",
                    "dele",
                    "dela",
                    "xg",
                    "press",
                    "kelly",
                    "edge",
                    "stake",
                    "value",
                    "qual o edge",
                )
            ):
                flags["intent_flip"] = True

    if "intent" in expect:
        want = expect["intent"]
        if isinstance(want, list):
            if intent not in want:
                flags["intent_flip"] = True
        elif intent != want:
            flags["intent_flip"] = True

    if "soft_intent" in expect:
        # soft — only flag if totally empty / loop, not hard miss
        pass

    # Fallback abuse
    if obs.get("overwrite_by") == "intelligence_fallback":
        flags["fallback_abuse"] = True
    if obs.get("fallback_kind") in {"calendar_authority", "intelligence_fallback"}:
        if expect.get("context_expected") or expect.get("no_ga_steal"):
            flags["fallback_abuse"] = True

    # Invalid entity expectations
    if expect.get("entity_invalid") is True or expect.get("fixture_quality") == "INVALID":
        if obs.get("entity_invalid") is not True and obs.get("fixture_quality") != "INVALID":
            flags["invalid_entity"] = True  # expected INVALID but didn't get it
        # Hallucination if INVALID path still invents markets language
        if expect.get("no_invention") and any(
            m in _fold(summary) for m in INVENTION_MARKERS
        ):
            flags["hallucination_risk"] = True
    else:
        # Unexpected INVALID on a real fixture ask is noteworthy but not always fail
        if obs.get("entity_invalid") is True and expect.get("sportish"):
            # soft: do not mark invalid_entity as failure for PARTIAL real fixtures
            pass

    # Hallucination risk on fiction markers without invalid flag
    fiction_user = any(
        x in _fold(str(obs.get("user_message") or ""))
        for x in ("goku", "naruto", "harry potter", "voldemort")
    )
    if fiction_user and obs.get("entity_invalid") is not True:
        if any(m in _fold(summary) for m in INVENTION_MARKERS):
            flags["hallucination_risk"] = True
            flags["invalid_entity"] = True

    # Useless reply
    if expect.get("useful_reply") or expect.get("no_loop"):
        if _looks_useless(obs):
            flags["useless_reply"] = True

    # Repair / frustration expect
    if expect.get("frustration_or_repair"):
        if not (
            obs.get("repair_mode")
            or flags["frustration_detected"]
            or intent in {"assistant_capabilities", "follow_up", "analyze_match"}
        ):
            # soft miss — not always repair; only flag loop
            if flags["loop_detected"]:
                flags["intent_flip"] = True

    return flags


def conversation_failed(turn_flags: list[dict[str, bool]]) -> bool:
    critical = (
        "loop_detected",
        "context_lost",
        "intent_flip",
        "fallback_abuse",
        "hallucination_risk",
        "invalid_entity",
        "useless_reply",
    )
    for flags in turn_flags:
        if any(flags.get(k) for k in critical):
            return True
    return False


def first_failure_turn(turn_flags: list[dict[str, bool]]) -> int | None:
    critical = (
        "loop_detected",
        "context_lost",
        "intent_flip",
        "fallback_abuse",
        "hallucination_risk",
        "invalid_entity",
        "useless_reply",
    )
    for i, flags in enumerate(turn_flags, start=1):
        if any(flags.get(k) for k in critical):
            return i
    return None
