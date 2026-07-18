"""Run frustration scenarios against /aurora/copilot (analytics only)."""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from tests.frustration.scenarios import FrustScript


@dataclass
class FrustTurnResult:
    index: int
    message: str
    tag: str
    frustration_detected: bool
    frustration_type: str | None
    frustration_score: float | None
    recovered_after_frustration: bool | None
    recovery_turns: int | None
    intent: str | None
    summary_prefix: str
    duration_ms: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FrustSessionResult:
    session_id: str
    script_id: str
    script_name: str
    seed: int
    had_frustration: bool
    recovered: bool | None
    frustration_types: list[str] = field(default_factory=list)
    turns_until_frustration: int | None = None
    repeated_frustration: bool = False
    recovery_turns: int | None = None
    turns: list[FrustTurnResult] = field(default_factory=list)
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "script_id": self.script_id,
            "script_name": self.script_name,
            "seed": self.seed,
            "had_frustration": self.had_frustration,
            "recovered": self.recovered,
            "frustration_types": self.frustration_types,
            "turns_until_frustration": self.turns_until_frustration,
            "repeated_frustration": self.repeated_frustration,
            "recovery_turns": self.recovery_turns,
            "duration_ms": self.duration_ms,
            "turns": [t.to_dict() for t in self.turns],
        }


def run_frustration_session(client: Any, script: FrustScript) -> FrustSessionResult:
    t0 = time.perf_counter()
    sid = f"frust_{script.id}_{script.seed}_{uuid.uuid4().hex[:8]}"
    turns_out: list[FrustTurnResult] = []
    types: list[str] = []
    turns_until: int | None = None
    recovered: bool | None = None
    recovery_turns: int | None = None
    frust_count = 0

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

        ents = payload.get("entities") or {}
        if not isinstance(ents, dict):
            ents = {}
        detected = bool(ents.get("frustration_detected"))
        ftype = ents.get("frustration_type")
        score = ents.get("frustration_score")
        rec = ents.get("recovered_after_frustration")
        rturns = ents.get("recovery_turns")

        if detected and ftype:
            types.append(str(ftype))
            frust_count += 1
            if turns_until is None:
                turns_until = i
        if rec is True:
            recovered = True
            recovery_turns = int(rturns or 0) or recovery_turns
        elif detected and recovered is None:
            recovered = False

        turns_out.append(
            FrustTurnResult(
                index=i,
                message=turn.message,
                tag=turn.tag,
                frustration_detected=detected,
                frustration_type=str(ftype) if ftype else None,
                frustration_score=float(score) if score is not None else None,
                recovered_after_frustration=rec if isinstance(rec, bool) else None,
                recovery_turns=int(rturns) if rturns is not None else None,
                intent=str(payload.get("intent") or "") or None,
                summary_prefix=str(payload.get("executive_summary") or "")[:200].replace(
                    "\n", " | "
                ),
                duration_ms=int((time.perf_counter() - tt0) * 1000),
            )
        )

    had = frust_count > 0
    if had and recovered is None:
        recovered = False

    return FrustSessionResult(
        session_id=sid,
        script_id=script.id,
        script_name=script.name,
        seed=script.seed,
        had_frustration=had,
        recovered=recovered if had else None,
        frustration_types=types,
        turns_until_frustration=turns_until,
        repeated_frustration=frust_count >= 2,
        recovery_turns=recovery_turns,
        turns=turns_out,
        duration_ms=int((time.perf_counter() - t0) * 1000),
    )
