"""
Information Ranking Engine — prioritize recent / important / expected facts.
Prohibits club-history encyclopedia noise.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_HISTORY_BAN = re.compile(
    r"("
    r"é uma agremia[cç][aã]o|"
    r"é um clube de futebol|"
    r"Clube de Regatas do|"
    r"fundado em \d{4}|"
    r"com sede na|"
    r"poliesportiv"
    r")",
    re.I,
)


@dataclass
class RankedItem:
    text: str
    score: float
    kind: str  # recent_result | news | next_game | moment | other


def _score_item(
    text: str,
    *,
    kind: str,
    expectation_keys: set[str],
) -> float:
    if _HISTORY_BAN.search(text or ""):
        return -100.0
    t = (text or "").lower()
    score = 0.0
    # Recency
    if re.search(r"\b(hoje|ontem|amanh[aã]|rodada|202[4-9]|agora)\b", t):
        score += 3.0
    if kind == "recent_result":
        score += 4.0
    elif kind == "news":
        score += 2.5
    elif kind == "next_game":
        score += 2.0
    elif kind == "moment":
        score += 2.2
    # Importance
    if re.search(r"\b(les[aã]o|t[eé]cnico|t[ií]tulo|rebaix|libertadores|final)\b", t):
        score += 2.0
    if re.search(r"\b(vit[oó]ria|derrota|empate|gols?)\b", t):
        score += 1.5
    # Relevance / expectation
    if kind == "recent_result" and (
        "último resultado" in expectation_keys or "recent_result" in expectation_keys
    ):
        score += 2.0
    if kind == "next_game" and (
        "próximos jogos" in expectation_keys or "next_matches" in expectation_keys
    ):
        score += 1.8
    if kind == "news" and (
        "notícias" in expectation_keys or "news" in expectation_keys
    ):
        score += 1.5
    if kind == "moment" and (
        "momento atual" in expectation_keys or "fase" in expectation_keys
    ):
        score += 1.8
    return score


def rank_information(
    pack: Any,
    *,
    expects: list[str] | None = None,
    limit: int = 8,
) -> list[RankedItem]:
    """
    Score and order knowledge. Drops history/encyclopedia.
    Priority target: último jogo > notícia > próximo jogo > história(ban).
    """
    expectation_keys = {e.lower() for e in (expects or [])}
    items: list[RankedItem] = []

    def add(texts: list[str] | None, kind: str) -> None:
        for t in texts or []:
            if not t or _HISTORY_BAN.search(t):
                continue
            s = _score_item(t, kind=kind, expectation_keys=expectation_keys)
            if s < 0:
                continue
            items.append(RankedItem(text=t, score=s, kind=kind))

    add(getattr(pack, "recent_results", None), "recent_result")
    add(getattr(pack, "market_news", None), "news")
    add(getattr(pack, "next_games", None), "next_game")
    add(getattr(pack, "team_moment", None), "moment")
    add(getattr(pack, "strengths", None), "moment")
    add(getattr(pack, "issues", None), "moment")

    items.sort(key=lambda x: x.score, reverse=True)
    # Reorder pack lists by score
    recent = [i.text for i in items if i.kind == "recent_result"]
    news = [i.text for i in items if i.kind == "news"]
    nxt = [i.text for i in items if i.kind == "next_game"]
    moment = [i.text for i in items if i.kind == "moment"]
    if recent:
        pack.recent_results = recent[:3]
    if news:
        pack.market_news = news[:3]
    if nxt:
        pack.next_games = nxt[:3]
    if moment:
        pack.team_moment = moment[:3]

    logger.warning(
        "[AUDIT] InformationRanking: top=%s",
        [(i.kind, round(i.score, 1)) for i in items[:5]],
    )
    return items[:limit]
