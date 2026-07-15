"""
Aurora v3.3.1-beta — Fixture input cleaner (Entity Resolver Stabilization).

Presentation/routing hygiene only: strips conversational stop-words around a
fixture mention before EntityResolver sees the team fragments.

Does NOT change methodology / market / confidence / learning engines.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass

logger = logging.getLogger(__name__)

AURORA_CLEANER_VERSION = "Aurora v3.3.1-beta"

# Separators accepted for a confrontation (x / vs / contra / versus / ×)
_SEP_RE = re.compile(r"\b(x|vs|contra|versus)\b|×", re.IGNORECASE)

# Longest phrases first so "quero saber sobre" wins over single tokens.
_STOP_PHRASES: tuple[str, ...] = (
    "quero saber sobre",
    "me diga",
    "por favor",
    "como esta",
    "ao vivo",
    "aurora",
    "quero",
    "saber",
    "sobre",
    "agora",
    "amanha",
    "hoje",
    "analise",
    "analisar",
    "analisa",
)


def _fold_accents(text: str) -> str:
    text = (text or "").lower().strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s×x]", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _strip_stop_phrases(fragment: str) -> str:
    """Remove conversational stop words/phrases from one side of the fixture."""
    text = _fold_accents(fragment)
    if not text:
        return ""

    phrases = sorted(_STOP_PHRASES, key=len, reverse=True)
    changed = True
    while changed and text:
        changed = False
        for phrase in phrases:
            pattern = rf"(?<!\w){re.escape(phrase)}(?!\w)"
            new = re.sub(pattern, " ", text, flags=re.IGNORECASE)
            new = re.sub(r"\s+", " ", new).strip()
            if new != text:
                text = new
                changed = True
                break
    return text


@dataclass(frozen=True)
class CleanedFixtureInput:
    raw_input: str
    clean_input: str
    home_team: str | None
    away_team: str | None
    separator: str | None
    is_live: bool = False


def clean_fixture_input(raw: str) -> CleanedFixtureInput:
    """
    Extract a clean ``home vs away`` span from a natural-language message.

    Example:
      "aurora quero saber sobre argentina vs inglaterra amanhã"
      → clean_input="argentina vs inglaterra"
        home_team="argentina", away_team="inglaterra"
    """
    raw_input = (raw or "").strip()
    norm = _fold_accents(raw_input)
    if not norm:
        result = CleanedFixtureInput(raw_input, "", None, None, None)
        _log_extraction(result)
        return result

    sep_m = _SEP_RE.search(norm)
    if not sep_m:
        result = CleanedFixtureInput(raw_input, "", None, None, None)
        _log_extraction(result)
        return result

    sep = sep_m.group(0)
    left = _strip_stop_phrases(norm[: sep_m.start()])
    right = _strip_stop_phrases(norm[sep_m.end() :])

    is_live = bool(
        re.search(r"\b(?:ao\s+vivo|live|agora)\b", norm)
        or "ao vivo" in _fold_accents(raw_input)
    )

    if not left or not right:
        result = CleanedFixtureInput(
            raw_input=raw_input,
            clean_input="",
            home_team=None,
            away_team=None,
            separator=sep,
            is_live=is_live,
        )
        _log_extraction(result)
        return result

    # Prefer a stable separator token for CLEAN_INPUT
    sep_out = "vs" if sep.lower() in {"vs", "versus", "×"} else (
        "x" if sep.lower() == "x" else "contra"
    )
    clean_input = f"{left} {sep_out} {right}"
    result = CleanedFixtureInput(
        raw_input=raw_input,
        clean_input=clean_input,
        home_team=left,
        away_team=right,
        separator=sep_out,
        is_live=is_live,
    )
    _log_extraction(result)
    return result


def _log_extraction(result: CleanedFixtureInput) -> None:
    logger.warning("RAW_INPUT=%r", result.raw_input)
    logger.warning("CLEAN_INPUT=%r", result.clean_input)
    logger.warning("HOME_TEAM=%r", result.home_team)
    logger.warning("AWAY_TEAM=%r", result.away_team)


def extract_fixture_teams(raw: str) -> tuple[str | None, str | None, bool]:
    """Convenience: (home, away, is_live) after cleaning."""
    cleaned = clean_fixture_input(raw)
    return cleaned.home_team, cleaned.away_team, cleaned.is_live
