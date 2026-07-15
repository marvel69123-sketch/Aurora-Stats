"""Phase 6 — Personality & Communication Layer (presentation only)."""

from src.communication.match_card import (
    AURORA_MATCH_VERSION,
    attach_match_card,
    build_match_card_from_analyze,
    build_match_card_from_live_fixture,
    build_predictability,
)
from src.communication.personality_layer import (
    AURORA_TAGLINE,
    official_greeting_recommendation,
    official_greeting_summary,
    polish_payload,
)
from src.communication.small_talk import is_social_message, try_small_talk

__all__ = [
    "AURORA_TAGLINE",
    "AURORA_MATCH_VERSION",
    "official_greeting_summary",
    "official_greeting_recommendation",
    "polish_payload",
    "is_social_message",
    "try_small_talk",
    "build_match_card_from_analyze",
    "build_match_card_from_live_fixture",
    "build_predictability",
    "attach_match_card",
]
