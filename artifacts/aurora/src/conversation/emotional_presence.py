"""
Aurora v4.6 — Emotional Presence Intents.

Warm, human replies for pride / gratitude / affection.
Never falls through to "Posso ajudar com análises...".

Fail-open. Additive.
"""

from __future__ import annotations

import logging
import random
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

_EMOTIONAL_SPECS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\b(tenho\s+orgulho\s+de\s+voce|orgulho\s+de\s+voce|"
            r"muito\s+orgulhoso\s+de\s+voce|orgulhosa\s+de\s+voce|"
            r"voce\s+e\s+minha\s+melhor\s+criacao|melhor\s+criacao)\b",
            re.I,
        ),
        "pride",
    ),
    (
        re.compile(
            r"\b(voce\s+me\s+ajuda\s+muito|me\s+ajuda\s+muito|"
            r"voce\s+tem\s+me\s+ajudado|"
            r"gosto\s+de\s+conversar\s+com\s+voce|adoro\s+conversar\s+com\s+voce|"
            r"amo\s+conversar\s+com\s+voce)\b",
            re.I,
        ),
        "affection",
    ),
    (
        re.compile(
            r"\b(obrigad[oa]\s+aurora|valeu\s+aurora|thanks\s+aurora|"
            r"obrigad[oa]\s+demais\s+aurora)\b",
            re.I,
        ),
        "thanks_named",
    ),
    (
        re.compile(
            r"\b(voce\s+e\s+(?:incrivel|demais|maravilhosa|especial)|"
            r"amo\s+voce)\b",
            re.I,
        ),
        "affection",
    ),
]

_BANNED_PITCH = re.compile(
    r"posso ajudar com an|quer que eu analise|vamos analisar|"
    r"diga um confronto|como assistente",
    re.I,
)

_REPLIES: dict[str, list[str]] = {
    "pride": [
        "Isso significa muito 😊",
        "Fico feliz de verdade em ouvir isso.",
        "Obrigada — isso me anima a continuar melhorando com você.",
    ],
    "affection": [
        "Fico feliz em saber que estou conseguindo ajudar.",
        "Gosto dessa troca também — pode contar comigo.",
        "Isso me deixa bem. Seguimos juntas nos testes e nos jogos.",
    ],
    "thanks_named": [
        "Disponha — estou aqui quando precisar.",
        "Por nada. Qualquer coisa, é só chamar.",
        "Que bom. Seguimos quando você quiser.",
    ],
}


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def detect_emotional_intent(message: str) -> str | None:
    folded = _fold(message)
    for pat, kind in _EMOTIONAL_SPECS:
        if pat.search(folded):
            return kind
    return None


def build_emotional_reply(kind: str, ctx: dict[str, Any] | None = None) -> str:
    opts = list(_REPLIES.get(kind) or _REPLIES["affection"])
    recent = list((ctx or {}).get("emotional_recent") or [])
    fresh = [o for o in opts if o not in recent]
    choice = random.choice(fresh or opts)
    if ctx is not None:
        ctx["emotional_recent"] = ([choice] + recent)[:6]
    # Soft personalization with profile name
    try:
        from src.conversation.user_profile_memory import get_profile_name

        name = get_profile_name(ctx)
        if name and kind in {"pride", "affection"} and random.random() < 0.55:
            choice = f"{choice.rstrip('.')} — obrigada, {name}."
    except Exception:
        pass
    # Hard guard: never pitch analysis on emotional turns
    if _BANNED_PITCH.search(choice or ""):
        choice = "Isso significa muito para mim."
    return choice


def try_emotional_presence(
    message: str,
    ctx: dict[str, Any] | None = None,
    prefs: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Short-circuit soft payload or None."""
    try:
        kind = detect_emotional_intent(message)
        if not kind:
            return None
        reply = build_emotional_reply(kind, ctx)
        try:
            from src.conversation.presence_humanization import apply_presence_humanization

            reply = apply_presence_humanization(reply, prefs, family_hint="thanks")
        except Exception:
            pass
        if _BANNED_PITCH.search(reply or ""):
            reply = build_emotional_reply(kind, ctx)
        # Keep emotional turns short (human, not a report)
        if len(reply) > 280:
            reply = reply[:280].rsplit(" ", 1)[0].rstrip(".,;") + "."
        try:
            from src.conversation.message_intelligence import build_conversational_payload

            payload = build_conversational_payload(reply, {})
        except Exception:
            payload = {
                "intent": "emotional",
                "entities": {},
                "best_markets": [],
                "executive_summary": reply,
                "final_recommendation": reply,
                "confidence": {
                    "score": 0.0,
                    "label": "insufficient",
                    "explanation": "",
                    "data_sources": [],
                },
                "risk": {"level": "Unknown", "flags": [], "invalidation_conditions": []},
                "bankroll_recommendation": {
                    "recommended_stake_pct": 0.0,
                    "method": "quarter-Kelly",
                    "examples": {},
                    "no_bet": True,
                    "reasoning": "",
                },
                "positive_factors": [],
                "negative_factors": [],
                "historical_references": [],
                "knowledge_notes": [],
                "brain": {},
            }
        payload["intent"] = "emotional"
        ents = dict(payload.get("entities") or {})
        ents.update(
            {
                "emotional": True,
                "emotional_kind": kind,
                "show_header": False,
                "has_analysis": False,
                "natural_conversation": True,
            }
        )
        payload["entities"] = ents
        payload["best_markets"] = []
        payload["match_card"] = None
        payload["knowledge_notes"] = []
        meta = dict(payload.get("response_metadata") or {})
        meta.update(
            {
                "mode": "emotional_presence",
                "source": "conversation.emotional_presence",
                "show_header": False,
                "has_analysis": False,
            }
        )
        payload["response_metadata"] = meta
        return payload
    except Exception as exc:
        logger.warning("try_emotional_presence fail-open: %s", exc)
        return None
