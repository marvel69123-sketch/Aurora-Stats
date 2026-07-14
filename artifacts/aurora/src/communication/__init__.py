"""Phase 6 — Personality & Communication Layer (presentation only)."""

from src.communication.personality_layer import (
    AURORA_TAGLINE,
    official_greeting_recommendation,
    official_greeting_summary,
    polish_payload,
)
from src.communication.small_talk import is_social_message, try_small_talk

__all__ = [
    "AURORA_TAGLINE",
    "official_greeting_summary",
    "official_greeting_recommendation",
    "polish_payload",
    "is_social_message",
    "try_small_talk",
]
