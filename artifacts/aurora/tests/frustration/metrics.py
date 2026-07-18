"""Aggregate frustration analytics metrics."""

from __future__ import annotations

from collections import Counter
from typing import Any

from tests.frustration.engine import FrustSessionResult


def _pct(num: float, den: float) -> float:
    if den <= 0:
        return 0.0
    return round(num / den * 100.0, 1)


def aggregate(sessions: list[FrustSessionResult]) -> dict[str, Any]:
    total = len(sessions)
    with_frust = [s for s in sessions if s.had_frustration]
    recovered = [s for s in with_frust if s.recovered is True]
    repeated = [s for s in with_frust if s.repeated_frustration]
    turns_list = [
        s.turns_until_frustration
        for s in with_frust
        if s.turns_until_frustration is not None
    ]
    cause_counter: Counter[str] = Counter()
    for s in with_frust:
        for t in s.frustration_types:
            cause_counter[t] += 1

    top_causes = [name for name, _ in cause_counter.most_common(8)]

    by_script: dict[str, dict[str, Any]] = {}
    for s in sessions:
        b = by_script.setdefault(
            s.script_id,
            {"sessions": 0, "frustrated": 0, "recovered": 0},
        )
        b["sessions"] += 1
        if s.had_frustration:
            b["frustrated"] += 1
            if s.recovered:
                b["recovered"] += 1

    return {
        "total_sessions": total,
        "frustration_rate": _pct(len(with_frust), total),
        "recovery_rate": _pct(len(recovered), len(with_frust)),
        "repeated_frustration_rate": _pct(len(repeated), len(with_frust)),
        "turns_until_frustration_avg": (
            round(sum(turns_list) / len(turns_list), 2) if turns_list else None
        ),
        "top_causes": top_causes,
        "cause_counts": dict(cause_counter.most_common()),
        "frustrated_sessions": len(with_frust),
        "recovered_sessions": len(recovered),
        "by_script": by_script,
    }


def build_report(
    sessions: list[FrustSessionResult],
    *,
    requested_sessions: int,
    seed: int,
    max_details: int = 40,
) -> dict[str, Any]:
    summary = aggregate(sessions)
    details = []
    for s in sessions:
        if not s.had_frustration:
            continue
        if len(details) >= max_details:
            break
        details.append(
            {
                "script_id": s.script_id,
                "seed": s.seed,
                "types": s.frustration_types,
                "recovered": s.recovered,
                "recovery_turns": s.recovery_turns,
                "turns_until_frustration": s.turns_until_frustration,
                "repeated": s.repeated_frustration,
                "sample_turns": [
                    {
                        "message": t.message,
                        "type": t.frustration_type,
                        "recovered": t.recovered_after_frustration,
                        "intent": t.intent,
                        "prefix": t.summary_prefix[:120],
                    }
                    for t in s.turns
                    if t.frustration_detected or t.tag in {"frustration", "after"}
                ],
            }
        )

    report = {
        "platform": "AEP",
        "component": "frustration_analytics",
        "version": "3.0.0",
        "requested_sessions": requested_sessions,
        "seed": seed,
        "total_sessions": summary["total_sessions"],
        "frustration_rate": summary["frustration_rate"],
        "recovery_rate": summary["recovery_rate"],
        "repeated_frustration_rate": summary["repeated_frustration_rate"],
        "turns_until_frustration_avg": summary["turns_until_frustration_avg"],
        "top_causes": summary["top_causes"],
        "cause_counts": summary["cause_counts"],
        "by_script": summary["by_script"],
        "session_details": details,
        "log_fields": [
            "frustration_detected",
            "frustration_type",
            "frustration_score",
            "recovered_after_frustration",
            "recovery_turns",
        ],
    }
    # Soft quality snapshot from recovered vs not (rubric on sample prefixes)
    try:
        from src.conversation.judge_rubric import classify_band, score_turn

        scored = []
        for s in sessions[:80]:
            for t in s.turns:
                payload = {
                    "intent": t.intent,
                    "entities": {
                        "frustration_detected": t.frustration_detected,
                        "frustration_type": t.frustration_type,
                        "recovered_after_frustration": t.recovered_after_frustration,
                    },
                    "executive_summary": t.summary_prefix,
                }
                scored.append(score_turn(t.message, payload))
        if scored:
            overall = round(
                sum(float(x["overall_score"]) for x in scored) / len(scored), 1
            )
            report["llm_judge"] = {
                "overall": overall,
                "band": classify_band(overall),
                "source": "frustration_sessions",
            }
    except Exception:
        report["llm_judge"] = None
    return report


def analyze_simulator_conversations(sim_results: list[Any]) -> dict[str, Any]:
    """
    Derive frustration metrics from Conversation Simulator results
    (entities already stamped by observability layer).
    """
    total = len(sim_results)
    with_frust = 0
    recovered = 0
    causes: Counter[str] = Counter()
    for r in sim_results:
        turns = getattr(r, "turns", None) or []
        session_frust = False
        session_rec = False
        for t in turns:
            obs = getattr(t, "observed", None) or {}
            # simulator TurnResult may not have frustration — check flags/attrs
            flags = getattr(t, "flags", {}) or {}
            if flags.get("frustration_detected") or obs.get("frustration_detected"):
                session_frust = True
                ftype = obs.get("frustration_type") or "MISUNDERSTANDING"
                causes[str(ftype)] += 1
            if obs.get("recovered_after_frustration") is True:
                session_rec = True
        if session_frust:
            with_frust += 1
            if session_rec:
                recovered += 1
    return {
        "total_sessions": total,
        "frustration_rate": _pct(with_frust, total),
        "recovery_rate": _pct(recovered, with_frust),
        "top_causes": [n for n, _ in causes.most_common(5)],
        "source": "conversation_simulator",
    }
