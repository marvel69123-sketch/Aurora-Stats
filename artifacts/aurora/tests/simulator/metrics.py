"""Aggregate simulator metrics and JSON report shaping."""

from __future__ import annotations

from collections import Counter
from typing import Any

from tests.simulator.engine import ConversationResult


def _pct(num: float, den: float) -> float:
    if den <= 0:
        return 0.0
    return round(num / den * 100.0, 1)


def aggregate(results: list[ConversationResult]) -> dict[str, Any]:
    total = len(results)
    successes = sum(1 for r in results if r.success)
    loops = 0
    context_loss = 0
    intent_flips = 0
    fallbacks = 0
    invalid_entity = 0
    hallucinations = 0
    frustrations = 0
    useless = 0
    context_ok = 0
    context_checks = 0
    intent_ok = 0
    intent_checks = 0
    fail_turns: list[int] = []
    top_counter: Counter[str] = Counter()
    by_persona: dict[str, dict[str, int]] = {}

    for r in results:
        bucket = by_persona.setdefault(r.persona_id, {"runs": 0, "success": 0, "fail": 0})
        bucket["runs"] += 1
        if r.success:
            bucket["success"] += 1
        else:
            bucket["fail"] += 1
            if r.failure_turn:
                fail_turns.append(r.failure_turn)
            for reason in r.failure_reasons:
                top_counter[reason] += 1

        for turn in r.turns:
            flags = turn.flags
            if flags.get("loop_detected"):
                loops += 1
            if flags.get("context_lost"):
                context_loss += 1
            if flags.get("intent_flip"):
                intent_flips += 1
            if flags.get("fallback_abuse"):
                fallbacks += 1
            if flags.get("invalid_entity"):
                invalid_entity += 1
            if flags.get("hallucination_risk"):
                hallucinations += 1
            if flags.get("frustration_detected"):
                frustrations += 1
            if flags.get("useless_reply"):
                useless += 1

            # Context preservation: turns that expected context
            if turn.tag in {"followup", "advanced", "pronoun_after_invalid"}:
                context_checks += 1
                if not flags.get("context_lost"):
                    context_ok += 1

            # Intent accuracy: capability / invalid hard expects via tag
            if turn.tag == "capabilities":
                intent_checks += 1
                if turn.observed.get("intent") == "assistant_capabilities":
                    intent_ok += 1
            if turn.tag in {"fiction", "pronoun_after_invalid"}:
                intent_checks += 1
                if (
                    turn.observed.get("entity_invalid") is True
                    or turn.observed.get("fixture_quality") == "INVALID"
                ):
                    intent_ok += 1

    avg_ttf = round(sum(fail_turns) / len(fail_turns), 2) if fail_turns else None

    top_failures = [
        {"reason": reason, "count": count}
        for reason, count in top_counter.most_common(15)
    ]

    return {
        "total_runs": total,
        "success_rate": _pct(successes, total),
        "loops": loops,
        "context_loss": context_loss,
        "fallbacks": fallbacks,
        "intent_flips": intent_flips,
        "invalid_entity": invalid_entity,
        "hallucination_risk": hallucinations,
        "frustration_detected": frustrations,
        "useless_replies": useless,
        "top_failures": top_failures,
        "metrics": {
            "conversation_success_rate": _pct(successes, total),
            "loop_rate": _pct(loops, total),
            "context_preservation": _pct(context_ok, context_checks)
            if context_checks
            else None,
            "intent_accuracy": _pct(intent_ok, intent_checks) if intent_checks else None,
            "average_turns_before_failure": avg_ttf,
            "context_checks": context_checks,
            "intent_checks": intent_checks,
        },
        "by_persona": by_persona,
    }


def build_report(
    results: list[ConversationResult],
    *,
    requested_runs: int,
    seed: int,
    include_failures_detail: bool = True,
    max_failure_details: int = 50,
) -> dict[str, Any]:
    summary = aggregate(results)
    failures = [r for r in results if not r.success]
    detail = []
    if include_failures_detail:
        for r in failures[:max_failure_details]:
            bad_turns = [
                {
                    "index": t.index,
                    "message": t.message,
                    "tag": t.tag,
                    "intent": t.observed.get("intent"),
                    "flags": {k: v for k, v in t.flags.items() if v},
                    "prefix": t.observed.get("summary_prefix"),
                }
                for t in r.turns
                if any(t.flags.values())
            ]
            detail.append(
                {
                    "run_id": r.run_id,
                    "persona_id": r.persona_id,
                    "seed": r.seed,
                    "failure_turn": r.failure_turn,
                    "failure_reasons": r.failure_reasons,
                    "bad_turns": bad_turns,
                }
            )

    report = {
        "platform": "AEP",
        "component": "conversation_simulator",
        "version": "2.0.0",
        "requested_runs": requested_runs,
        "seed": seed,
        "total_runs": summary["total_runs"],
        "success_rate": summary["success_rate"],
        "loops": summary["loops"],
        "context_loss": summary["context_loss"],
        "fallbacks": summary["fallbacks"],
        "top_failures": summary["top_failures"],
        "intent_flips": summary["intent_flips"],
        "invalid_entity": summary["invalid_entity"],
        "hallucination_risk": summary["hallucination_risk"],
        "frustration_detected": summary["frustration_detected"],
        "metrics": summary["metrics"],
        "by_persona": summary["by_persona"],
        "failure_details": detail,
    }
    # AEP Phase 3 — attach frustration analytics slice
    try:
        from tests.frustration.metrics import analyze_simulator_conversations

        report["frustration_analytics"] = analyze_simulator_conversations(results)
    except Exception:
        report["frustration_analytics"] = None
    # AEP Phase 4 — LLM Judge slice
    try:
        from tests.judge.metrics import judge_simulator_results

        report["llm_judge"] = judge_simulator_results(results)
    except Exception:
        report["llm_judge"] = None
    return report
