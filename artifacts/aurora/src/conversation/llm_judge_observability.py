"""
AEP Phase 4 — LLM Judge observability (stamp-only).

Attaches heuristic quality scores to entities / debug.
Does not alter reply text or engines.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

CTX_KEY = "llm_judge_analytics"


def note_llm_judge_observability(
    ctx: dict[str, Any] | None,
    message: str,
    payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(ctx, dict) or not isinstance(payload, dict):
        return payload
    try:
        from src.conversation.judge_rubric import classify_band, score_turn

        state = dict(ctx.get(CTX_KEY) or {})
        prior = {"had_sport_context": bool(state.get("had_sport_context"))}
        scores = score_turn(message, payload, prior=prior)
        out = dict(payload)
        ents = dict(out.get("entities") or {})
        ents["judge_understanding_score"] = scores["understanding_score"]
        ents["judge_utility_score"] = scores["utility_score"]
        ents["judge_continuity_score"] = scores["continuity_score"]
        ents["judge_credibility_score"] = scores["credibility_score"]
        ents["judge_naturalness_score"] = scores["naturalness_score"]
        ents["judge_clarity_score"] = scores["clarity_score"]
        ents["judge_overall_score"] = scores["overall_score"]
        ents["judge_band"] = scores["band"]
        ents["judge_mode"] = scores.get("judge_mode") or "rubric"
        out["entities"] = ents

        intent = str(out.get("intent") or "")
        if intent in {"analyze_match", "follow_up"} or ents.get(
            "pronoun_resolved"
        ) or ents.get("advanced_fixture_reused"):
            state["had_sport_context"] = True
        hist = list(state.get("overall_hist") or [])
        hist.append(scores["overall_score"])
        state["overall_hist"] = hist[-30:]
        if hist:
            state["session_overall"] = round(sum(hist) / len(hist), 1)
            state["session_band"] = classify_band(state["session_overall"])
        ctx[CTX_KEY] = state
        return out
    except Exception as exc:
        logger.warning("note_llm_judge_observability fail-open: %s", exc)
        return payload


def judge_debug_block(entities: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(entities, dict):
        return None
    if entities.get("judge_overall_score") is None:
        return None
    return {
        "overall": entities.get("judge_overall_score"),
        "understanding": entities.get("judge_understanding_score"),
        "utility": entities.get("judge_utility_score"),
        "continuity": entities.get("judge_continuity_score"),
        "credibility": entities.get("judge_credibility_score"),
        "naturalness": entities.get("judge_naturalness_score"),
        "clarity": entities.get("judge_clarity_score"),
        "band": entities.get("judge_band"),
        "mode": entities.get("judge_mode"),
    }
