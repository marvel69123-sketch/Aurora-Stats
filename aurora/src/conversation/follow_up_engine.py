"""Re-export follow-up API from core (Phase 5B path compatibility)."""

from src.core.follow_up_engine import (  # noqa: F401
    is_followup,
    resolve,
    _detect_followup_type,
)

__all__ = ["is_followup", "resolve", "_detect_followup_type"]
