"""
AEP Phase 3 — Frustration observability (stamp-only).

Detects user frustration signals, classifies likely cause, tracks recovery.
Does not alter reply text, engines, ownership, or routing decisions.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

CTX_KEY = "frustration_analytics"

# Canonical categories
MISUNDERSTANDING = "MISUNDERSTANDING"
LOST_CONTEXT = "LOST_CONTEXT"
TOO_GENERIC = "TOO_GENERIC"
WRONG_INTENT = "WRONG_INTENT"
REPETITION = "REPETITION"
INVALID_RESPONSE = "INVALID_RESPONSE"
OVER_REFUSAL = "OVER_REFUSAL"
HALLUCINATION_RISK = "HALLUCINATION_RISK"

CATEGORIES = (
    MISUNDERSTANDING,
    LOST_CONTEXT,
    TOO_GENERIC,
    WRONG_INTENT,
    REPETITION,
    INVALID_RESPONSE,
    OVER_REFUSAL,
    HALLUCINATION_RISK,
)

# (folded substring / pattern, default category, score)
_MARKER_SPECS: list[tuple[str, str, float]] = [
    ("voce nao entendeu", MISUNDERSTANDING, 0.9),
    ("nao entendeu", MISUNDERSTANDING, 0.85),
    ("nao foi isso", WRONG_INTENT, 0.85),
    ("preste atencao", MISUNDERSTANDING, 0.8),
    ("releia", MISUNDERSTANDING, 0.75),
    ("pensa um pouco", MISUNDERSTANDING, 0.8),
    ("pensa", MISUNDERSTANDING, 0.55),
    ("nao respondeu", INVALID_RESPONSE, 0.85),
    ("isso esta errado", HALLUCINATION_RISK, 0.85),
    ("esta errado", WRONG_INTENT, 0.7),
    ("aff", TOO_GENERIC, 0.65),
    ("hã?", MISUNDERSTANDING, 0.7),
    ("ha?", MISUNDERSTANDING, 0.65),
    ("???", TOO_GENERIC, 0.7),
]

_LOOP_MARKERS = (
    "entendi. posso te ajudar com isso de forma direta",
    "diz o objetivo em uma frase",
)


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def get_frustration_state(ctx: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(ctx, dict):
        return {}
    raw = ctx.get(CTX_KEY)
    return dict(raw) if isinstance(raw, dict) else {}


def detect_frustration_signal(message: str | None) -> dict[str, Any] | None:
    """Return hit dict or None for a user message."""
    folded = _fold(message or "")
    if not folded:
        return None
    # Bare ??? 
    if folded in {"???", "??", "?"} or folded.endswith("???"):
        return {
            "frustration_detected": True,
            "frustration_type": TOO_GENERIC,
            "frustration_score": 0.7,
            "marker": "???",
        }
    best: dict[str, Any] | None = None
    for marker, category, score in _MARKER_SPECS:
        if marker in folded:
            hit = {
                "frustration_detected": True,
                "frustration_type": category,
                "frustration_score": score,
                "marker": marker,
            }
            if best is None or score > float(best["frustration_score"]):
                best = hit
    return best


def _prior_was_generic(ctx: dict[str, Any]) -> bool:
    state = get_frustration_state(ctx)
    last = str(state.get("last_assistant_prefix") or "").lower()
    return any(m in last for m in _LOOP_MARKERS) or len(last.strip()) < 12


def _prior_lost_context(ctx: dict[str, Any]) -> bool:
    state = get_frustration_state(ctx)
    return bool(state.get("last_intent") in {"general_chat", "small_talk"})


def refine_category(
    hit: dict[str, Any],
    ctx: dict[str, Any],
    payload: dict[str, Any] | None,
) -> str:
    """Refine classification using prior turn signals (still observational)."""
    base = str(hit.get("frustration_type") or MISUNDERSTANDING)
    if _prior_was_generic(ctx) and base in {MISUNDERSTANDING, TOO_GENERIC}:
        return TOO_GENERIC
    if _prior_lost_context(ctx) and base in {MISUNDERSTANDING, WRONG_INTENT}:
        return LOST_CONTEXT
    ents = (payload or {}).get("entities") if isinstance(payload, dict) else {}
    if isinstance(ents, dict) and ents.get("entity_invalid") and base == HALLUCINATION_RISK:
        return HALLUCINATION_RISK
    # Repeated frustration
    state = get_frustration_state(ctx)
    if int(state.get("frustration_events") or 0) >= 1 and base == MISUNDERSTANDING:
        return REPETITION
    return base


def _reply_looks_recovered(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    summary = str(payload.get("executive_summary") or "").strip()
    if not summary or len(summary) < 24:
        return False
    low = _fold(summary)
    if any(m in low for m in _LOOP_MARKERS):
        return False
    if low in {"?", "…", "...", "."}:
        return False
    # Repair / capabilities / follow-up / sport continuity count as recovery attempts
    intent = str(payload.get("intent") or "")
    ents = payload.get("entities") or {}
    if not isinstance(ents, dict):
        ents = {}
    if ents.get("repair_mode") or ents.get("conversation_repair"):
        return True
    if ents.get("pronoun_resolved") or ents.get("advanced_fixture_reused"):
        return True
    if ents.get("continuity_followup") or ents.get("followup_context_found"):
        return True
    if intent in {
        "assistant_capabilities",
        "follow_up",
        "analyze_match",
        "match_opinion",
    }:
        return True
    # Non-loop substantive text
    return len(summary) >= 40


def note_frustration_observability(
    ctx: dict[str, Any] | None,
    message: str,
    payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """
    Update session frustration state and stamp observability fields on payload.
    Never changes executive_summary / recommendations.
    """
    if not isinstance(ctx, dict) or not isinstance(payload, dict):
        return payload
    try:
        state = get_frustration_state(ctx)
        out = dict(payload)
        ents = dict(out.get("entities") or {})

        # Recovery tracking for a prior open frustration
        pending = state.get("pending")
        if isinstance(pending, dict) and pending.get("active"):
            turns = int(pending.get("turns_since") or 0) + 1
            pending["turns_since"] = turns
            if _reply_looks_recovered(out):
                ents["frustration_detected"] = True
                ents["frustration_type"] = pending.get("type")
                ents["frustration_score"] = pending.get("score")
                ents["recovered_after_frustration"] = True
                ents["recovery_turns"] = turns
                state["recoveries"] = int(state.get("recoveries") or 0) + 1
                state["last_recovery_turns"] = turns
                pending["active"] = False
                state["pending"] = pending
                logger.warning(
                    "[AUDIT] FrustrationObservability: RECOVERED type=%s turns=%s",
                    pending.get("type"),
                    turns,
                )
            else:
                ents["recovered_after_frustration"] = False
                ents["recovery_turns"] = turns
                state["pending"] = pending

        # New frustration signal on this user message
        hit = detect_frustration_signal(message)
        if hit:
            category = refine_category(hit, ctx, out)
            score = float(hit["frustration_score"])
            ents["frustration_detected"] = True
            ents["frustration_type"] = category
            ents["frustration_score"] = score
            state["frustration_events"] = int(state.get("frustration_events") or 0) + 1
            causes = list(state.get("causes") or [])
            causes.append(category)
            state["causes"] = causes[-50:]
            # Same-turn recovery if Aurora already corrected in this reply
            if _reply_looks_recovered(out):
                ents["recovered_after_frustration"] = True
                ents["recovery_turns"] = 1
                state["recoveries"] = int(state.get("recoveries") or 0) + 1
                state["last_recovery_turns"] = 1
                state["pending"] = {
                    "active": False,
                    "type": category,
                    "score": score,
                    "turns_since": 1,
                    "marker": hit.get("marker"),
                }
                logger.warning(
                    "[AUDIT] FrustrationObservability: DETECTED+RECOVERED same-turn "
                    "type=%s score=%.2f",
                    category,
                    score,
                )
            else:
                ents["recovered_after_frustration"] = False
                ents["recovery_turns"] = 0
                state["pending"] = {
                    "active": True,
                    "type": category,
                    "score": score,
                    "turns_since": 0,
                    "marker": hit.get("marker"),
                }
                logger.warning(
                    "[AUDIT] FrustrationObservability: DETECTED type=%s score=%.2f marker=%r",
                    category,
                    score,
                    hit.get("marker"),
                )
            state["turns_until_first"] = state.get("turns_until_first") or (
                int(state.get("turn_index") or 0) + 1
            )

        # Book-keeping for next refine
        state["turn_index"] = int(state.get("turn_index") or 0) + 1
        state["last_intent"] = out.get("intent")
        prefix = str(out.get("executive_summary") or "")[:180]
        state["last_assistant_prefix"] = prefix
        ctx[CTX_KEY] = state
        out["entities"] = ents
        return out
    except Exception as exc:
        logger.warning("note_frustration_observability fail-open: %s", exc)
        return payload


def frustration_debug_block(entities: dict[str, Any] | None) -> dict[str, Any] | None:
    """Slice for developer_audit_mode / payload['debug'].frustration."""
    if not isinstance(entities, dict):
        return None
    if not (
        entities.get("frustration_detected")
        or entities.get("recovered_after_frustration") is not None
    ):
        return None
    return {
        "frustration_detected": bool(entities.get("frustration_detected")),
        "frustration_type": entities.get("frustration_type"),
        "frustration_score": entities.get("frustration_score"),
        "recovered_after_frustration": entities.get("recovered_after_frustration"),
        "recovery_turns": entities.get("recovery_turns"),
    }
