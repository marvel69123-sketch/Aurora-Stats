#!/usr/bin/env python3
"""Phase 8.2-E — full-pipeline opinion routing (Recovery → HIE → Natural → Fallback)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.conversation.brain_authority import (  # noqa: E402
    is_calendar_authority,
    natural_may_emit_opinion,
)
from src.conversation.context_recovery import (  # noqa: E402
    apply_recovery_to_message,
    recover_context,
)
from src.conversation.human_inference import apply_human_inference  # noqa: E402
from src.conversation.intelligence_fallback import (  # noqa: E402
    try_intelligence_fallback,
)
from src.conversation.master_intent_router import apply_master_intent  # noqa: E402
from src.conversation.natural_conversation import (  # noqa: E402
    detect_natural_intent,
    try_natural_conversation,
)
from src.conversation.response_review import run_deep_thinking_engine  # noqa: E402


async def full_path(msg: str, ctx: dict | None = None) -> dict:
    ctx = dict(ctx or {})
    ctx["raw_user_message"] = msg
    apply_master_intent(msg, ctx)
    rec = recover_context(msg, ctx)
    msg_r = apply_recovery_to_message(msg, ctx, min_confidence=0.7)
    run_deep_thinking_engine(msg_r, ctx, recovery=rec.to_dict())
    msg2, inf = apply_human_inference(msg_r, ctx)
    nat = await try_natural_conversation(msg2, ctx, {"emojis": "none"})
    fb = None
    if nat is None:
        fb = try_intelligence_fallback(msg2, ctx, {"emojis": "none"})
    elif not (nat.get("entities") or {}).get("opinion_time"):
        # same as router: intel may still claim if unlocked — check what it would emit
        fb = try_intelligence_fallback(msg2, ctx, {"emojis": "none"})
    return {
        "recovered": msg_r,
        "hie_intent": inf.intent if inf else None,
        "hie_topic": inf.topic_kind if inf else None,
        "calendar_auth": is_calendar_authority(ctx),
        "may_opinion": natural_may_emit_opinion(ctx),
        "detect": (detect_natural_intent(msg2) or {}).get("kind"),
        "detect_recent": (detect_natural_intent(msg2) or {}).get("recent_match"),
        "nat_kind": (nat or {}).get("entities", {}).get("natural_kind") if nat else None,
        "opinion_time": (nat or {}).get("entities", {}).get("opinion_time") if nat else None,
        "fallback_kind": (fb or {}).get("entities", {}).get("fallback_kind") if fb else None,
        "nat": nat,
        "fb": fb,
    }


def main() -> int:
    failures: list[str] = []

    opinion_cases = [
        "o que você achou do jogo do fluminense ontem?",
        "como foi a partida do flamengo?",
        "o flamengo jogou bem?",
        "o que você achou da atuação do flamengo?",
        "como você viu o último jogo do santos?",
    ]
    agenda_cases = [
        "quando é o próximo jogo?",
        "tem jogo hoje?",
        "tem jogo do fluminense hoje?",
        "proximo jogo do palmeiras",
    ]

    print("=== OPINION (full pipeline) ===")
    for msg in opinion_cases:
        r = asyncio.run(full_path(msg))
        fb = r["fallback_kind"]
        ok = (
            r["hie_topic"] == "opinion"
            and r["may_opinion"] is True
            and fb != "calendar_authority"
            and (
                r["nat_kind"] == "team_opinion"
                or r["detect"] == "team_opinion"
                or (r["opinion_time"] is True)
            )
        )
        # Strong success: natural opinion_time True and never calendar_authority
        strong = r["opinion_time"] is True and fb != "calendar_authority"
        status = "OK" if (ok or strong) else "FAIL"
        if status == "FAIL":
            failures.append(msg)
        print(
            f"  [{status}] {msg!r}\n"
            f"       recovered={r['recovered']!r} hie={r['hie_intent']}/{r['hie_topic']}\n"
            f"       may_op={r['may_opinion']} nat={r['nat_kind']} "
            f"opinion_time={r['opinion_time']} fb={fb} detect={r['detect']} recent={r['detect_recent']}"
        )
        if not strong and ok:
            # prefer natural opinion_time for criterion
            if r["opinion_time"] is not True:
                failures.append(f"weak opinion_time for {msg!r}")

    print("=== AGENDA (must stay calendar) ===")
    for msg in agenda_cases:
        r = asyncio.run(full_path(msg))
        # Agenda: not forced into opinion via recent_match steal
        stolen = r["hie_topic"] == "opinion" and "achou" not in msg.lower() and "como foi" not in msg.lower()
        # For pure agenda, calendar path or calendar detect is OK; calendar_authority OK
        ok = r["hie_topic"] in {"calendar", "fixture", "kickoff", None} or r[
            "detect"
        ] in {"team_calendar", "calendar_today", "calendar_tomorrow", "kickoff_lookup", None}
        # "quando é o próximo jogo?" may have no team — still not opinion
        ok = ok and r["hie_topic"] != "opinion"
        status = "OK" if ok else "FAIL"
        if not ok:
            failures.append(msg)
        print(
            f"  [{status}] {msg!r} hie={r['hie_intent']}/{r['hie_topic']} "
            f"detect={r['detect']} fb={r['fallback_kind']}"
        )

    print()
    if failures:
        print(f"FAIL ({len(failures)})")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS — 8.2-E opinion routing (full pipeline)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
