"""
Phase 7.5 — superficial phrase variation for HCE continuity.

Not an engine. Same meaning, different wording.
Never invents facts. Ownership unchanged.
"""

from __future__ import annotations

from typing import Any


def pick_variant(
    ctx: dict[str, Any] | None,
    family: str,
    variants: list[str],
) -> str:
    """
    Pick next unused variant in family; remember in HCE state.
    Fail-open: returns variants[0].
    """
    if not variants:
        return ""
    try:
        from src.conversation.human_conversation_state import (
            get_hce_state,
            update_hce_state,
        )

        st = get_hce_state(ctx) if isinstance(ctx, dict) else {}
        recent = list(st.get("recent_phrase_keys") or [])
        last_idx = st.get(f"pv_idx_{family}")
        try:
            last_i = int(last_idx) if last_idx is not None else -1
        except Exception:
            last_i = -1

        order = list(range(len(variants)))
        # Rotate starting after last used
        start = (last_i + 1) % len(variants)
        rotated = order[start:] + order[:start]
        chosen_i = rotated[0]
        for i in rotated:
            key = f"{family}:{i}"
            if key not in recent[-8:]:
                chosen_i = i
                break

        text = variants[chosen_i]
        key = f"{family}:{chosen_i}"
        recent = (recent + [key])[-10:]
        if isinstance(ctx, dict):
            update_hce_state(
                ctx,
                recent_phrase_keys=recent,
                **{f"pv_idx_{family}": chosen_i},
            )
        return text
    except Exception:
        return variants[0]
