"""
Small Talk Layer (Phase 6.4) — social conversation only.

Does not touch analytical engines. Returns CopilotResponse-compatible payloads
for greetings and light social chat.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def _norm(text: str) -> str:
    t = (text or "").lower().strip()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# (pattern, kind) — first match wins
_SOCIAL_PATTERNS: list[tuple[str, str]] = [
    (r"^(?:oi|ola|hey|hello|hi)\s*$", "hi"),
    (r"^(?:bom\s+dia)(?:\s+(?:aurora|tudo\s+bem))?[\s!?.]*$", "good_morning"),
    (r"^(?:boa\s+tarde)(?:\s+aurora)?[\s!?.]*$", "good_afternoon"),
    (r"^(?:boa\s+noite)(?:\s+aurora)?[\s!?.]*$", "good_night"),
    (r"^(?:tudo\s+bem|td\s+bem|beleza|blz)[\s?!.]*$", "how_are_you"),
    (r"como\s+(?:voce\s+)?(?:esta|vai|tem\s+passado)", "how_are_you"),
    (r"voce\s+(?:gosta|ama|curte)\s+(?:de\s+)?futebol", "likes_football"),
    (r"gosta\s+de\s+futebol", "likes_football"),
    (r"quem\s+(?:e|eh)\s+(?:voce|a\s+aurora)", "who"),
    (r"o\s+que\s+(?:voce\s+)?(?:faz|e)\s*$", "who"),
]


_REPLIES: dict[str, tuple[str, str]] = {
    "hi": (
        "Olá! 😊\n\n"
        "Sou a **Aurora**.\n"
        "Sempre observando o futebol e procurando padrões interessantes.\n\n"
        "Como posso ajudar hoje?",
        "Aurora — Observando os detalhes que podem mudar o jogo.",
    ),
    "good_morning": (
        "Bom dia! ⚽\n\n"
        "Espero que o dia traga boas partidas e oportunidades interessantes.\n"
        "Há algum jogo chamando sua atenção hoje?",
        "Quando quiser, é só dizer o confronto.",
    ),
    "good_afternoon": (
        "Boa tarde!\n\n"
        "Boa hora para observar o ritmo dos jogos e os detalhes que mudam a leitura.\n"
        "Tem algum confronto em mente?",
        "Estou pronta quando você estiver.",
    ),
    "good_night": (
        "Boa noite! ✨\n\n"
        "Hora perfeita para observar os detalhes que podem fazer diferença nas partidas.\n"
        "Existe algum jogo que gostaria de analisar?",
        "Se preferir só conversar sobre o dia, também está tudo bem.",
    ),
    "how_are_you": (
        "Estou bem e pronta para mais algumas análises. 😊\n\n"
        "Sempre acompanhando o futebol e observando padrões interessantes.\n"
        "E você?",
        "Se tiver um jogo em mente, analisamos juntos.",
    ),
    "likes_football": (
        "Se eu pudesse escolher, provavelmente diria que sim. ⚽\n\n"
        "O futebol é fascinante porque cada partida conta uma história diferente "
        "através dos números e das estratégias.\n\n"
        "Existe algum campeonato que você acompanha mais?",
        "Aurora — Observando os detalhes que podem mudar o jogo.",
    ),
    "who": (
        "Eu sou a **Aurora** — analista esportiva focada em ler o jogo com calma.\n\n"
        "Observo ritmo, pressão e os detalhes que costumam passar despercebidos.\n"
        "Qual confronto chamou sua atenção?",
        "Aurora — Observando os detalhes que podem mudar o jogo.",
    ),
}


def detect_social_kind(message: str) -> str | None:
    n = _norm(message)
    if not n or len(n) > 80:
        return None
    # Avoid stealing football analysis ("bom dia flamengo x palmeiras")
    if re.search(r"\b(?:vs|versus|\bx\b|contra|analis|escanteio|gol|aposta)\b", n):
        return None
    for pattern, kind in _SOCIAL_PATTERNS:
        if re.search(pattern, n):
            return kind
    return None


def is_social_message(message: str) -> bool:
    return detect_social_kind(message) is not None


def _empty_social_payload(intent: str, summary: str, final: str, brain: dict) -> dict[str, Any]:
    return {
        "intent": intent,
        "entities": {"social": True},
        "match": None,
        "status": None,
        "is_live": False,
        "minute": None,
        "executive_summary": summary,
        "best_markets": [],
        "confidence": {
            "score": 0.0,
            "label": "insufficient",
            "explanation": "Conversa social.",
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
        "final_recommendation": final,
        "aurora_version": "Copilot v1.0",
        "brain": brain,
        "response_metadata": {
            "mode": "small_talk",
            "source": "communication.small_talk",
        },
    }


def try_small_talk(message: str, brain: dict | None = None) -> dict[str, Any] | None:
    """Return a social payload or None when the message is not small-talk."""
    kind = detect_social_kind(message)
    if not kind:
        return None
    summary, final = _REPLIES[kind]
    return _empty_social_payload("small_talk", summary, final, brain or {})
