"""
FASE 7.9-A — Smoke P0-1 (ensure_soft_sections).
Sem alterar comportamento além do anti-KeyError.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.conversation.ensure_soft_sections import ensure_soft_sections
from src.conversation.general_assistant import try_general_assistant
from src.conversation.human_conversation_engine import try_human_conversation
from src.conversation.master_intent_router import apply_master_intent
from src.conversation.natural_response_engine import (
    apply_natural_response,
    try_natural_social_payload,
)
from src.conversation.turn_ownership import finalize_early_ownership


def _build_forced_incomplete() -> dict[str, Any]:
    return {
        "intent": "general_chat",
        "entities": {"general_assistant": True, "assistant_kind": "general"},
        "executive_summary": "Entendi. Posso te ajudar com isso de forma direta.",
        "final_recommendation": "Entendi. Posso te ajudar com isso de forma direta.",
        "best_markets": [],
        "match": None,
        "is_live": False,
        "brain": {},
    }


def _simulate_builder(payload: dict[str, Any]) -> tuple[bool, str]:
    """Mirrors CopilotResponse confidence/risk/bankroll access."""
    try:
        payload = ensure_soft_sections(payload) or payload
        _ = payload["confidence"]
        _ = payload["risk"]
        _ = payload["bankroll_recommendation"]
        # pydantic-like required keys
        assert isinstance(payload["confidence"]["score"], (int, float))
        assert "label" in payload["confidence"]
        return True, "ok"
    except KeyError as exc:
        return False, f"KeyError:{exc}"
    except Exception as exc:
        return False, f"{type(exc).__name__}:{exc}"


def _early_reply(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    master = apply_master_intent(message, ctx)
    ga = None
    if not master.allow_sport_pipeline:
        ga = try_general_assistant(message, master.intent, ctx)
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
    if payload is None:
        # sport stub or empty — still run ensure path
        payload = {
            "intent": "unknown",
            "executive_summary": f"[no early payload] intent={master.intent}",
            "final_recommendation": "",
            "entities": {},
            "best_markets": [],
            "is_live": False,
        }
    # Always pass through P0-1 before "builder"
    payload = ensure_soft_sections(payload) or payload
    return {
        "message": message,
        "intent": master.intent,
        "summary": str(payload.get("executive_summary") or "")[:160],
        "has_confidence": isinstance(payload.get("confidence"), dict),
        "builder_ok": _simulate_builder(dict(payload))[0],
    }


def main() -> int:
    print("FASE 7.9-A P0-1 SMOKE")
    print()

    # Unit: incomplete forced payload
    incomplete = _build_forced_incomplete()
    before = "confidence" in incomplete
    ok, detail = _simulate_builder(incomplete)
    print("=== KeyError guard (forced incomplete) ===")
    print(f"  had_confidence_before_ensure: {before}")
    print(f"  builder_ok_after_ensure: {ok} ({detail})")
    print(f"  confidence_label: {incomplete.get('confidence', {}).get('label')}")
    print()

    probes = [
        "que horas são?",
        "quais jogos estão ao vivo?",
        "estou triste",
        "vc está em loop",
        "oi",
    ]
    print("=== Probes ===")
    ctx: dict[str, Any] = {}
    all_ok = ok
    for msg in probes:
        row = _early_reply(msg, ctx)
        all_ok = all_ok and row["builder_ok"]
        print(
            f"  [{ 'OK' if row['builder_ok'] else 'FAIL' }] "
            f"{msg!r} intent={row['intent']} conf={row['has_confidence']}"
        )
        print(f"       {row['summary'][:120]}")

    print()
    print(f"KeyError eliminado: {'SIM' if all_ok else 'NÃO'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
