"""
Deterministic quality rubric for AEP LLM Judge.

Scores 0–10 from observable conversation signals.
Never invents match facts. Soft scores only — hard AEP fails still win.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

LOOP_MARKERS = (
    "entendi. posso te ajudar com isso de forma direta",
    "diz o objetivo em uma frase",
)

INVENTION_MARKERS = (
    "probabilidade de",
    "stake recomendado",
    "xg=",
    "ve +",
)


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def _clamp(score: float) -> float:
    return round(max(0.0, min(10.0, score)), 1)


def classify_band(score: float) -> str:
    if score >= 9.0:
        return "Excelente"
    if score >= 7.0:
        return "Boa"
    if score >= 5.0:
        return "Aceitável"
    return "Ruim"


def score_turn(
    user_message: str,
    payload: dict[str, Any] | None,
    *,
    prior: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score a single turn. Returns dimension scores + overall + band."""
    prior = prior or {}
    payload = payload if isinstance(payload, dict) else {}
    ents = payload.get("entities") if isinstance(payload.get("entities"), dict) else {}
    summary = str(payload.get("executive_summary") or "")
    intent = str(payload.get("intent") or "")
    low = _fold(summary)
    msg = _fold(user_message)

    understanding = 7.5
    utility = 7.0
    continuity = 7.0
    credibility = 8.0
    naturalness = 7.5
    clarity = 7.5

    if intent in {
        "analyze_match",
        "follow_up",
        "assistant_capabilities",
        "match_opinion",
    }:
        understanding += 1.2
    if ents.get("capability_intent_detected") or ents.get("pronoun_resolved"):
        understanding += 0.8
    if ents.get("advanced_term_detected"):
        understanding += 0.8
    if intent in {"general_chat", "small_talk"} and any(
        msg.startswith(p) for p in ("e ", "xg", "mercados", "press", "kelly")
    ):
        understanding -= 3.5
    if ents.get("frustration_detected") and not ents.get(
        "recovered_after_frustration"
    ):
        understanding -= 1.5
    if ents.get("recovered_after_frustration"):
        understanding += 1.0

    if len(summary.strip()) >= 80:
        utility += 1.0
    elif len(summary.strip()) < 20:
        utility -= 3.0
    if any(m in low for m in LOOP_MARKERS):
        utility -= 4.0
        naturalness -= 3.0
        clarity -= 2.5
    if ents.get("followup_context_found") or ents.get("continuity_followup"):
        utility += 0.8
    if ents.get("best_markets") or payload.get("best_markets"):
        utility += 0.5

    had_sport = bool(prior.get("had_sport_context"))
    if had_sport and (
        ents.get("followup_context_found")
        or ents.get("pronoun_resolved")
        or ents.get("advanced_fixture_reused")
        or intent == "follow_up"
    ):
        continuity += 2.0
    elif had_sport and intent in {"general_chat", "small_talk"}:
        continuity -= 3.5
    if ents.get("advanced_fixture_reused") or ents.get("pronoun_fixture"):
        continuity += 0.5

    if ents.get("entity_invalid") or ents.get("fixture_quality") == "INVALID":
        if any(m in low for m in INVENTION_MARKERS):
            credibility -= 5.0
        else:
            credibility += 1.0
    if "sem inventar" in low or "não invent" in low:
        credibility += 0.5
    if ents.get("preliminary_analysis"):
        credibility += 0.3

    # PATCH-001 R4 — entity ∩ user input (central entity must be grounded)
    try:
        from src.conversation.entity_safety import judge_entity_overlap

        _ov = judge_entity_overlap(user_message, payload)
        ents["entity_input_overlap_ok"] = bool(_ov.get("overlap_ok"))
        ents["entity_input_overlap_missing"] = list(_ov.get("missing") or [])
        if _ov.get("has_central_entity") and not _ov.get("overlap_ok"):
            understanding -= 4.5
            credibility -= 3.0
            utility -= 2.0
            continuity -= 2.0
            ents["entity_grounding_failed"] = True
    except Exception:
        pass

    if re.search(r"[.!?]\s+\S", summary) and len(summary) > 40:
        naturalness += 0.5
    if summary.strip() in {"?", "…", "...", "."}:
        naturalness -= 4.0
        clarity -= 4.0
    if intent == "assistant_capabilities" and "posso" in low:
        naturalness += 0.5

    if "**" in summary or "\n" in summary:
        clarity += 0.5
    if len(summary) > 1200:
        clarity -= 1.0
    bullets = summary.count("•") + summary.count("- ")
    if 1 <= bullets <= 8:
        clarity += 0.5

    scores = {
        "understanding_score": _clamp(understanding),
        "utility_score": _clamp(utility),
        "continuity_score": _clamp(continuity),
        "credibility_score": _clamp(credibility),
        "naturalness_score": _clamp(naturalness),
        "clarity_score": _clamp(clarity),
    }
    overall = _clamp(
        (
            scores["understanding_score"] * 1.1
            + scores["utility_score"] * 1.1
            + scores["continuity_score"] * 1.2
            + scores["credibility_score"] * 1.2
            + scores["naturalness_score"] * 0.9
            + scores["clarity_score"] * 0.9
        )
        / 6.4
    )
    # Hard cap: never HIGH/Boa+ when central entity is ungrounded in user text
    if ents.get("entity_grounding_failed"):
        overall = min(overall, 4.5)
    scores["overall_score"] = overall
    scores["band"] = classify_band(overall)
    scores["judge_mode"] = "rubric"
    return scores


def aggregate_turn_scores(turn_scores: list[dict[str, Any]]) -> dict[str, Any]:
    if not turn_scores:
        return {
            "understanding_score": 0.0,
            "utility_score": 0.0,
            "continuity_score": 0.0,
            "credibility_score": 0.0,
            "naturalness_score": 0.0,
            "clarity_score": 0.0,
            "overall_score": 0.0,
            "band": "Ruim",
            "judge_mode": "rubric",
            "turns_scored": 0,
            "overall": 0.0,
            "understanding": 0.0,
            "continuity": 0.0,
            "utility": 0.0,
            "credibility": 0.0,
            "naturalness": 0.0,
            "clarity": 0.0,
        }

    keys = (
        "understanding_score",
        "utility_score",
        "continuity_score",
        "credibility_score",
        "naturalness_score",
        "clarity_score",
        "overall_score",
    )
    out: dict[str, Any] = {}
    for k in keys:
        vals = [float(t.get(k) or 0) for t in turn_scores]
        out[k] = _clamp(sum(vals) / len(vals))
    out["band"] = classify_band(out["overall_score"])
    out["judge_mode"] = turn_scores[-1].get("judge_mode") or "rubric"
    out["turns_scored"] = len(turn_scores)
    out["overall"] = out["overall_score"]
    out["understanding"] = out["understanding_score"]
    out["continuity"] = out["continuity_score"]
    out["utility"] = out["utility_score"]
    out["credibility"] = out["credibility_score"]
    out["naturalness"] = out["naturalness_score"]
    out["clarity"] = out["clarity_score"]
    return out
