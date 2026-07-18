"""
Simulator engine — runs persona scripts against /aurora/copilot.

Simulation-only. Does not modify Aurora engines.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from tests.simulator.detectors import (
    conversation_failed,
    detect_turn_failures,
    extract_turn_obs,
    first_failure_turn,
)
from tests.simulator.personas import Script


@dataclass
class TurnResult:
    index: int
    message: str
    tag: str
    observed: dict[str, Any]
    flags: dict[str, bool]
    duration_ms: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConversationResult:
    run_id: str
    persona_id: str
    persona_name: str
    seed: int
    success: bool
    turns: list[TurnResult] = field(default_factory=list)
    failure_turn: int | None = None
    failure_reasons: list[str] = field(default_factory=list)
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "persona_id": self.persona_id,
            "persona_name": self.persona_name,
            "seed": self.seed,
            "success": self.success,
            "failure_turn": self.failure_turn,
            "failure_reasons": self.failure_reasons,
            "duration_ms": self.duration_ms,
            "turns": [t.to_dict() for t in self.turns],
        }


def _reasons_from_flags(flags: dict[str, bool]) -> list[str]:
    return [k for k, v in flags.items() if v]


def run_conversation(client: Any, script: Script) -> ConversationResult:
    t0 = time.perf_counter()
    sid = f"sim_{script.persona_id}_{script.seed}_{uuid.uuid4().hex[:8]}"
    run_id = f"{script.persona_id}_{script.seed}"
    turns_out: list[TurnResult] = []
    flag_list: list[dict[str, bool]] = []
    prior_intents: list[str] = []
    had_sport_context = False
    all_reasons: list[str] = []

    for i, turn in enumerate(script.turns, start=1):
        tt0 = time.perf_counter()
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

        obs = extract_turn_obs(payload, turn.message)
        flags = detect_turn_failures(
            obs,
            expect=turn.expect,
            prior_intents=prior_intents,
            had_sport_context=had_sport_context,
        )
        reasons = _reasons_from_flags(flags)
        all_reasons.extend(reasons)
        flag_list.append(flags)

        intent = str(obs.get("intent") or "")
        if intent in {"analyze_match", "follow_up"} or obs.get("pronoun_resolved"):
            had_sport_context = True
        if turn.tag in {"fixture", "fiction"}:
            had_sport_context = True
        prior_intents.append(intent)

        turns_out.append(
            TurnResult(
                index=i,
                message=turn.message,
                tag=turn.tag,
                observed=obs,
                flags=flags,
                duration_ms=int((time.perf_counter() - tt0) * 1000),
            )
        )

    failed = conversation_failed(flag_list)
    return ConversationResult(
        run_id=run_id,
        persona_id=script.persona_id,
        persona_name=script.persona_name,
        seed=script.seed,
        success=not failed,
        turns=turns_out,
        failure_turn=first_failure_turn(flag_list) if failed else None,
        failure_reasons=sorted(set(all_reasons)),
        duration_ms=int((time.perf_counter() - t0) * 1000),
    )
