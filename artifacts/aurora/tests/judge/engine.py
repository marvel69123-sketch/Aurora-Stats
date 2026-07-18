"""Run conversations and score them with the AEP LLM Judge."""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from tests.judge.optional_llm import soft_judge_conversation
from tests.judge.rubric import aggregate_turn_scores, classify_band, score_turn
from tests.simulator.personas import Script, generate_batch


@dataclass
class JudgedTurn:
    index: int
    message: str
    intent: str | None
    summary_prefix: str
    scores: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class JudgedConversation:
    run_id: str
    persona_id: str
    seed: int
    scores: dict[str, Any]
    turns: list[JudgedTurn] = field(default_factory=list)
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "persona_id": self.persona_id,
            "seed": self.seed,
            "scores": self.scores,
            "duration_ms": self.duration_ms,
            "turns": [t.to_dict() for t in self.turns],
        }


def judge_payload_turn(
    message: str,
    payload: dict[str, Any],
    *,
    prior: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return score_turn(message, payload, prior=prior)


def run_judged_conversation(client: Any, script: Script) -> JudgedConversation:
    t0 = time.perf_counter()
    sid = f"judge_{script.persona_id}_{script.seed}_{uuid.uuid4().hex[:8]}"
    prior = {"had_sport_context": False}
    turn_scores: list[dict[str, Any]] = []
    turns_out: list[JudgedTurn] = []
    transcript_for_llm: list[dict[str, Any]] = []

    for i, turn in enumerate(script.turns, start=1):
        try:
            resp = client.post(
                "/aurora/copilot",
                json={"message": turn.message, "session_id": sid, "debug": True},
            )
            payload = (
                resp.json()
                if resp.status_code == 200
                else {
                    "intent": "http_error",
                    "entities": {},
                    "executive_summary": f"HTTP {resp.status_code}",
                }
            )
        except Exception as exc:
            payload = {
                "intent": "runtime_error",
                "entities": {},
                "executive_summary": str(exc)[:200],
            }

        scores = score_turn(turn.message, payload, prior=prior)
        turn_scores.append(scores)
        prefix = str(payload.get("executive_summary") or "")[:200].replace("\n", " | ")
        turns_out.append(
            JudgedTurn(
                index=i,
                message=turn.message,
                intent=str(payload.get("intent") or "") or None,
                summary_prefix=prefix,
                scores=scores,
            )
        )
        transcript_for_llm.append(
            {"message": turn.message, "summary_prefix": prefix}
        )

        intent = str(payload.get("intent") or "")
        ents = payload.get("entities") or {}
        if intent in {"analyze_match", "follow_up"} or (
            isinstance(ents, dict)
            and (
                ents.get("pronoun_resolved")
                or ents.get("advanced_fixture_reused")
                or ents.get("preliminary_analysis")
            )
        ):
            prior["had_sport_context"] = True

    agg = aggregate_turn_scores(turn_scores)
    soft = soft_judge_conversation(transcript_for_llm, rubric=agg)
    if isinstance(soft, dict):
        for k, v in soft.items():
            if k.endswith("_score"):
                # blend 70% rubric / 30% llm
                base = float(agg.get(k) or v)
                agg[k] = round(base * 0.7 + float(v) * 0.3, 1)
        agg["judge_mode"] = "llm+rubric"
        agg["overall_score"] = agg.get("overall_score")
        agg["band"] = classify_band(float(agg["overall_score"]))
        agg["overall"] = agg["overall_score"]
        agg["understanding"] = agg["understanding_score"]
        agg["continuity"] = agg["continuity_score"]
        agg["utility"] = agg["utility_score"]
        agg["credibility"] = agg["credibility_score"]
        agg["naturalness"] = agg["naturalness_score"]
        agg["clarity"] = agg["clarity_score"]

    return JudgedConversation(
        run_id=f"{script.persona_id}_{script.seed}",
        persona_id=script.persona_id,
        seed=script.seed,
        scores=agg,
        turns=turns_out,
        duration_ms=int((time.perf_counter() - t0) * 1000),
    )


def generate_judge_batch(
    n: int,
    *,
    base_seed: int = 42,
    persona: str | None = None,
) -> list[Script]:
    return generate_batch(n, base_seed=base_seed, persona=persona)
