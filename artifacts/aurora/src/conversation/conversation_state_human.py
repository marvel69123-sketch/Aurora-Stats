"""
Compatibility alias for perception conversation state schema.

Sports short-term memory remains in `conversation_state.py` (untouched).
Human perception goal persistence lives here as requested field surface:

  current_goal, previous_goal, entities, frustration_level,
  clarify_count, repair_count, state_streak
"""

from __future__ import annotations

from src.conversation.perception_conversation_state import (  # noqa: F401
    CTX_KEY,
    anti_sticky_reply,
    build_goal_answer,
    clarify_or_unknown_expired,
    current_goal_text,
    get_perception_state,
    is_frustration,
    is_short_message,
    menus_disabled,
    note_state,
    note_user_message,
    set_goal,
    should_assume_after_clarify,
    should_reanswer_after_repair,
    stamp_entities,
)

# Explicit schema export for docs / tests
CONVERSATION_STATE_FIELDS = (
    "current_goal",
    "previous_goal",
    "entities",
    "frustration_level",
    "clarify_count",
    "repair_count",
    "state_streak",
)
