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


# Phase 7.9-B P0-2 — anti sticky regenerate (NRF only)
_ENTENDI_PREFIX = "Entendi. Posso te ajudar"

_BYPASS_REPLIES: tuple[str, ...] = (
    "Pode falar comigo normalmente — em que posso ajudar?",
    "Me conta de outro jeito o que você precisa agora.",
    "Ok — vamos tentar de novo. O que você quer que eu faça?",
    "Parece que travamos na mesma resposta. Diz o objetivo em uma frase.",
)


def _norm_sig(text: str, n: int = 80) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())[:n].lower()


def extremely_similar(a: str, b: str) -> bool:
    """True when two replies are effectively the same template."""
    sa, sb = (a or "").strip(), (b or "").strip()
    if not sa or not sb:
        return False
    if sa == sb:
        return True
    na, nb = _norm_sig(sa), _norm_sig(sb)
    if na == nb:
        return True
    if len(na) > 40 and len(nb) > 40 and na[:40] == nb[:40]:
        return True
    if sa.startswith(_ENTENDI_PREFIX) and sb.startswith(_ENTENDI_PREFIX):
        return True
    return False


def _pick_bypass(ctx: dict[str, Any] | None, *, avoid: str = "") -> str:
    hist = []
    if isinstance(ctx, dict):
        raw = ctx.get("recent_assistant_replies") or []
        if isinstance(raw, list):
            hist = [str(x) for x in raw]
    idx = len(hist) % len(_BYPASS_REPLIES)
    for offset in range(len(_BYPASS_REPLIES)):
        candidate = _BYPASS_REPLIES[(idx + offset) % len(_BYPASS_REPLIES)]
        if not extremely_similar(candidate, avoid) and not any(
            extremely_similar(candidate, h) for h in hist[-3:]
        ):
            return candidate
    return _BYPASS_REPLIES[0]


def _hist_list(ctx: dict[str, Any] | None) -> list[str]:
    if not isinstance(ctx, dict):
        return []
    raw = ctx.get("recent_assistant_replies") or []
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw]


def _trace_pipe(tag: str, **fields: Any) -> None:
    try:
        from src.conversation.pipeline_trace import trace as _ptrace

        _ptrace(tag, **fields)
    except Exception:
        pass


def _log_obrigatory(tag: str, **fields: Any) -> None:
    """Emit required Phase 7.9-B tags to both logger and pipeline_trace."""
    try:
        parts = " ".join(f"{k}={v}" for k, v in fields.items() if v is not None)
        logger.warning("[%s] %s", tag, parts)
    except Exception:
        pass
    _trace_pipe(tag, **fields)


def filter_or_regenerate(
    text: str,
    *,
    master_intent: str,
    ctx: dict[str, Any] | None = None,
    regenerate: str | None = None,
) -> str:
    """If artificial / low perception / template-repeat → use regenerate or strip."""
    _trace_pipe(
        "NRF_INPUT",
        master_intent=master_intent,
        text_prefix=(text or "")[:80],
        regen_prefix=(regenerate or "")[:80] if regenerate else None,
        hist_len=len(_hist_list(ctx)),
    )

    score = score_perceived_intelligence(text, master_intent=master_intent)
    similar = template_too_similar(text, ctx)
    sticky_keep = bool(
        (text or "").strip().startswith(_ENTENDI_PREFIX)
        and any(
            extremely_similar(text, h) or h.strip().startswith(_ENTENDI_PREFIX)
            for h in _hist_list(ctx)[-3:]
        )
    )

    if (
        score.ok
        and not similar
        and not sticky_keep
        and not (
            looks_artificial_sport_voice(text)
            and master_intent not in {"SPORT_QUERY", "LIVE_MATCH"}
        )
    ):
        note_assistant_reply(ctx, text)
        _trace_pipe(
            "NRF_OUTPUT",
            action="keep",
            similar=False,
            text_prefix=(text or "")[:80],
        )
        return text

    if sticky_keep and score.ok and not similar:
        # Re-keep of Entendi after it already appeared → bypass without fake regen
        _log_obrigatory(
            "NRF_LOOP_DETECTED",
            similar=similar,
            same_as_input=True,
            same_as_regen=bool(regenerate)
            and extremely_similar(text or "", regenerate or ""),
            sticky_entendi=True,
            text_prefix=(text or "")[:80],
        )
        bypass = _pick_bypass(ctx, avoid=text or "")
        _log_obrigatory(
            "NRF_BYPASS",
            reason="sticky_keep_entendi",
            text_prefix=bypass[:80],
            previous_prefix=(text or "")[:80],
        )
        note_assistant_reply(ctx, bypass)
        if ctx is not None:
            ctx["perception_score"] = score.to_dict()
            ctx["nrf_last_action"] = "bypass"
        _trace_pipe(
            "NRF_OUTPUT",
            action="bypass",
            similar=False,
            text_prefix=bypass[:80],
            entendi_out=False,
        )
        return bypass

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

    _in = (text or "").strip()
    _out = (out or "").strip()
    _regen = (regenerate or "").strip() if regenerate else ""
    same_as_input = extremely_similar(_out, _in)
    same_as_regen = bool(_regen) and extremely_similar(_out, _regen)
    sticky_entendi = _out.startswith(_ENTENDI_PREFIX) and (
        similar or same_as_input or template_too_similar(_out, ctx)
    )

    # P0-2: never ship regenerate that is the same sticky template
    used_bypass = False
    if same_as_input or (same_as_regen and similar) or sticky_entendi:
        _log_obrigatory(
            "NRF_LOOP_DETECTED",
            similar=similar,
            same_as_input=same_as_input,
            same_as_regen=same_as_regen,
            sticky_entendi=sticky_entendi,
            text_prefix=_out[:80],
        )
        bypass = _pick_bypass(ctx, avoid=_out)
        _log_obrigatory(
            "NRF_BYPASS",
            reason="same_regen_or_sticky",
            text_prefix=bypass[:80],
            previous_prefix=_out[:80],
        )
        out = bypass
        _out = out.strip()
        used_bypass = True
        same_as_input = extremely_similar(_out, _in)
        same_as_regen = bool(_regen) and extremely_similar(_out, _regen)

    note_assistant_reply(ctx, out)
    if ctx is not None:
        ctx["perception_score"] = score.to_dict()
        ctx["nrf_last_action"] = "bypass" if used_bypass else "regenerate"
    _trace_pipe(
        "NRF_OUTPUT",
        action=("bypass" if used_bypass else "regenerate"),
        similar=similar,
        score=round(score.overall, 1),
        reasons=",".join(score.reasons) if score.reasons else "",
        text_prefix=_out[:80],
        same_as_input=same_as_input,
        same_as_regen=same_as_regen if _regen else None,
        entendi_in=(_ENTENDI_PREFIX in _in),
        entendi_out=(_ENTENDI_PREFIX in _out),
    )
    return out
