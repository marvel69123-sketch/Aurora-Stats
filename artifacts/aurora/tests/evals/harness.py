"""
AEP harness — run conversational cases against /aurora/copilot.

Evaluation-only. Does not modify Aurora engines.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

LOOP_MARKERS = (
    "entendi. posso te ajudar com isso de forma direta",
    "diz o objetivo em uma frase",
    "pode falar comigo normalmente — em que posso ajudar?",
    "pode reformular em uma frase o que você queria saber?",
)

FRUSTRATION_USER_MARKERS = (
    "voce nao entendeu",
    "você não entendeu",
    "nao entendeu",
    "não entendeu",
    "aff",
    "preste atencao",
    "preste atenção",
    "nao foi isso",
    "não foi isso",
    "releia",
    "pensa um pouco",
    "nao respondeu",
    "não respondeu",
    "isso esta errado",
    "isso está errado",
    "hã?",
    "ha?",
    "???",
)


@dataclass
class EvalResult:
    id: str
    category: str
    evaluation_pass: bool
    evaluation_score: float
    evaluation_fail_reason: str | None = None
    loop_detected: bool = False
    frustration_detected: bool = False
    context_preserved: bool | None = None
    observed: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fold(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def detect_loop(summary: str) -> bool:
    low = _fold(summary)
    if not low:
        return True
    if low in {"?", "…", "...", "."}:
        return True
    return any(m in low for m in LOOP_MARKERS)


def detect_frustration(message: str) -> bool:
    low = _fold(message)
    return any(m in low for m in FRUSTRATION_USER_MARKERS)


def _extract_observed(payload: dict[str, Any]) -> dict[str, Any]:
    ents = payload.get("entities") or {}
    if not isinstance(ents, dict):
        ents = {}
    summary = str(payload.get("executive_summary") or "")
    return {
        "intent": payload.get("intent"),
        "fixture_quality": ents.get("fixture_quality") or payload.get("fixture_quality"),
        "entity_invalid": ents.get("entity_invalid"),
        "assistant_kind": ents.get("assistant_kind"),
        "response_owner": ents.get("response_owner"),
        "turn_owner": ents.get("turn_owner"),
        "followup_context_found": ents.get("followup_context_found"),
        "followup_before_fallback": ents.get("followup_before_fallback"),
        "continuity_followup": ents.get("continuity_followup"),
        "preliminary_analysis": ents.get("preliminary_analysis"),
        "repair_mode": bool(ents.get("repair_mode") or ents.get("conversation_repair")),
        "repair_reclassified": ents.get("repair_reclassified"),
        "capability_intent_detected": ents.get("capability_intent_detected"),
        "pronoun_detected": ents.get("pronoun_detected"),
        "pronoun_value": ents.get("pronoun_value"),
        "pronoun_resolved": ents.get("pronoun_resolved"),
        "pronoun_entity": ents.get("pronoun_entity"),
        "pronoun_fixture": ents.get("pronoun_fixture"),
        "pronoun_before_fallback": ents.get("pronoun_before_fallback"),
        "entity_resolved": ents.get("entity_resolved"),
        "advanced_term_detected": ents.get("advanced_term_detected"),
        "advanced_term": ents.get("advanced_term"),
        "advanced_fixture_reused": ents.get("advanced_fixture_reused"),
        "advanced_before_fallback": ents.get("advanced_before_fallback"),
        "frustration_detected": ents.get("frustration_detected"),
        "frustration_type": ents.get("frustration_type"),
        "frustration_score": ents.get("frustration_score"),
        "recovered_after_frustration": ents.get("recovered_after_frustration"),
        "recovery_turns": ents.get("recovery_turns"),
        "overwrite_by": ents.get("overwrite_by"),
        "summary_prefix": summary[:220].replace("\n", " | "),
        "loop_detected": detect_loop(summary),
    }


def _expect_bool(obs: dict[str, Any], key: str, expected: bool) -> str | None:
    val = obs.get(key)
    # soft aliases
    if key == "followup_found":
        val = bool(
            obs.get("followup_context_found")
            or obs.get("continuity_followup")
            or obs.get("intent") == "follow_up"
        )
    if key == "fixture_reused":
        val = bool(
            obs.get("advanced_fixture_reused")
            or (
                obs.get("pronoun_resolved")
                and (obs.get("pronoun_fixture") or obs.get("followup_resolved_fixture"))
            )
            or obs.get("followup_context_found")
            or obs.get("continuity_followup")
            or (
                obs.get("intent") in {"follow_up", "analyze_match"}
                and (obs.get("pronoun_resolved") or obs.get("advanced_term_detected"))
            )
        )
    if key == "entity_resolved":
        val = bool(
            obs.get("entity_resolved")
            or (obs.get("pronoun_resolved") and obs.get("pronoun_entity"))
        )
    if bool(val) != bool(expected):
        return f"{key}_expected_{expected}_got_{val}"
    return None


def evaluate_expectations(
    expect: dict[str, Any] | None,
    obs: dict[str, Any],
    *,
    user_messages: list[str],
) -> tuple[bool, list[str], bool | None]:
    """Return (ok, fail_reasons, context_preserved)."""
    if not isinstance(expect, dict) or not expect:
        return True, [], None

    fails: list[str] = []
    context_preserved: bool | None = None

    if "intent" in expect:
        want = expect["intent"]
        got = obs.get("intent")
        if isinstance(want, list):
            if got not in want:
                fails.append(f"intent_expected_one_of_{want}_got_{got}")
        elif got != want:
            fails.append(f"intent_expected_{want}_got_{got}")

    if "fixture_quality" in expect:
        if obs.get("fixture_quality") != expect["fixture_quality"]:
            fails.append(
                f"fixture_quality_expected_{expect['fixture_quality']}_got_{obs.get('fixture_quality')}"
            )

    if "entity_invalid" in expect:
        if bool(obs.get("entity_invalid")) != bool(expect["entity_invalid"]):
            fails.append(
                f"entity_invalid_expected_{expect['entity_invalid']}_got_{obs.get('entity_invalid')}"
            )

    if "followup_found" in expect:
        err = _expect_bool(obs, "followup_found", bool(expect["followup_found"]))
        if err:
            fails.append(err)
        else:
            context_preserved = True

    if "fixture_reused" in expect:
        err = _expect_bool(obs, "fixture_reused", bool(expect["fixture_reused"]))
        if err:
            fails.append(err)
            context_preserved = False
        else:
            context_preserved = True

    if "entity_resolved" in expect:
        err = _expect_bool(obs, "entity_resolved", bool(expect["entity_resolved"]))
        if err:
            fails.append(err)

    if "repair_mode" in expect:
        got = bool(obs.get("repair_mode") or obs.get("repair_reclassified"))
        if got != bool(expect["repair_mode"]):
            fails.append(f"repair_mode_expected_{expect['repair_mode']}_got_{got}")

    if expect.get("no_loop") is True and obs.get("loop_detected"):
        fails.append("loop_detected")

    if expect.get("no_invented_analysis") is True:
        # INVALID fiction must not look like a full confident match analysis
        if obs.get("fixture_quality") not in {"INVALID", None} and obs.get(
            "entity_invalid"
        ) is not True:
            # if explicitly INVALID expected elsewhere, skip
            pass
        summary = _fold(str(obs.get("summary_prefix") or ""))
        invented_markers = (
            "probabilidade de",
            "stake recomendado",
            "melhor mercado",
            "xG=",
            "ve +",
        )
        if obs.get("entity_invalid") is True or obs.get("fixture_quality") == "INVALID":
            if any(m in summary for m in invented_markers):
                fails.append("invented_analysis_on_invalid")

    if expect.get("summary_contains"):
        needle = str(expect["summary_contains"]).lower()
        if needle not in _fold(str(obs.get("summary_prefix") or "")):
            fails.append(f"summary_missing_{needle[:40]}")

    if expect.get("summary_not_contains"):
        needle = str(expect["summary_not_contains"]).lower()
        if needle in _fold(str(obs.get("summary_prefix") or "")):
            fails.append(f"summary_has_forbidden_{needle[:40]}")

    # Frustration flag is observational (user side)
    _ = any(detect_frustration(m) for m in user_messages)

    return (len(fails) == 0), fails, context_preserved


def load_cases(evals_root: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in sorted(evals_root.rglob("cases.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            cases.append(
                {
                    "id": f"load_error_{path.name}",
                    "category": path.parent.name,
                    "steps": [{"message": "noop"}],
                    "expect": {"intent": "__load_error__"},
                    "_load_error": str(exc),
                }
            )
            continue
        items = data if isinstance(data, list) else data.get("cases") or []
        for case in items:
            if isinstance(case, dict):
                case.setdefault("category", path.parent.name)
                cases.append(case)
    return cases


def run_case(client: Any, case: dict[str, Any]) -> EvalResult:
    from tests.evals.schema import validate_case

    cid = str(case.get("id") or "unknown")
    category = str(case.get("category") or "unknown")
    t0 = time.perf_counter()

    schema_errs = validate_case(case)
    if schema_errs or case.get("_load_error"):
        return EvalResult(
            id=cid,
            category=category,
            evaluation_pass=False,
            evaluation_score=0.0,
            evaluation_fail_reason=";".join(schema_errs or [str(case.get("_load_error"))]),
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )

    sid = f"aep_{category}_{cid}_{uuid.uuid4().hex[:8]}"
    steps = list(case.get("steps") or [])
    user_messages = [str(s.get("message") or "") for s in steps]
    last_payload: dict[str, Any] = {}

    try:
        for step in steps:
            msg = str(step.get("message") or "")
            resp = client.post(
                "/aurora/copilot",
                json={"message": msg, "session_id": sid, "debug": True},
            )
            last_payload = resp.json() if resp.status_code == 200 else {
                "intent": "http_error",
                "entities": {},
                "executive_summary": f"HTTP {resp.status_code}",
            }
    except Exception as exc:
        return EvalResult(
            id=cid,
            category=category,
            evaluation_pass=False,
            evaluation_score=0.0,
            evaluation_fail_reason=f"runtime:{exc}",
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )

    obs = _extract_observed(last_payload)
    expect = case.get("expect") if isinstance(case.get("expect"), dict) else {}
    # allow expect_last alias
    if not expect and isinstance(case.get("expect_last"), dict):
        expect = case["expect_last"]

    ok, fails, ctx_pres = evaluate_expectations(
        expect, obs, user_messages=user_messages
    )
    loop = bool(obs.get("loop_detected"))
    frustration = bool(obs.get("frustration_detected")) or any(
        detect_frustration(m) for m in user_messages
    )

    # Score: 1.0 pass, else partial credit for useful signals
    score = 1.0 if ok else 0.0
    if not ok and obs.get("intent") and expect.get("intent"):
        # near-miss intent
        score = 0.25

    return EvalResult(
        id=cid,
        category=category,
        evaluation_pass=ok,
        evaluation_score=score,
        evaluation_fail_reason=";".join(fails) if fails else None,
        loop_detected=loop,
        frustration_detected=frustration,
        context_preserved=ctx_pres,
        observed=obs,
        duration_ms=int((time.perf_counter() - t0) * 1000),
    )


def summarize(results: list[EvalResult]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for r in results if r.evaluation_pass)
    failed = total - passed
    rate = (passed / total * 100.0) if total else 0.0
    avg_score = (sum(r.evaluation_score for r in results) / total) if total else 0.0
    by_cat: dict[str, dict[str, int]] = {}
    for r in results:
        bucket = by_cat.setdefault(r.category, {"pass": 0, "fail": 0})
        if r.evaluation_pass:
            bucket["pass"] += 1
        else:
            bucket["fail"] += 1
    return {
        "total": total,
        "pass": passed,
        "fail": failed,
        "success_rate": round(rate, 1),
        "evaluation_score_avg": round(avg_score, 3),
        "by_category": by_cat,
        "loops": sum(1 for r in results if r.loop_detected),
        "frustration_signals": sum(1 for r in results if r.frustration_detected),
    }
