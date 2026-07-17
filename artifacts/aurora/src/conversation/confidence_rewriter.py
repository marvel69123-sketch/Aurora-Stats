"""
Confidence Rewriter — sound like an assistant, not like an error log.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Banned "error-ish" honesty → assistant tone
_REWRITES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"n[aã]o confirmei um boletim fresco[^.]*\.", re.I),
        "Sem informações ao vivo neste momento, a leitura fica no contexto geral.",
    ),
    (
        re.compile(r"n[aã]o confirmei[^.]*\.", re.I),
        "Com base no contexto atual, ainda sem um recorte ao vivo fechado.",
    ),
    (
        re.compile(r"n[aã]o (?:consegui|localizei|encontrei)[^.]*\.", re.I),
        "Sem informações ao vivo neste momento — sigo pelo contexto disponível.",
    ),
    (
        re.compile(r"n[aã]o tenho a sequ[eê]ncia recente confirmada[^.]*\.", re.I),
        "Com base no contexto atual, a fase ainda pede cautela sem cravar forma.",
    ),
    (
        re.compile(r"sem placar/recorte oficial recente[^.]*\.", re.I),
        "Ainda sem um placar recente amarrado aqui; o útil é cruzar fase e próximo desafio.",
    ),
    (
        re.compile(r"sem recorte oficial[^.]*\.", re.I),
        "Sem um recorte ao vivo amarrado; priorizo fase e próximo adversário.",
    ),
    (
        re.compile(
            r"n[aã]o localizei o pr[oó]ximo jogo confirmado[^.]*\.",
            re.I,
        ),
        "O próximo desafio depende do calendário oficial — me diga o adversário e eu afunilo.",
    ),
    (
        re.compile(r"me diga o campeonato ou o advers[aá]rio que eu afunilo\.?", re.I),
        "Se tiver o próximo adversário em mente, a gente afunila na hora.",
    ),
    (
        re.compile(r"sem boletim fresco completo na mesa[^.]*\.", re.I),
        "Com o contexto atual do confronto, a leitura nasce do momento de cada lado.",
    ),
    (
        re.compile(r"qualquer 'est[aá] bem/mal' seria chute\.?", re.I),
        "melhor cravar só o que o contexto sustenta.",
    ),
    (
        re.compile(r"ent[aã]o trato o momento com cautela, sem cravar forma\.?", re.I),
        "priorizo fase e próximo desafio em vez de um veredito seco.",
    ),
]


_BANNED_AFTER = re.compile(
    r"\b(n[aã]o confirmei|n[aã]o (?:consegui|localizei|encontrei)|"
    r"n[aã]o tenho a sequ[eê]ncia)\b",
    re.I,
)


def rewrite_confidence_tone(text: str) -> str:
    """Rewrite gap/error phrasing into assistant confidence."""
    out = text or ""
    for pat, repl in _REWRITES:
        out = pat.sub(repl, out)
    # Residual cleanup
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    if _BANNED_AFTER.search(out):
        out = _BANNED_AFTER.sub("com o contexto atual", out)
        logger.warning("[AUDIT] ConfidenceRewriter: residual banned phrase scrubbed")
    else:
        logger.warning("[AUDIT] ConfidenceRewriter: applied")
    return out


def has_errorish_honesty(text: str) -> bool:
    return bool(
        re.search(
            r"\b(n[aã]o confirmei|n[aã]o (?:consegui|localizei|encontrei))\b",
            text or "",
            re.I,
        )
    )
