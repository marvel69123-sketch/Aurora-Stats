"""
Aurora v4.5.2 — Presence Humanization Layer.

Light emoji / enthusiasm polish for social replies.
Uses optional conversation_preferences from the request.
Fail-open. Additive. Does not edit State/CIL/CRL.
"""

from __future__ import annotations

import logging
import random
import re
from typing import Any

logger = logging.getLogger(__name__)

_EMOJI_BY_FAMILY: dict[str, list[str]] = {
    "greeting": ["😊", "✨", "👋"],
    "wellbeing": ["😊", "✨", "👍"],
    "thanks": ["😊", "👍", "✨"],
    "farewell": ["👋", "✨"],
    "farewell_night": ["🌙", "✨", "😊"],
    "casual": ["⚽", "✨", "😊"],
    "calendar": ["⚽", "📅"],
    "team_opinion": ["⚽", "✨"],
    "capabilities": ["✨", "⚽"],
}


def normalize_prefs(raw: dict[str, Any] | None) -> dict[str, str]:
    raw = raw or {}
    emojis = str(raw.get("emojis") or raw.get("emoji_level") or "none").lower()
    enthusiasm = str(raw.get("enthusiasm") or raw.get("enthusiasm_level") or "medium").lower()
    structure = str(raw.get("structure") or raw.get("structure_level") or "balanced").lower()
    detail = str(raw.get("detail") or raw.get("detail_level") or "normal").lower()
    if emojis not in {"none", "low", "medium", "high"}:
        emojis = "none"
    if enthusiasm not in {"low", "medium", "high"}:
        enthusiasm = "medium"
    if structure not in {"conversational", "balanced", "technical"}:
        structure = "balanced"
    if detail not in {"short", "normal", "detailed"}:
        detail = "normal"
    return {
        "emojis": emojis,
        "enthusiasm": enthusiasm,
        "structure": structure,
        "detail": detail,
    }


def _detect_family(text: str, hint: str | None = None) -> str:
    if hint and hint in _EMOJI_BY_FAMILY:
        return hint
    low = (text or "").lower()
    if any(x in low for x in ("boa noite", "até amanhã", "ate amanha", "falou", "até logo")):
        if "noite" in low or "🌙" in text:
            return "farewell_night"
        return "farewell"
    if any(x in low for x in ("obrigad", "valeu", "disponha", "por nada")):
        return "thanks"
    if any(x in low for x in ("tudo certo", "tudo bem", "por aqui")):
        return "wellbeing"
    if low.startswith("oi") or "bom te ver" in low:
        return "greeting"
    return "casual"


def _should_add_emoji(prefs: dict[str, str]) -> bool:
    level = prefs.get("emojis") or "none"
    if level == "none":
        return False
    if level == "low":
        return random.random() < 0.25
    if level == "medium":
        return random.random() < 0.65
    return True  # high


def _enthusiasm_boost(text: str, prefs: dict[str, str], family: str) -> str:
    """Light enthusiasm without rewriting the whole message."""
    if prefs.get("enthusiasm") != "high":
        return text
    body = (text or "").strip()
    if not body:
        return body
    # Avoid double-boost
    if any(x in body.lower() for x in ("demais", "adoro", "super bem", "animada")):
        return body
    if family == "wellbeing" and body.lower().startswith("tudo"):
        # "Tudo certo por aqui" → warmer
        if "obrigad" in body.lower():
            return body.replace("obrigada por perguntar.", "obrigada por perguntar — fico feliz!").replace(
                "obrigado por perguntar.", "obrigado por perguntar — fico feliz!"
            )
        if not body.endswith("!") and not body.endswith("?"):
            return body.rstrip(".") + "!"
    if family == "greeting" and body.lower().startswith("oi") and prefs.get("enthusiasm") == "high":
        if "!" not in body[:8]:
            return body.replace("Oi!", "Oi!", 1) if body.startswith("Oi!") else ("Oi! " + body[3:].lstrip() if body.lower().startswith("oi ") else body)
    return body


def apply_presence_humanization(
    text: str,
    prefs: dict[str, Any] | None = None,
    *,
    family_hint: str | None = None,
) -> str:
    """
    Optionally append one light emoji and soften enthusiasm.
    Never invents markets. Fail-open → original text.
    """
    try:
        body = (text or "").strip()
        if not body:
            return body
        p = normalize_prefs(prefs if isinstance(prefs, dict) else None)
        family = _detect_family(body, family_hint)
        body = _enthusiasm_boost(body, p, family)

        # Already has emoji — don't stack
        if re.search(r"[\U0001F300-\U0001FAFF]", body):
            return body

        if not _should_add_emoji(p):
            return body

        opts = list(_EMOJI_BY_FAMILY.get(family) or _EMOJI_BY_FAMILY["casual"])
        emoji = random.choice(opts)
        # Prefer trailing emoji on last line
        lines = body.split("\n")
        last = lines[-1].rstrip()
        if last.endswith((".", "!", "?")):
            lines[-1] = last + f" {emoji}"
        else:
            lines[-1] = last + f" {emoji}"
        return "\n".join(lines)
    except Exception as exc:
        logger.warning("presence_humanization fail-open: %s", exc)
        return text
