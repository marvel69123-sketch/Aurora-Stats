"""
Aurora v4.8 — Presence Humanization Layer (personality prefs actually apply).

emojis | enthusiasm | structure | detail — all influence narrative.
Fail-open. Additive. Does not edit State/CIL/CRL/engines.
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
    "team_opinion": ["⚽", "✨", "😊"],
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
        return random.random() < 0.35
    if level == "medium":
        return random.random() < 0.75
    return True


def _enthusiasm_boost(text: str, prefs: dict[str, str], family: str) -> str:
    level = prefs.get("enthusiasm") or "medium"
    body = (text or "").strip()
    if not body:
        return body
    if level == "low":
        # Soften exclamation spam
        return re.sub(r"!{2,}", "!", body)
    if level == "medium":
        return body
    # high — warmer
    if any(x in body.lower() for x in ("demais", "adoro", "super bem", "animada")):
        return body
    if family == "wellbeing":
        if "obrigad" in body.lower() and "feliz" not in body.lower():
            body = body.replace(
                "obrigada por perguntar.",
                "obrigada por perguntar — fico feliz!",
            ).replace(
                "obrigado por perguntar.",
                "obrigado por perguntar — fico feliz!",
            )
        if not body.endswith("!") and not body.endswith("?"):
            body = body.rstrip(".") + "!"
        return body
    if family in {"greeting", "thanks", "casual", "team_opinion"}:
        if not body.endswith(("!", "?", "😊", "⚽", "✨")) and random.random() < 0.55:
            if body.endswith("."):
                body = body[:-1] + "!"
            else:
                body = body + "!"
        if family == "team_opinion" and not body.lower().startswith(
            ("olha", "cara", "então", "entao", "hmm", "pensei")
        ):
            if random.random() < 0.4:
                body = "Olha… " + body[0].lower() + body[1:] if len(body) > 1 else body
    return body


def _apply_structure(text: str, prefs: dict[str, str]) -> str:
    structure = prefs.get("structure") or "balanced"
    body = (text or "").strip()
    if not body or structure == "balanced":
        return body
    if structure == "conversational":
        # Prefer flowing prose: soften markdown-ish headers
        body = re.sub(r"^#+\s*", "", body, flags=re.M)
        body = re.sub(r"\*\*([^*]+)\*\*", r"\1", body)
        return body
    if structure == "technical":
        # Keep / lightly encourage clearer breaks between ideas
        if "\n\n" not in body and len(body) > 220:
            # Split on sentence boundary once for readability
            parts = re.split(r"(?<=[.!?])\s+", body)
            if len(parts) >= 4:
                mid = len(parts) // 2
                body = " ".join(parts[:mid]) + "\n\n" + " ".join(parts[mid:])
        return body
    return body


def _apply_detail(text: str, prefs: dict[str, str], family: str) -> str:
    detail = prefs.get("detail") or "normal"
    body = (text or "").strip()
    if not body:
        return body
    if detail == "short":
        # Keep at most 2 paragraphs for social/opinion
        if family in {"greeting", "wellbeing", "thanks", "farewell", "farewell_night"}:
            parts = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
            return "\n\n".join(parts[:1]) if parts else body
        parts = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        if len(parts) > 2:
            return "\n\n".join(parts[:2])
        if len(body) > 520:
            return body[:520].rsplit(" ", 1)[0].rstrip(".,;") + "…"
        return body
    if detail == "detailed":
        # Don't truncate; if very short opinion, leave for review layer to enrich
        return body
    return body


def apply_presence_humanization(
    text: str,
    prefs: dict[str, Any] | None = None,
    *,
    family_hint: str | None = None,
) -> str:
    """
    Apply emoji, enthusiasm, structure and detail prefs.
    Never invents markets. Fail-open → original text.
    """
    try:
        body = (text or "").strip()
        if not body:
            return body
        p = normalize_prefs(prefs if isinstance(prefs, dict) else None)
        family = _detect_family(body, family_hint)
        body = _enthusiasm_boost(body, p, family)
        body = _apply_structure(body, p)
        body = _apply_detail(body, p, family)

        if re.search(r"[\U0001F300-\U0001FAFF]", body):
            return body

        if not _should_add_emoji(p):
            return body

        opts = list(_EMOJI_BY_FAMILY.get(family) or _EMOJI_BY_FAMILY["casual"])
        emoji = random.choice(opts)
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


def apply_personality_to_payload(
    payload: dict[str, Any],
    prefs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply prefs to narrative fields of any soft/social/opinion payload."""
    try:
        if not isinstance(payload, dict):
            return payload
        ents = payload.get("entities") or {}
        hint = None
        if ents.get("opinion_time") or ents.get("natural_kind") == "team_opinion":
            hint = "team_opinion"
        elif ents.get("emotional"):
            hint = "thanks"
        elif "calendar" in str(ents.get("natural_kind") or ""):
            hint = "calendar"
        for field in ("executive_summary", "final_recommendation"):
            if payload.get(field):
                payload[field] = apply_presence_humanization(
                    str(payload[field]), prefs, family_hint=hint
                )
        meta = dict(payload.get("response_metadata") or {})
        meta["personality_applied"] = normalize_prefs(
            prefs if isinstance(prefs, dict) else None
        )
        payload["response_metadata"] = meta
        return payload
    except Exception as exc:
        logger.warning("apply_personality_to_payload fail-open: %s", exc)
        return payload
