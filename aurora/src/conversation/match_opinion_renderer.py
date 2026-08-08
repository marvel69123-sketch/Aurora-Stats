"""
Phase 8.3-A — Match opinion renderer.

When opinion_time / recent_match is set, produce a match-reading reply —
never panorama / fase / agenda templates.
"""

from __future__ import annotations

import logging
import random
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def _tone(message: str) -> str:
    folded = _fold(message)
    if re.search(r"\b(atuacao|jogou\s+bem|como\s+foi)\b", folded):
        return "performance"
    if re.search(r"\b(viu|achou|opiniao)\b", folded):
        return "opinion"
    return "opinion"


def render_match_opinion(
    *,
    team: str,
    message: str = "",
    ctx: dict[str, Any] | None = None,
    variant: int | None = None,
) -> str:
    """
    Honest match-opinion reply. Does not invent scorelines.
    """
    label = (team or "o time").strip() or "o time"
    if variant is None:
        variant = random.randint(0, 2)
    tone = _tone(message)

    # Prefer real fixture label from short memory when present
    subject = f"partida do {label}"
    try:
        sm = (ctx or {}).get("short_conversation_memory") or {}
        fx = sm.get("last_fixture")
        if isinstance(fx, str) and fx.strip() and _fold(label) in _fold(fx):
            subject = fx.strip()
    except Exception:
        pass

    if tone == "performance":
        pool = [
            (
                f"Sobre a atuação do {label}: sem o placar e o adversário confirmados "
                f"aqui, eu evito um veredito seco.\n\n"
                f"Minha leitura genérica é olhar intensidade, organização sem bola e "
                f"se o time sustentou ideia por 90 minutos — isso costuma separar "
                f"“jogou bem” de só resultado.\n\n"
                f"Se você me disser o adversário ou o resultado da {subject}, "
                f"eu comento a atuação com bem mais precisão."
            ),
            (
                f"Atuação do {label}: do jeito que eu leio, “jogou bem” depende do "
                f"contexto — domínio vs eficiência, e se o plano apareceu em campo.\n\n"
                f"Ainda sem o detalhe da partida na mesa, prefiro opinião aberta a "
                f"nota inventada.\n\n"
                f"Me passa o placar ou o rival que eu afino a leitura."
            ),
            (
                f"Eu olharia a atuação do {label} por controle de jogo e resposta sob "
                f"pressão, não só pelo resultado.\n\n"
                f"Sem o recorte confirmado da {subject}, minha opinião fica "
                f"provisória.\n\n"
                f"Se tiver adversário/resultado, consigo ser bem mais direto."
            ),
        ]
    else:
        pool = [
            (
                f"Sem o placar confirmado aqui, minha leitura é que o {label} "
                f"mostrou sinais positivos ou negativos dependendo do contexto da "
                f"partida — ritmo, erros baratos e se a ideia de jogo apareceu.\n\n"
                f"Se você me disser o adversário ou o resultado, consigo comentar "
                f"de forma mais precisa."
            ),
            (
                f"Sobre a {subject}: eu não cravo um “foi bom/ruim” sem o placar "
                f"e o rival na mesa.\n\n"
                f"Minha opinião honesta é que o útil é cruzar o que o {label} "
                f"tentou fazer com o que realmente sustentou em 90 minutos.\n\n"
                f"Me passa o resultado ou o adversário que eu fecho a leitura."
            ),
            (
                f"O que eu acho do jogo do {label}: sem o detalhe confirmado da "
                f"partida, prefiro uma opinião em aberto a inventar narrativa.\n\n"
                f"Em geral eu olharia se o time controlou o jogo ou só reagiu — "
                f"isso muda completamente o veredito.\n\n"
                f"Com adversário/placar, a opinião fica bem mais afiada."
            ),
        ]

    text = pool[int(variant) % len(pool)]
    logger.warning(
        "[AUDIT] MatchOpinionRenderer: team=%r tone=%s variant=%s",
        label,
        tone,
        variant,
    )
    return text


def wants_match_opinion_render(
    message: str,
    *,
    detected: dict[str, Any] | None = None,
    ctx: dict[str, Any] | None = None,
) -> bool:
    """True when renderer should own the turn (not team_summary panorama)."""
    det = detected or {}
    if det.get("recent_match"):
        return True
    try:
        from src.conversation.human_inference import is_recent_match_opinion_ask

        if is_recent_match_opinion_ask(message):
            return True
        raw = ""
        if isinstance(ctx, dict):
            raw = str(ctx.get("raw_user_message") or "")
        if raw and is_recent_match_opinion_ask(raw):
            return True
    except Exception:
        pass
    hie = (ctx or {}).get("human_inference") or {} if isinstance(ctx, dict) else {}
    expects = hie.get("what_user_expects") or []
    return isinstance(expects, list) and "recent_match" in expects
