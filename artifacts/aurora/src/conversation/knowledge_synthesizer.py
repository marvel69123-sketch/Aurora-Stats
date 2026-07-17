"""
Knowledge Synthesizer — turn web/api/memory into usable football knowledge.
NEVER forwards Wikipedia institutional dumps as answer content.
Fail-open. Additive.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

CTX_KEY = "knowledge_pack"

_ENCYCLOPEDIA = re.compile(
    r"("
    r"é uma agremia[cç][aã]o|"
    r"é um clube de futebol|"
    r"Clube de Regatas do|"
    r"Football Club is |"
    r"is an? (?:Italian|English|Brazilian|Spanish) (?:football|soccer) club|"
    r"com sede na|"
    r"fundado em \d{4}|"
    r"poliesportiv"
    r")",
    re.I,
)

_USEFUL = re.compile(
    r"("
    r"\b(vit[oó]ria|derrota|empate|gols?|pontos?|classifica|"
    r"les[aã]o|contrato|t[eé]cnico|treinador|elenco|"
    r"pr[oó]ximo|hoje|amanh[aã]|ontem|rodada|copa|"
    r"brasileir|libertadores|premier|champions|"
    r"202[4-9]|form|resultado|placar)\b"
    r")",
    re.I,
)


@dataclass
class KnowledgePack:
    recent_results: list[str] = field(default_factory=list)
    team_moment: list[str] = field(default_factory=list)
    market_news: list[str] = field(default_factory=list)
    next_games: list[str] = field(default_factory=list)
    perspective: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    sources_used: list[str] = field(default_factory=list)
    has_real_signal: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def _clean(text: str, *, limit: int = 180) -> str:
    t = re.sub(r"\s+", " ", (text or "")).strip()
    if len(t) > limit:
        t = t[: limit - 1].rstrip() + "…"
    return t


def is_encyclopedia_noise(text: str) -> bool:
    return bool(_ENCYCLOPEDIA.search(text or ""))


def _is_useful_fact(text: str) -> bool:
    if not text or len(text.strip()) < 24:
        return False
    if is_encyclopedia_noise(text):
        return False
    return bool(_USEFUL.search(text))


def synthesize_knowledge(
    *,
    team: str | None = None,
    home: str | None = None,
    away: str | None = None,
    web_results: list[str] | None = None,
    api_results: list[str] | None = None,
    memory_results: list[str] | None = None,
    ctx: dict[str, Any] | None = None,
) -> KnowledgePack:
    """
    Merge sources into structured knowledge buckets.
    """
    pack = KnowledgePack()
    snippets: list[tuple[str, str]] = []

    for s in web_results or []:
        if s:
            snippets.append(("web", str(s)))
    for s in api_results or []:
        if s:
            snippets.append(("api", str(s)))
    for s in memory_results or []:
        if s:
            snippets.append(("memory", str(s)))

    # Pull from ctx if caller didn't pass lists
    if ctx is not None:
        web_ctx = ctx.get("web_context") or {}
        if isinstance(web_ctx, dict):
            for f in web_ctx.get("facts") or []:
                snippets.append(("web", str(f)))
            for f in web_ctx.get("recent_events") or []:
                snippets.append(("web", str(f)))
        web = ctx.get("web_thinking") or {}
        if isinstance(web, dict) and web.get("summary"):
            snippets.append(("web", str(web["summary"])))
            for src in web.get("sources_used") or []:
                if src not in pack.sources_used:
                    pack.sources_used.append(str(src))
        for g in ctx.get("next_games_hints") or []:
            snippets.append(("api", str(g)))

    subject = _fold(team or home or "")
    for src, raw in snippets:
        clean = _clean(raw)
        if not clean or is_encyclopedia_noise(clean):
            continue
        if src not in pack.sources_used:
            pack.sources_used.append(src)
        folded = _fold(clean)
        useful = _is_useful_fact(clean)

        if re.search(r"\b(proxima|proximo|amanha|hoje|vs| x )\b", folded) and useful:
            if clean not in pack.next_games:
                pack.next_games.append(clean)
        elif re.search(
            r"\b(vitoria|derrota|empate|gols?|placar|resultado|ontem|rodada)\b",
            folded,
        ):
            if clean not in pack.recent_results:
                pack.recent_results.append(clean)
        elif re.search(
            r"\b(lesao|suspenso|crise|pressa[oa]|oscil|instavel|problema)\b",
            folded,
        ):
            if clean not in pack.issues:
                pack.issues.append(clean)
        elif re.search(
            r"\b(solido|lider|invicto|regular|forte|bom momento|sequencia)\b",
            folded,
        ):
            if clean not in pack.strengths:
                pack.strengths.append(clean)
        elif useful:
            if clean not in pack.market_news:
                pack.market_news.append(clean)
            if clean not in pack.team_moment:
                pack.team_moment.append(clean)

    # Perspective from signal quality (honest, not philosophical)
    label = team or (f"{home} x {away}" if home and away else "o time")
    if pack.recent_results or pack.team_moment or pack.strengths:
        pack.has_real_signal = True
        pack.perspective.append(
            f"Com o que apareceu na mesa, o {label} pede leitura pelo "
            f"recorte recente — não só pela camisa."
        )
    else:
        pack.has_real_signal = False
        pack.perspective.append(
            f"Sem um recorte fresco confirmado do {label}, o caminho honesto "
            f"é olhar o próximo adversário e a regularidade recente — "
            f"posso afunilar se você tiver o jogo em mente."
        )

    # Cap lists
    pack.recent_results = pack.recent_results[:3]
    pack.team_moment = pack.team_moment[:3]
    pack.market_news = pack.market_news[:3]
    pack.next_games = pack.next_games[:3]
    pack.strengths = pack.strengths[:3]
    pack.issues = pack.issues[:3]
    pack.perspective = pack.perspective[:2]

    if ctx is not None:
        ctx[CTX_KEY] = pack.to_dict()
    logger.warning(
        "[AUDIT] KnowledgeSynthesizer: signal=%s recent=%d news=%d next=%d sources=%s",
        pack.has_real_signal,
        len(pack.recent_results),
        len(pack.market_news),
        len(pack.next_games),
        pack.sources_used,
    )
    return pack


async def collect_api_next_games(team: str | None) -> list[str]:
    """Best-effort next fixtures for a team — fail-open empty."""
    if not team:
        return []
    try:
        from datetime import date, timedelta

        from src.conversation.natural_conversation import (
            _fetch_fixtures_for_date,
            _filter_fixtures_by_teams,
            _format_agenda_blocks,
        )

        out: list[str] = []
        for offset in (0, 1, 2, 3):
            day = (date.today() + timedelta(days=offset)).isoformat()
            items = await _fetch_fixtures_for_date(day, league_id=None)
            matched = _filter_fixtures_by_teams(items or [], [team])
            if matched:
                block = _format_agenda_blocks(
                    matched[:2],
                    title=f"{team} — {day}",
                )
                # flatten first lines
                for line in block.splitlines():
                    line = line.strip()
                    if line and not line.startswith("⚽") and len(line) > 8:
                        out.append(line[:160])
                if len(out) >= 2:
                    break
        return out[:3]
    except Exception as exc:
        logger.warning("collect_api_next_games fail-open: %s", exc)
        return []
