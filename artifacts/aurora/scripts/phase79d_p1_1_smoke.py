"""
FASE 7.9-D — Smoke P1-1 (forced ownership finalization).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.conversation.emotional_presence import try_emotional_presence
from src.conversation.general_assistant import try_general_assistant
from src.conversation.human_conversation_engine import try_human_conversation
from src.conversation.master_intent_router import apply_master_intent
from src.conversation.natural_response_engine import (
    apply_natural_response,
    try_natural_social_payload,
)
from src.conversation.natural_response_filter import filter_or_regenerate
from src.conversation.turn_ownership import (
    can_presence_claim,
    finalize_early_ownership,
    finalize_forced_ownership,
    finalize_presence_ownership,
    get_owner,
    is_rewrite_locked,
    note_overwrite_blocked,
)


def _early_stack(message: str, ctx: dict[str, Any]) -> dict[str, Any] | None:
    master = apply_master_intent(message, ctx)
    ga = None
    if not master.allow_sport_pipeline:
        ga = try_general_assistant(message, master.intent, ctx)
        if ga:
            txt = str(ga.get("executive_summary") or "")
            txt = filter_or_regenerate(
                txt, master_intent=master.intent, ctx=ctx, regenerate=txt
            )
            ga = dict(ga)
            ga["executive_summary"] = txt
            ga["final_recommendation"] = txt
    hce = try_human_conversation(
        message, ctx, master_intent=master.intent, existing_payload=ga
    )
    payload = hce or ga
    if payload is None:
        payload = try_natural_social_payload(message, ctx)
    elif payload is not None:
        payload = apply_natural_response(message, payload, ctx) or payload
    if payload is not None:
        payload = finalize_early_ownership(payload) or payload
    if can_presence_claim(payload):
        emo = try_emotional_presence(message, ctx, None)
        if emo:
            payload = emo
    if payload is not None:
        payload = finalize_presence_ownership(payload) or payload
    return payload, master


def simulate(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    payload, master = _early_stack(message, ctx)
    sport_ok = bool(master.allow_sport_pipeline)
    forced = False
    owner_before_forced = get_owner(payload) if payload else None

    # Mirror router: forced when !sport_ok and payload is None
    if not sport_ok and payload is None:
        forced = True
        ga = try_general_assistant(message, master.intent or "GENERAL_CHAT", ctx)
        payload = ga or {
            "intent": "general_chat",
            "entities": {
                "general_assistant": True,
                "assistant_kind": "general",
                "fallback": True,
                "fallback_source": "forced_general_incomplete",
            },
            "executive_summary": "Entendi. Posso te ajudar com isso de forma direta.",
            "final_recommendation": "Entendi. Posso te ajudar com isso de forma direta.",
            "best_markets": [],
            "match": None,
            "is_live": False,
            "brain": {},
        }
        payload = finalize_forced_ownership(payload) or payload

    # Competing layer attempt (metric: overwrite blocked when locked)
    overwrite_blocked = False
    if payload is not None and is_rewrite_locked(payload):
        note_overwrite_blocked(payload, layer="LateFilterProbe")
        overwrite_blocked = True

    return {
        "message": message,
        "intent": master.intent,
        "sport_ok": sport_ok,
        "forced": forced,
        "owner_before_forced": owner_before_forced or "none",
        "owner_final": get_owner(payload) or "none",
        "locked": is_rewrite_locked(payload),
        "source": get_owner(payload) or "none",
        "overwrite_blocked": overwrite_blocked,
        "summary": str((payload or {}).get("executive_summary") or "")[:140],
        "forced_flag": bool(((payload or {}).get("entities") or {}).get("forced_nonsport")),
    }


def main() -> int:
    print("FASE 7.9-D P1-1 SMOKE — forced ownership")
    print()

    # Unit: incomplete forced shell (CR4 path)
    incomplete = {
        "intent": "general_chat",
        "entities": {
            "general_assistant": True,
            "assistant_kind": "general",
            "fallback_source": "forced_general_incomplete",
        },
        "executive_summary": "Entendi.",
        "final_recommendation": "Entendi.",
        "best_markets": [],
    }
    before_owner = get_owner(incomplete)
    after = finalize_forced_ownership(dict(incomplete))
    print("=== Forced incomplete shell ===")
    print(f"  before owner={before_owner} locked=False")
    print(
        f"  after  owner={get_owner(after)} locked={is_rewrite_locked(after)} "
        f"forced={((after or {}).get('entities') or {}).get('forced_nonsport')}"
    )
    unit_ok = get_owner(after) == "GA" and is_rewrite_locked(after)

    # MEMORY_QUERY → GA returns None → forced path in router mirror
    print()
    print("=== Forced path via MEMORY (payload None) ===")
    mem = simulate("qual é meu nome", {})
    print(
        f"  forced={mem['forced']} owner={mem['owner_final']} locked={mem['locked']} "
        f"forced_flag={mem['forced_flag']} overwrite_blocked={mem['overwrite_blocked']}"
    )
    # If HCE claimed memory early, still prove forced finalize on shell
    if not mem["forced"]:
        shell = finalize_forced_ownership(
            {
                "intent": "general_chat",
                "entities": {
                    "general_assistant": True,
                    "assistant_kind": "general",
                    "fallback_source": "forced_general_incomplete",
                },
                "executive_summary": "Entendi.",
                "final_recommendation": "Entendi.",
                "best_markets": [],
            }
        )
        mem_ok = get_owner(shell) == "GA" and is_rewrite_locked(shell)
        print(
            f"  (early claimed — shell finalize) owner={get_owner(shell)} "
            f"locked={is_rewrite_locked(shell)}"
        )
    else:
        mem_ok = mem["locked"] and mem["owner_final"] != "none"

    probes = [
        "quais jogos estão ao vivo?",
        "que horas são?",
        "Cabo Verde",
        "pesquisa simples",
        "estou triste",
        "aurora é minha maior criação",
        "vc está em loop",
        "oi",
    ]
    print()
    print("=== Probes ===")
    ctx: dict[str, Any] = {}
    rows = []
    for msg in probes:
        # fresh ctx per probe except loop needs hist — use fresh each for isolation
        r = simulate(msg, {})
        rows.append(r)
        print(
            f"  [{msg!r}] forced={r['forced']} owner={r['owner_final']} "
            f"locked={r['locked']} overwrite_blocked={r['overwrite_blocked']} "
            f"source={r['source']}"
        )
        print(f"       {r['summary'][:100]}")

    locked_n = sum(1 for r in rows if r["locked"])
    print()
    print("MÉTRICAS")
    print(f"  unit_forced_incomplete_ok={unit_ok}")
    print(f"  memory_forced_ok={mem_ok}")
    print(f"  probes_locked={locked_n}/{len(rows)}")
    print(f"  forced_path_hits={sum(1 for r in rows if r['forced']) + (1 if mem['forced'] else 0)}")
    return 0 if unit_ok and mem_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
