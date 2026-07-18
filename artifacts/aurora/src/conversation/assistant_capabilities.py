"""
Phase 8.4-A.9 — Assistant Capabilities intent.

Detects "o que você faz / funcionalidades / como funciona" and builds a
clear onboarding-style capabilities reply.

Fail-open. Does not touch sport engines / ownership / markets.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

INTENT_NAME = "assistant_capabilities"

_CAPABILITY_RE = re.compile(
    r"("
    r"o\s+que\s+(?:voce\s+)?faz\b|"
    r"o\s+que\s+(?:voce\s+)?sabe\s+fazer|"
    r"o\s+que\s+(?:voce\s+)?(?:consegue|pode)\s+fazer|"
    r"o\s+que\s+(?:voce\s+)?consegue\s+analisar|"
    r"o\s+que\s+(?:e\s+)?capaz\s+de\s+fazer|"
    r"como\s+(?:voce\s+)?funciona|"
    r"como\s+(?:voce\s+)?pode\s+me\s+ajudar|"
    r"como\s+(?:voce\s+)?pode\s+ajudar|"
    r"no\s+que\s+(?:voce\s+)?(?:pode|consegue)\s+ajudar|"
    r"para\s+que\s+serve\s+(?:a\s+)?aurora|"
    r"(?:suas?\s+)?funcionalidades|"
    r"quais\s+(?:seus?\s+|suas?\s+)?(?:recursos|funcoes|capacidades|funcionalidades)|"
    r"quais\s+recursos\s+(?:voce\s+)?possui|"
    r"aurora\s+funcionalidades|"
    r"^(?:funcionalidades|recursos)\s*\??$|"
    r"what\s+can\s+you\s+do|"
    r"what\s+do\s+you\s+do"
    r")",
    re.I,
)


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def is_capabilities_ask(message: str | None) -> bool:
    folded = _fold(message or "")
    if not folded:
        return False
    return bool(_CAPABILITY_RE.search(folded))


def capability_source_phrase(message: str | None) -> str | None:
    folded = _fold(message or "")
    m = _CAPABILITY_RE.search(folded)
    if not m:
        return None
    return (m.group(0) or "").strip()[:120] or None


def build_capabilities_reply() -> str:
    return (
        "Sou a **Aurora**, uma IA especializada em futebol.\n\n"
        "Posso:\n\n"
        "⚽ Analisar partidas e confrontos.\n"
        "📊 Explicar estatísticas, pressão e tendências.\n"
        "🎯 Identificar oportunidades e mercados.\n"
        "🧠 Conversar naturalmente sobre futebol.\n"
        "📅 Informar próximos jogos e calendário.\n"
        "💬 Manter contexto durante a conversa.\n\n"
        "Também posso responder perguntas gerais e explicar como cheguei "
        "às minhas conclusões.\n\n"
        "Pode pedir, por exemplo: *analisar Argentina x Espanha*, "
        "*próximo jogo do Fluminense* ou *o que você achou do jogo ontem?*."
    )


def stamp_capability_audit(
    payload: dict[str, Any] | None,
    *,
    source_phrase: str | None = None,
    repair_reclassified: bool = False,
    previous_intent: str | None = None,
    new_intent: str | None = None,
) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    ents = dict(out.get("entities") or {})
    ents["capability_intent_detected"] = True
    if source_phrase:
        ents["capability_source_phrase"] = source_phrase
    if repair_reclassified:
        ents["repair_reclassified"] = True
        if previous_intent is not None:
            ents["previous_intent"] = previous_intent
        if new_intent is not None:
            ents["new_intent"] = new_intent
    out["entities"] = ents
    return out


def build_capabilities_payload(
    message: str | None = None,
    *,
    repair_reclassified: bool = False,
    previous_intent: str | None = None,
) -> dict[str, Any]:
    try:
        from src.brain import get_brain_meta

        brain = get_brain_meta()
    except Exception:
        brain = {}

    text = build_capabilities_reply()
    phrase = capability_source_phrase(message)
    payload: dict[str, Any] = {
        "intent": INTENT_NAME,
        "entities": {
            "general_assistant": True,
            "assistant_kind": "capabilities",
            "assistant_capabilities": True,
            "has_analysis": False,
            "show_header": False,
            "skip_llm": True,
            "rewrite_locked": True,
            "final_response": True,
            "response_owner": "assistant_capabilities",
        },
        "match": None,
        "status": None,
        "is_live": False,
        "minute": None,
        "executive_summary": text,
        "best_markets": [],
        "confidence": {
            "score": 0.0,
            "label": "insufficient",
            "explanation": "Apresentação de capacidades da Aurora.",
            "data_sources": ["AssistantCapabilities"],
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
        "knowledge_notes": [
            "Análise → \"Analisar [Casa] x [Fora]\"",
            "Agenda → \"Próximo jogo do [Time]\" / \"Jogos de hoje\"",
            "Opinião → \"O que você achou do jogo do [Time]?\"",
            "Identidade → \"Quem é você?\"",
        ],
        "final_recommendation": text,
        "aurora_version": "Copilot v1.0",
        "brain": brain,
        "response_metadata": {
            "mode": "assistant_capabilities",
            "source": "assistant_capabilities",
            "show_header": False,
        },
    }
    stamped = stamp_capability_audit(
        payload,
        source_phrase=phrase or (message or "")[:80],
        repair_reclassified=repair_reclassified,
        previous_intent=previous_intent,
        new_intent=INTENT_NAME if repair_reclassified else None,
    )
    logger.warning(
        "[AUDIT] AssistantCapabilities: phrase=%r repair=%s prev=%r",
        phrase,
        repair_reclassified,
        previous_intent,
    )
    return stamped or payload
