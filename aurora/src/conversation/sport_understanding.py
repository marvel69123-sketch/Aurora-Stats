"""
P2.5-S Sports Understanding MVP — route real sport asks into the sport pipeline.

Fail-open. Additive. Does not invent match stats/odds.
Forces dialog_mode=SPORT (not UNKNOWN/SMALL_TALK) when real clubs/fixtures
or sport form asks are present.
"""

from __future__ import annotations

import re
import time
import unicodedata
from typing import Any

CTX_KEY = "sport_understanding"

_FICTION = re.compile(
    r"(?:"
    r"\bgoku\b|\bnaruto\b|\bvoldemort\b|\bbatman\b|\bsuperman\b|"
    r"\bpikachu\b|\bluffy\b|\bsaitama\b|\bthanos\b|\bsonic\b|"
    r"harry\s+potter|\bpotter\b|\bunicorn|\bdragao\b|\bdragão\b|"
    r"\bmarte\b"
    r")",
    re.I,
)

_KNOWN_CLUB = re.compile(
    r"\b("
    r"flamengo|botafogo|santos|corinthians|palmeiras|sao\s+paulo|são\s+paulo|"
    r"fluminense|gremio|grêmio|internacional|vasco|bahia|mirassol|cruzeiro|"
    r"atletico|atlético|fortaleza|bragantino|cuiaba|cuiabá|"
    r"mengao|mengão|verdao|verdão|timao|timão|fogao|fogão|fla|flu|galo|chape|"
    r"arsenal|chelsea|liverpool|juventus|manchester|barcelona|real\s+madrid|"
    r"barca|barça|city|united|bayern|dortmund|psg|milan|juve|"
    r"londrina|sao\s+bernardo|ivai|cabo\s+verde"
    r")\b",
    re.I,
)

_FIXTURE = re.compile(
    r"\b[\wÀ-ÿ.''-]{2,}\s+(?:x|vs\.?|versus|ou|contra)\s+[\wÀ-ÿ.''-]{2,}\b",
    re.I,
)

_FORM_ASK = re.compile(
    r"(?:"
    r"\b(?:ta|tá|esta|está|vai)\s+bem\b|"
    r"\bcomo\s+(?:ta|tá|esta|está|vai)\b|"
    r"\bo\s+que\s+(?:voce\s+)?acha\s+d[oe]\b|"
    r"\bmomento\s+(?:atual\s+)?d[oe]\b|"
    r"\bforma\s+(?:d[oe]|atual)\b|"
    r"\bvale\s+a\s+pena\b|"
    r"\bquem\s+ganha\b|"
    r"\bpalpite\b|"
    r"\banalis(?:ar|e)\b|"
    r"\bmercado\b|\bodds?\b|\baposta\b|"
    r"\bplacar\b|\bao\s+vivo\b|"
    r"\be\s+o\s+(?:meio[- ]?campo|ataque|defesa|goleiro)\b|"
    r"\be\s+dele\b|\be\s+o\s+outro\b|\bcomo\s+ele\b"
    r")",
    re.I,
)

_SPORT_LEX = re.compile(
    r"\b("
    r"jogo|jogos|partida|partidas|confronto|times?|sele[cç][aã]o|"
    r"brasileir[aã]o|libertadores|champions|classico|clássico|"
    r"escanteio|cart[aã]o|gols?"
    r")\b",
    re.I,
)


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def _bump(ctx: dict[str, Any] | None, key: str) -> None:
    if not isinstance(ctx, dict):
        return
    st = ctx.get(CTX_KEY)
    if not isinstance(st, dict):
        st = {"counters": {}}
        ctx[CTX_KEY] = st
    c = st.setdefault("counters", {})
    c[key] = int(c.get(key) or 0) + 1
    st["updated_at"] = time.time()


def is_pure_fiction(message: str | None) -> bool:
    """Fiction with no salvageable real-club primary ask."""
    folded = _fold(message or "")
    if not folded or not _FICTION.search(folded):
        return False
    if _FIXTURE.search(folded):
        m = _FIXTURE.search(folded)
        span = m.group(0) if m else ""
        if _FICTION.search(_fold(span)):
            return True
        if _KNOWN_CLUB.search(folded):
            return False
        return True
    if _FICTION.search(folded) and re.search(r"\be\s+se\b|\bjogasse\b", folded):
        return True
    if _FICTION.search(folded) and not _KNOWN_CLUB.search(folded):
        return True
    return False


def extract_known_club(message: str | None) -> str | None:
    folded = _fold(message or "")
    m = _KNOWN_CLUB.search(folded)
    if not m:
        return None
    raw = m.group(1)
    return " ".join(w.capitalize() for w in raw.replace("são", "sao").split())


def has_real_sport_signal(message: str | None, ctx: dict[str, Any] | None = None) -> bool:
    """True when the user is making a real sports ask (not pure fiction)."""
    if is_pure_fiction(message):
        return False
    folded = _fold(message or "")
    if not folded:
        return False
    if _KNOWN_CLUB.search(folded):
        return True
    if _FIXTURE.search(folded) and not _FICTION.search(folded):
        return True
    if _SPORT_LEX.search(folded) and _FORM_ASK.search(folded):
        return True
    try:
        from src.conversation.dialog_mode import _has_sport_frame, _is_sport_short_fu

        if _has_sport_frame(ctx) and _is_sport_short_fu(message):
            return True
    except Exception:
        pass
    return False


def should_force_sport_mode(
    message: str | None,
    ctx: dict[str, Any] | None = None,
    *,
    master_intent: str | None = None,
) -> bool:
    """Force dialog_mode=SPORT so UNKNOWN/SMALL_TALK cannot claim the turn."""
    intent = (master_intent or "").upper()
    if intent in {"SPORT_QUERY", "LIVE_MATCH"} and not is_pure_fiction(message):
        return True
    if has_real_sport_signal(message, ctx):
        return True
    if isinstance(ctx, dict):
        mi = ctx.get("master_intent")
        if isinstance(mi, dict) and str(mi.get("intent") or "").upper() in {
            "SPORT_QUERY",
            "LIVE_MATCH",
        }:
            if not is_pure_fiction(message):
                return True
    return False


def is_fixture_pair_ask(message: str | None) -> bool:
    folded = _fold(message or "")
    if not folded or is_pure_fiction(message):
        return False
    return bool(_FIXTURE.search(folded) and _KNOWN_CLUB.search(folded))


def is_team_form_ask(message: str | None) -> bool:
    folded = _fold(message or "")
    if not folded or is_pure_fiction(message):
        return False
    if not _KNOWN_CLUB.search(folded):
        return False
    if _FIXTURE.search(folded):
        return False
    return bool(_FORM_ASK.search(folded) or len(folded.split()) <= 6)


def stamp_sport_understanding(
    ctx: dict[str, Any] | None,
    message: str | None,
    *,
    master_intent: str | None = None,
    forced: bool = False,
) -> dict[str, Any]:
    """Record recall decision on ctx (fail-open)."""
    info = {
        "forced_sport_mode": bool(forced),
        "master_intent": master_intent,
        "club": extract_known_club(message),
        "fixture_pair": is_fixture_pair_ask(message),
        "team_form": is_team_form_ask(message),
        "pure_fiction": is_pure_fiction(message),
    }
    if isinstance(ctx, dict):
        st = ctx.get(CTX_KEY)
        if not isinstance(st, dict):
            st = {"counters": {}}
        st.update(info)
        st["updated_at"] = time.time()
        if forced:
            c = st.setdefault("counters", {})
            c["forced_sport_mode"] = int(c.get("forced_sport_mode") or 0) + 1
        ctx[CTX_KEY] = st
    return info


def enrich_sport_entities(
    entities: dict[str, Any] | None,
    message: str | None,
) -> dict[str, Any]:
    """Stamp dialog_mode=SPORT and team when known."""
    ents = dict(entities or {})
    ents["dialog_mode"] = "SPORT"
    ents["p25_sport_understanding"] = True
    club = extract_known_club(message)
    if club and not ents.get("team"):
        ents["team"] = club
    if is_fixture_pair_ask(message):
        ents["sport_ask_shape"] = "fixture_pair"
    elif is_team_form_ask(message):
        ents["sport_ask_shape"] = "team_form"
    else:
        ents["sport_ask_shape"] = "sport_other"
    return ents
