"""
Human Conversation State — lightweight turn memory that SURVIVES sport hard-block.

Separate from sport conversation_state / conversation_focus.
Additive. Fail-open. Does not invent fixtures.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

STATE_KEY = "human_conversation_state"
TTL_SECONDS = 45 * 60


def get_hce_state(ctx: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(ctx, dict):
        return {}
    st = ctx.get(STATE_KEY)
    if not isinstance(st, dict):
        return {}
    ts = float(st.get("updated_at") or 0)
    if ts and (time.time() - ts) > TTL_SECONDS:
        ctx.pop(STATE_KEY, None)
        return {}
    return dict(st)


def update_hce_state(ctx: dict[str, Any] | None, **fields: Any) -> dict[str, Any]:
    if not isinstance(ctx, dict):
        return {}
    st = get_hce_state(ctx)
    for k, v in fields.items():
        if v is None:
            # Explicit clear (short-cancel / topic end)
            st.pop(k, None)
            continue
        st[k] = v
    st["updated_at"] = time.time()
    # keep last few user lines for continuity (not sport focus)
    hist = list(st.get("recent_user") or [])
    umsg = fields.get("last_user_message")
    if umsg:
        hist.append(str(umsg)[:160])
        st["recent_user"] = hist[-8:]
    ctx[STATE_KEY] = st
    return st


def clear_hce_expectation(ctx: dict[str, Any] | None) -> None:
    if not isinstance(ctx, dict):
        return
    st = get_hce_state(ctx)
    st.pop("last_expected_action", None)
    st.pop("pending_question", None)
    st["updated_at"] = time.time()
    ctx[STATE_KEY] = st


def note_assistant_question(
    ctx: dict[str, Any] | None,
    question: str,
    *,
    expected_action: str,
    topic: str | None = None,
) -> None:
    """Aurora asked something — short answers should resolve against this."""
    update_hce_state(
        ctx,
        last_question=question,
        pending_question=question,
        last_expected_action=expected_action,
        last_topic=topic or get_hce_state(ctx).get("last_topic"),
        last_intent="awaiting_user",
    )


def note_sport_turn(
    ctx: dict[str, Any] | None,
    *,
    entity: str | None = None,
    topic: str = "sport",
    expected: list[str] | None = None,
    live: bool = False,
) -> None:
    update_hce_state(
        ctx,
        last_topic=topic,
        last_intent="sport",
        last_entity=entity,
        last_expected_action="sport_followup" if entity else None,
        expectation_hints=expected
        or (
            ["placar", "minuto", "estatisticas", "pressao", "mercados"]
            if live
            else ["resumo", "mercados", "confianca"]
        ),
        is_live=live,
    )
