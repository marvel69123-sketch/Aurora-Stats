"""Aggregate LLM Judge reports."""

from __future__ import annotations

from collections import Counter
from typing import Any

from tests.judge.engine import JudgedConversation
from tests.judge.rubric import classify_band


def _avg(vals: list[float]) -> float:
    if not vals:
        return 0.0
    return round(sum(vals) / len(vals), 1)


def aggregate(results: list[JudgedConversation]) -> dict[str, Any]:
    keys = (
        "understanding_score",
        "utility_score",
        "continuity_score",
        "credibility_score",
        "naturalness_score",
        "clarity_score",
        "overall_score",
    )
    buckets = {k: [] for k in keys}
    bands: Counter[str] = Counter()
    by_persona: dict[str, list[float]] = {}

    for r in results:
        s = r.scores or {}
        for k in keys:
            buckets[k].append(float(s.get(k) or 0))
        bands[str(s.get("band") or classify_band(float(s.get("overall_score") or 0)))] += 1
        by_persona.setdefault(r.persona_id, []).append(float(s.get("overall_score") or 0))

    overall = _avg(buckets["overall_score"])
    return {
        "total_conversations": len(results),
        "overall": overall,
        "understanding": _avg(buckets["understanding_score"]),
        "utility": _avg(buckets["utility_score"]),
        "continuity": _avg(buckets["continuity_score"]),
        "credibility": _avg(buckets["credibility_score"]),
        "naturalness": _avg(buckets["naturalness_score"]),
        "clarity": _avg(buckets["clarity_score"]),
        "overall_score": overall,
        "understanding_score": _avg(buckets["understanding_score"]),
        "utility_score": _avg(buckets["utility_score"]),
        "continuity_score": _avg(buckets["continuity_score"]),
        "credibility_score": _avg(buckets["credibility_score"]),
        "naturalness_score": _avg(buckets["naturalness_score"]),
        "clarity_score": _avg(buckets["clarity_score"]),
        "band": classify_band(overall),
        "band_distribution": dict(bands),
        "by_persona_overall": {
            pid: _avg(vals) for pid, vals in sorted(by_persona.items())
        },
    }


def build_report(
    results: list[JudgedConversation],
    *,
    requested: int,
    seed: int,
    max_details: int = 30,
) -> dict[str, Any]:
    summary = aggregate(results)
    # lowest overall samples for triage
    ranked = sorted(
        results, key=lambda r: float((r.scores or {}).get("overall_score") or 0)
    )
    details = []
    for r in ranked[:max_details]:
        details.append(
            {
                "run_id": r.run_id,
                "persona_id": r.persona_id,
                "seed": r.seed,
                "scores": {
                    "overall": r.scores.get("overall"),
                    "understanding": r.scores.get("understanding"),
                    "continuity": r.scores.get("continuity"),
                    "utility": r.scores.get("utility"),
                    "band": r.scores.get("band"),
                    "judge_mode": r.scores.get("judge_mode"),
                },
            }
        )
    return {
        "platform": "AEP",
        "component": "llm_judge",
        "version": "4.0.0",
        "requested_conversations": requested,
        "seed": seed,
        **summary,
        "lowest_samples": details,
    }


def judge_simulator_results(sim_results: list[Any]) -> dict[str, Any]:
    """Score already-run simulator conversations from observed turns."""
    from tests.judge.rubric import aggregate_turn_scores, score_turn

    judged: list[dict[str, Any]] = []
    for r in sim_results:
        prior = {"had_sport_context": False}
        turn_scores = []
        for t in getattr(r, "turns", []) or []:
            obs = getattr(t, "observed", {}) or {}
            payload = {
                "intent": obs.get("intent"),
                "entities": {
                    k: obs.get(k)
                    for k in (
                        "followup_context_found",
                        "continuity_followup",
                        "pronoun_resolved",
                        "pronoun_fixture",
                        "advanced_fixture_reused",
                        "advanced_term_detected",
                        "entity_invalid",
                        "fixture_quality",
                        "frustration_detected",
                        "recovered_after_frustration",
                        "capability_intent_detected",
                        "preliminary_analysis",
                    )
                },
                "executive_summary": obs.get("summary") or obs.get("summary_prefix") or "",
            }
            turn_scores.append(
                score_turn(str(getattr(t, "message", "")), payload, prior=prior)
            )
            if obs.get("intent") in {"analyze_match", "follow_up"} or obs.get(
                "pronoun_resolved"
            ):
                prior["had_sport_context"] = True
        judged.append(aggregate_turn_scores(turn_scores))

    if not judged:
        return {"overall": 0.0, "source": "conversation_simulator"}

    def avg(key: str) -> float:
        vals = [float(j.get(key) or 0) for j in judged]
        return round(sum(vals) / len(vals), 1)

    return {
        "source": "conversation_simulator",
        "total_conversations": len(judged),
        "overall": avg("overall"),
        "understanding": avg("understanding"),
        "continuity": avg("continuity"),
        "utility": avg("utility"),
        "credibility": avg("credibility"),
        "naturalness": avg("naturalness"),
        "clarity": avg("clarity"),
        "band": classify_band(avg("overall")),
    }
