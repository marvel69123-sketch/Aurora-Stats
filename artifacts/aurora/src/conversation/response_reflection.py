"""
Response Reflection — usefulness / Gemini-like / anti-philosophy gate.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_PHILOSOPHY = re.compile(
    r"("
    r"evitaria opini[aã]o engessada|"
    r"olharia menos o hype|"
    r"camisa n[aã]o decide sozinha|"
    r"veredito engessado|"
    r"mesmo sem um boletim|"
    r"leitura sem veredito|"
    r"prefiro raciocinar a cravar|"
    r"n[aã]o trato s[oó] a camisa|"
    r"n[aã]o s[oó] a camisa"
    r")",
    re.I,
)

_ENCYCLOPEDIA = re.compile(
    r"("
    r"é uma agremia[cç][aã]o|"
    r"é um clube de futebol|"
    r"Clube de Regatas do|"
    r"Football Club is |"
    r"com sede na|"
    r"fundado em \d{4}"
    r")",
    re.I,
)

_ERRORISH = re.compile(
    r"\b(n[aã]o confirmei|n[aã]o (?:consegui|localizei|encontrei))\b",
    re.I,
)

_USEFUL_MARKERS = re.compile(
    r"("
    r"Momento|Fase|Press[aã]o|Mercado|Pr[oó]ximos|Perspectiva|"
    r"Como chega|Pontos positivos|Pontos de aten|"
    r"Expectativa|Contexto|T[aá]tica|Cen[aá]rio|"
    r"Sem informa[cç][oõ]es ao vivo|Com base no contexto|"
    r"vit[oó]ria|derrota|empate|hoje|amanh[aã]|rodada|"
    r"pr[oó]ximo (?:jogo|desafio|advers)"
    r")",
    re.I,
)

_SECTION_HEADERS = re.compile(
    r"(📊|📰|📅|🎯|✅|⚠|🔮|⚔|📈|📉|🔥|📡|⏭|🧭|🧠|🎟|🗞️|🧾)",
)


@dataclass
class ReflectionResult:
    ok: bool
    contains_real_information: bool
    answers_question: bool
    feels_useful: bool
    feels_like_analyst: bool
    feels_like_gemini: bool
    user_would_be_satisfied: bool
    reasons: list[str] = field(default_factory=list)
    blocked: bool = False
    usefulness_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def does_answer_contain_real_information(text: str) -> bool:
    t = text or ""
    if _ENCYCLOPEDIA.search(t):
        return False
    if _SECTION_HEADERS.search(t) and _USEFUL_MARKERS.search(t):
        return True
    if re.search(
        r"\b(vit[oó]ria|derrota|empate|gols?|rodada|hoje|amanh[aã]|les[aã]o)\b",
        t,
        re.I,
    ):
        return True
    return bool(_SECTION_HEADERS.search(t) and len(t) > 120)


def does_answer_answer_question(text: str, question: str = "") -> bool:
    t = (text or "").strip()
    if not t or t in {"?", ".", "-"}:
        return False
    if _PHILOSOPHY.search(t) and not _SECTION_HEADERS.search(t):
        return False
    q = (question or "").lower()
    if "como est" in q or "atualmente" in q:
        return bool(re.search(r"(Fase|Momento|Press|Como chega|aten|fase)", t, re.I))
    return bool(_SECTION_HEADERS.search(t) or len(t) > 80)


def does_answer_feel_useful(text: str) -> bool:
    """P1 gate — FAIL on philosophy blurbs / hype essays."""
    t = text or ""
    if _PHILOSOPHY.search(t):
        return False
    if _ENCYCLOPEDIA.search(t):
        return False
    if _ERRORISH.search(t):
        return False
    if not _SECTION_HEADERS.search(t):
        return False
    return bool(_USEFUL_MARKERS.search(t))


def does_answer_feel_like_analyst(text: str) -> bool:
    t = text or ""
    if _PHILOSOPHY.search(t) or _ENCYCLOPEDIA.search(t):
        return False
    headers = len(_SECTION_HEADERS.findall(t))
    return headers >= 2 and does_answer_feel_useful(t)


def does_answer_feel_like_gemini(text: str) -> bool:
    t = text or ""
    if _PHILOSOPHY.search(t) or _ENCYCLOPEDIA.search(t) or _ERRORISH.search(t):
        return False
    headers = len(_SECTION_HEADERS.findall(t))
    return headers >= 2 and does_answer_contain_real_information(t)


def reflect_response(
    text: str,
    *,
    question: str = "",
    answer_type: str = "",
) -> ReflectionResult:
    info = does_answer_contain_real_information(text)
    answers = does_answer_answer_question(text, question)
    useful = does_answer_feel_useful(text)
    analyst = does_answer_feel_like_analyst(text)
    gemini = does_answer_feel_like_gemini(text)
    reasons: list[str] = []
    if _PHILOSOPHY.search(text or ""):
        reasons.append("philosophy_blurb")
    if _ENCYCLOPEDIA.search(text or ""):
        reasons.append("encyclopedia_dump")
    if _ERRORISH.search(text or ""):
        reasons.append("errorish_honesty")
    if not info:
        reasons.append("no_real_information")
    if not answers:
        reasons.append("does_not_answer_question")
    if not useful:
        reasons.append("not_useful")
    if not gemini:
        reasons.append("not_gemini_like")

    score = (
        (25.0 if info else 0.0)
        + (25.0 if answers else 0.0)
        + (25.0 if useful else 0.0)
        + (15.0 if analyst else 0.0)
        + (10.0 if gemini else 0.0)
    )
    satisfied = score >= 70 and "philosophy_blurb" not in reasons
    blocked = bool(
        (_PHILOSOPHY.search(text or "") and not _SECTION_HEADERS.search(text or ""))
        or _ENCYCLOPEDIA.search(text or "")
        or (text or "").strip() in {"?", ".", "-"}
        or _ERRORISH.search(text or "")
    )
    ok = (
        info
        and answers
        and useful
        and gemini
        and not blocked
        and "philosophy_blurb" not in reasons
    )

    result = ReflectionResult(
        ok=ok,
        contains_real_information=info,
        answers_question=answers,
        feels_useful=useful,
        feels_like_analyst=analyst,
        feels_like_gemini=gemini,
        user_would_be_satisfied=satisfied,
        reasons=reasons,
        blocked=blocked,
        usefulness_score=score,
    )
    logger.warning(
        "[AUDIT] ResponseReflection: ok=%s score=%.0f blocked=%s reasons=%s type=%s",
        result.ok,
        score,
        result.blocked,
        reasons,
        answer_type,
    )
    return result
