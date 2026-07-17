"""
Natural Response Filter + template / perceived-intelligence gates.
Blocks artificial sports-analyst filler in non-sport (and regenerates when needed).
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from typing import Any

logger = logging.getLogger(__name__)

_ARTIFICIAL = re.compile(
    r"("
    r"o contexto atual|"
    r"com o contexto atual|"
    r"o [uú]til [eé]|"
    r"o caminho honesto|"
    r"a leitura pede|"
    r"como chega|"
    r"o recorte recente|"
    r"priorizo fase|"
    r"sem informa[cç][oõ]es ao vivo neste momento|"
    r"leitura r[aá]pida|"
    r"pr[eé]-leitura"
    r")",
    re.I,
)

_PHILOSOPHY = re.compile(
    r"("
    r"evitaria opini[aã]o engessada|"
    r"olharia menos o hype|"
    r"n[aã]o s[oó] a camisa|"
    r"veredito engessado"
    r")",
    re.I,
)


@dataclass
class PerceptionScore:
    intelligent: float
    human: float
    useful: float
    thoughtful: float
    overall: float
    ok: bool
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def looks_artificial_sport_voice(text: str) -> bool:
    return bool(_ARTIFICIAL.search(text or "") or _PHILOSOPHY.search(text or ""))


def template_too_similar(text: str, ctx: dict[str, Any] | None) -> bool:
    """Compare against last few assistant replies stored on ctx."""
    t = (text or "").strip()
    if not t or not ctx:
        return False
    hist = ctx.get("recent_assistant_replies") or []
    if not isinstance(hist, list):
        return False
    # Same first header / first 80 chars
    sig = re.sub(r"\s+", " ", t)[:80].lower()
    for prev in hist[-3:]:
        p = re.sub(r"\s+", " ", str(prev))[:80].lower()
        if p and sig and (sig == p or (len(sig) > 40 and sig[:40] == p[:40])):
            return True
    return False


def score_perceived_intelligence(
    text: str,
    *,
    master_intent: str = "",
) -> PerceptionScore:
    t = (text or "").strip()
    reasons: list[str] = []
    intelligent = 80.0
    human = 80.0
    useful = 80.0
    thoughtful = 80.0

    if not t or t == "?":
        return PerceptionScore(0, 0, 0, 0, 0, False, ["empty"])

    if looks_artificial_sport_voice(t) and master_intent not in {
        "SPORT_QUERY",
        "LIVE_MATCH",
    }:
        intelligent -= 40
        human -= 50
        useful -= 40
        reasons.append("artificial_sport_voice")

    if _PHILOSOPHY.search(t):
        intelligent -= 30
        human -= 30
        reasons.append("philosophy")

    if master_intent == "MATH_QUERY":
        if re.fullmatch(r"-?\d+(?:\.\d+)?", t):
            useful = 95
            thoughtful = 90
            human = 90
            intelligent = 90
        elif "2+2" in t or "futebol" in t.lower():
            useful -= 50
            reasons.append("math_contaminated")

    if master_intent in {"SMALL_TALK", "SYSTEM_QUERY"} and re.search(
        r"(Botafogo|Flamengo|Corinthians|Santos|panorama|Momento atual)",
        t,
        re.I,
    ):
        human -= 50
        useful -= 40
        reasons.append("sport_leak_in_social")

    overall = (intelligent + human + useful + thoughtful) / 4.0
    ok = overall >= 80 and "sport_leak_in_social" not in reasons and "math_contaminated" not in reasons
    return PerceptionScore(
        intelligent=intelligent,
        human=human,
        useful=useful,
        thoughtful=thoughtful,
        overall=overall,
        ok=ok,
        reasons=reasons,
    )


def note_assistant_reply(ctx: dict[str, Any] | None, text: str) -> None:
    if not isinstance(ctx, dict) or not text:
        return
    hist = list(ctx.get("recent_assistant_replies") or [])
    hist.append(text[:240])
    ctx["recent_assistant_replies"] = hist[-5:]


def filter_or_regenerate(
    text: str,
    *,
    master_intent: str,
    ctx: dict[str, Any] | None = None,
    regenerate: str | None = None,
) -> str:
    """If artificial / low perception / template-repeat → use regenerate or strip."""
    score = score_perceived_intelligence(text, master_intent=master_intent)
    similar = template_too_similar(text, ctx)
    if score.ok and not similar and not (
        looks_artificial_sport_voice(text)
        and master_intent not in {"SPORT_QUERY", "LIVE_MATCH"}
    ):
        note_assistant_reply(ctx, text)
        return text

    logger.warning(
        "[AUDIT] NaturalFilter: regenerate intent=%s score=%.0f reasons=%s similar=%s",
        master_intent,
        score.overall,
        score.reasons,
        similar,
    )
    out = regenerate if regenerate else text
    if looks_artificial_sport_voice(out) and master_intent not in {
        "SPORT_QUERY",
        "LIVE_MATCH",
    }:
        out = regenerate or "Pode falar comigo normalmente — em que posso ajudar?"
    note_assistant_reply(ctx, out)
    if ctx is not None:
        ctx["perception_score"] = score.to_dict()
    return out
