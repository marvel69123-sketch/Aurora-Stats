"""
Mission 050 — Shared bare market chip / short follow-up tokens.

Keeps gols / cartões / BTTS / over / under at parity with escanteios for
Router + Conversational short-FU detectors. Accent-tolerant via callers'
fold/norm, and via accent classes in the regex itself.
"""

from __future__ import annotations

import re
import unicodedata

# Shared alt used by detectors (goals, corners, cards, BTTS, over/under, …)
MARKET_TOKEN_ALT = (
    r"gols?|golos?|"
    r"escanteios?|corners?|cantos?|"
    r"cart[oõ]es?|cart[aã]o|cards?|amarelos?|"
    r"btts|ambos(?:\s+marcam)?|ambas(?:\s+marcam)?|"
    r"over|under|handicap"
)

# Pure market chip (optional leading "e "/"pra ", optional line number)
BARE_MARKET_FOLLOWUP = re.compile(
    rf"^(?:e\s+)?(?:(?:a|o|as|os|pra|para)\s+)?"
    rf"(?:{MARKET_TOKEN_ALT})"
    rf"(?:\s+\d+(?:[.,]\d+)?)?"
    rf"\s*[?!]*$",
    re.I,
)

# Continuity kind → follow_up_engine bridge message
_KIND_TO_ENGINE: dict[str, str] = {
    "gols": "gols",
    "escanteios": "escanteios",
    "cartoes": "cartoes",
    "btts": "btts",
    "over": "over",
    "under": "under",
    "handicap": "handicap",
}

_KIND_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("escanteios", re.compile(r"escanteios?|corners?|cantos?", re.I)),
    ("cartoes", re.compile(r"cart[oõ]es?|cart[aã]o|cards?|amarelos?", re.I)),
    ("btts", re.compile(r"btts|ambos(?:\s+marcam)?|ambas(?:\s+marcam)?", re.I)),
    ("over", re.compile(r"\bover\b", re.I)),
    ("under", re.compile(r"\bunder\b", re.I)),
    ("handicap", re.compile(r"\bhandicap\b", re.I)),
    ("gols", re.compile(r"gols?|golos?", re.I)),
]

MARKET_FOLLOWUP_KINDS = frozenset(_KIND_TO_ENGINE.keys())


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def is_bare_market_followup(message: str | None) -> bool:
    """True for solicited chips like 'gols', 'escanteios', 'BTTS', 'over'."""
    folded = _fold(message or "")
    if not folded or len(folded.split()) > 6:
        return False
    return bool(BARE_MARKET_FOLLOWUP.match(folded)) or bool(
        BARE_MARKET_FOLLOWUP.match((message or "").strip())
    )


def bare_market_kind(message: str | None) -> str | None:
    """Return continuity/FU kind for a bare market chip, or None."""
    if not is_bare_market_followup(message):
        return None
    folded = _fold(message or "")
    for kind, pat in _KIND_PATTERNS:
        if pat.search(folded):
            return kind
    return None


def engine_bridge_message(kind: str, fallback: str = "") -> str:
    """Map continuity kind → message for follow_up_engine."""
    return _KIND_TO_ENGINE.get(kind, fallback or kind)


def has_sport_sticky_context(ctx: dict | None) -> bool:
    """True when session/anchor memory makes a bare market chip sport-safe."""
    if not isinstance(ctx, dict):
        return False
    if isinstance(ctx.get("last_match"), str) and ctx["last_match"].strip():
        return True
    if isinstance(ctx.get("last_fixture"), str) and ctx["last_fixture"].strip():
        return True
    if ctx.get("last_home") and ctx.get("last_away"):
        return True
    if isinstance(ctx.get("last_analysis"), dict) and ctx["last_analysis"]:
        return True
    scg = ctx.get("sport_continuity_guard")
    if isinstance(scg, dict):
        anchor = scg.get("anchor")
        if isinstance(anchor, dict) and (
            anchor.get("fixture") or anchor.get("teams")
        ):
            return True
    cont = ctx.get("conversation_continuity")
    if isinstance(cont, dict) and cont.get("active") and int(cont.get("turns_left") or 0) > 0:
        return True
    csl = ctx.get("csl")
    if isinstance(csl, dict) and (csl.get("fixture") or csl.get("teams")):
        return True
    cs = ctx.get("conversation_state")
    if isinstance(cs, dict) and cs.get("active_fixture"):
        return True
    sm = ctx.get("short_conversation_memory")
    if isinstance(sm, dict) and (sm.get("last_fixture") or sm.get("last_team")):
        return True
    return False
