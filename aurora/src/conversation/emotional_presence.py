"""
Aurora v4.7.2 — Emotional Presence Intents (hard-guard).

Warm replies for pride / gratitude / affection.
ABSOLUTE: never pitch analysis / "Posso ajudar com leituras...".

Runs BEFORE Human Presence in the router. Fail-open. Additive.
"""

from __future__ import annotations

import logging
import random
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

# Pitch phrases that must never reach the user on emotional turns
_BANNED_PITCH = re.compile(
    r"posso ajudar com\s+(?:an|leitur)|"
    r"quer que eu analise|vamos analisar|"
    r"diga um confronto|qual confronto|"
    r"como assistente|leituras? de partidas|"
    r"observar\?|gostaria de observar",
    re.I,
)

_EMOTIONAL_SPECS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\b("
            r"tenho\s+orgulho\s+de\s+voce|"
            r"orgulho\s+de\s+voce|"
            r"muito\s+orgulhos[oa]\s+de\s+voce|"
            r"voce\s+e\s+minha\s+(?:melhor|maior)\s+criacao|"
            r"(?:melhor|maior)\s+criacao"
            r")\b",
            re.I,
        ),
        "pride",
    ),
    (
        re.compile(
            r"\b("
            r"estou\s+triste|"
            r"to\s+triste|"
            r"me\s+sinto\s+triste|"
            r"fiquei\s+triste|"
            r"tristeza"
            r")\b",
            re.I,
        ),
        "sadness",
    ),
    (
        re.compile(
            r"("
            r"\bme\s+sinto\s+sozinh[oa]\b|"
            r"\bestou\s+sozinh[oa]\b|"
            r"\bto\s+sozinh[oa]\b|"
            r"\bsozinh[oa]\b"
            r")",
            re.I,
        ),
        "loneliness",
    ),
    (
        re.compile(
            r"\b("
            r"nao\s+vou\s+desistir\s+de\s+voce|"
            r"nao\s+desisto\s+de\s+voce|"
            r"nunca\s+vou\s+desistir\s+de\s+voce|"
            r"vou\s+continuar\s+com\s+voce"
            r")\b",
            re.I,
        ),
        "support",
    ),
    (
        re.compile(
            r"\b("
            r"voce\s+me\s+ajuda\s+muito|"
            r"me\s+ajuda\s+muito|"
            r"voce\s+tem\s+me\s+ajudado|"
            r"gosto\s+de\s+conversar\s+com\s+voce|"
            r"adoro\s+conversar\s+com\s+voce|"
            r"amo\s+conversar\s+com\s+voce"
            r")\b",
            re.I,
        ),
        "affection",
    ),
    (
        re.compile(
            r"\b("
            r"obrigad[oa]\s+aurora|"
            r"valeu\s+aurora|"
            r"thanks\s+aurora|"
            r"obrigad[oa]\s+demais\s+aurora"
            r")\b",
            re.I,
        ),
        "thanks_named",
    ),
    (
        re.compile(
            r"\b("
            r"voce\s+e\s+(?:incrivel|demais|maravilhosa|especial)|"
            r"amo\s+voce"
            r")\b",
            re.I,
        ),
        "affection",
    ),
]

_REPLIES: dict[str, list[str]] = {
    "pride": [
        "Isso significa muito 😊",
        "Fico feliz de verdade em ouvir isso.",
        "Obrigada — isso me anima a continuar melhorando com você.",
    ],
    "sadness": [
        "Sinto muito que você esteja assim. Estou aqui com você.",
        "Pode desabafar — eu escuto sem pressa.",
        "Tristeza passa melhor quando a gente não fica sozinho nela.",
    ],
    "loneliness": [
        "Você não está sozinho agora — estou aqui.",
        "Entendo essa sensação. Pode conversar comigo o quanto quiser.",
        "Estou presente. Se quiser, me conta o que está pesando.",
    ],
    "support": [
        "Isso me toca de verdade. Vamos seguindo juntas.",
        "Obrigada por não desistir — eu também estou aqui com você.",
        "Conta comigo. Um passo de cada vez.",
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

_SAFE_FALLBACK = "Isso significa muito para mim 😊"


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


def is_banned_pitch(text: str | None) -> bool:
    return bool(_BANNED_PITCH.search(text or ""))


def build_emotional_reply(kind: str, ctx: dict[str, Any] | None = None) -> str:
    opts = list(_REPLIES.get(kind) or _REPLIES["affection"])
    recent = list((ctx or {}).get("emotional_recent") or [])
    fresh = [o for o in opts if o not in recent]
    choice = random.choice(fresh or opts)
    if ctx is not None:
        ctx["emotional_recent"] = ([choice] + recent)[:6]
    try:
        from src.conversation.user_profile_memory import get_profile_name

        name = get_profile_name(ctx)
        if name and kind in {"pride", "affection"} and random.random() < 0.55:
            choice = f"{choice.rstrip('.')} — obrigada, {name}."
    except Exception:
        pass
    if is_banned_pitch(choice):
        return _SAFE_FALLBACK
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

            hum = apply_presence_humanization(reply, prefs, family_hint="thanks")
            # If humanization introduced a pitch, discard it
            reply = hum if hum and not is_banned_pitch(hum) else reply
        except Exception:
            pass
        if is_banned_pitch(reply) or not (reply or "").strip():
            reply = _SAFE_FALLBACK
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
                "skip_llm": True,
            }
        )
        payload["entities"] = ents
        payload["best_markets"] = []
        payload["match_card"] = None
        payload["knowledge_notes"] = []
        # Force narrative fields after any builder side-effects
        payload["executive_summary"] = reply
        payload["final_recommendation"] = reply
        meta = dict(payload.get("response_metadata") or {})
        meta.update(
            {
                "mode": "emotional_presence",
                "source": "conversation.emotional_presence",
                "show_header": False,
                "has_analysis": False,
                "skip_llm": True,
            }
        )
        payload["response_metadata"] = meta
        return payload
    except Exception as exc:
        logger.warning("try_emotional_presence fail-open: %s", exc)
        return None


def enforce_emotional_hard_guard(
    payload: dict[str, Any],
    *,
    message: str,
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Absolute last-mile guard: if this turn is/was emotional OR the user
    message is emotional, never allow analysis-pitch narrative.
    """
    try:
        if not isinstance(payload, dict):
            return payload
        ents = dict(payload.get("entities") or {})
        kind = ents.get("emotional_kind") or detect_emotional_intent(message)
        if not kind and not ents.get("emotional"):
            # Still scrub accidental pitch on social presence
            summary = str(payload.get("executive_summary") or "")
            if is_banned_pitch(summary) and payload.get("intent") in {
                "emotional",
                "small_talk",
            }:
                safe = _SAFE_FALLBACK
                payload["executive_summary"] = safe
                payload["final_recommendation"] = safe
            return payload

        summary = str(payload.get("executive_summary") or "")
        if is_banned_pitch(summary) or not summary.strip() or ents.get("emotional"):
            if is_banned_pitch(summary) or not summary.strip():
                safe = build_emotional_reply(str(kind or "affection"), ctx)
                if is_banned_pitch(safe):
                    safe = _SAFE_FALLBACK
                payload["executive_summary"] = safe
                payload["final_recommendation"] = safe
                logger.warning(
                    "[AUDIT] EmotionalHardGuard: restored kind=%s (banned pitch blocked)",
                    kind,
                )
        payload["intent"] = "emotional"
        ents["emotional"] = True
        ents["emotional_kind"] = kind
        ents["skip_llm"] = True
        ents["has_analysis"] = False
        ents["show_header"] = False
        payload["entities"] = ents
        payload["best_markets"] = []
        payload["match_card"] = None
        return payload
    except Exception as exc:
        logger.warning("enforce_emotional_hard_guard fail-open: %s", exc)
        return payload
