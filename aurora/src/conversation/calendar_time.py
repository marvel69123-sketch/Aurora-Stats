"""
AURORA-CALENDAR-001 — Fixture calendar date resolution.

Wraps brittle hoje/amanhã regex with optional dateparser (pt-BR).
Does NOT invent fixtures — only resolves a calendar day for lookups.

Feature flag: ENABLE_DATEPARSER (default OFF).
When off → legacy regex only.
When on  → dateparser search; fail-open to legacy on any error.
"""

from __future__ import annotations

import logging
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

_FLAG_ENV = "ENABLE_DATEPARSER"
_BR_TZ = timezone(timedelta(hours=-3))
_TZ_NAME = "America/Sao_Paulo"

# Weekday token → Python weekday (Mon=0 … Sun=6)
_WEEKDAY_INDEX: dict[str, int] = {
    "segunda": 0,
    "segunda-feira": 0,
    "terca": 1,
    "terca-feira": 1,
    "quarta": 2,
    "quarta-feira": 2,
    "quinta": 3,
    "quinta-feira": 3,
    "sexta": 4,
    "sexta-feira": 4,
    "sabado": 5,
    "domingo": 6,
}

_TEMPORAL_TOKEN = re.compile(
    r"("
    r"hoje|amanh[aã]|ontem|"
    r"depois\s+de\s+amanh[aã]|"
    r"semana\s+que\s+vem|pr[oó]xima\s+semana|"
    r"domingo|segunda(?:\s*-?\s*feira)?|ter[cç]a(?:\s*-?\s*feira)?|"
    r"quarta(?:\s*-?\s*feira)?|quinta(?:\s*-?\s*feira)?|"
    r"sexta(?:\s*-?\s*feira)?|s[aá]bado"
    r")",
    re.I,
)

_LEGACY_HOJE = re.compile(r"\bhoje\b", re.I)
_LEGACY_AMANHA = re.compile(r"\bamanh[aã]\b", re.I)


@dataclass(frozen=True)
class CalendarDateHint:
    """Resolved calendar day for fixture lookups (date-only, BR-leaning)."""

    date_iso: str
    date_offset: int
    label: str
    source: str  # "legacy" | "dateparser"
    matched_text: str = ""


def dateparser_enabled() -> bool:
    """ENABLE_DATEPARSER default OFF (0 / unset / false / off / no)."""
    raw = (os.environ.get(_FLAG_ENV) or "0").strip().lower()
    return raw not in {"0", "false", "off", "no", ""}


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def _now_br(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(_BR_TZ)
    if now.tzinfo is None:
        return now.replace(tzinfo=_BR_TZ)
    return now.astimezone(_BR_TZ)


def _to_hint(
    d: date,
    *,
    today: date,
    label: str,
    source: str,
    matched_text: str = "",
) -> CalendarDateHint:
    offset = (d - today).days
    return CalendarDateHint(
        date_iso=d.isoformat(),
        date_offset=int(offset),
        label=label,
        source=source,
        matched_text=matched_text,
    )


def legacy_resolve_fixture_date(
    message: str,
    *,
    now: datetime | None = None,
) -> CalendarDateHint | None:
    """
    Legacy regex path: hoje → offset 0, amanhã → offset 1.
    Unchanged behaviour when ENABLE_DATEPARSER is off.
    """
    folded = _fold(message)
    if not folded:
        return None
    base = _now_br(now)
    today = base.date()
    if _LEGACY_AMANHA.search(folded):
        d = today + timedelta(days=1)
        return _to_hint(d, today=today, label="amanhã", source="legacy", matched_text="amanha")
    if _LEGACY_HOJE.search(folded):
        return _to_hint(today, today=today, label="hoje", source="legacy", matched_text="hoje")
    return None


def _label_for(matched: str, offset: int) -> str:
    folded = _fold(matched)
    if offset == 0:
        return "hoje"
    if offset == 1:
        return "amanhã"
    if "amanh" in folded:
        return "amanhã"
    if folded == "hoje":
        return "hoje"
    # Prefer compact weekday label
    for key in (
        "domingo",
        "sabado",
        "segunda",
        "terca",
        "quarta",
        "quinta",
        "sexta",
    ):
        if key in folded.replace(" ", "").replace("-", ""):
            pretty = {
                "domingo": "domingo",
                "sabado": "sábado",
                "segunda": "segunda",
                "terca": "terça",
                "quarta": "quarta",
                "quinta": "quinta",
                "sexta": "sexta",
            }[key]
            return pretty
    return matched.strip() or (f"em {offset} dias" if offset else "hoje")


def _snap_weekday_to_today(
    matched: str,
    resolved: date,
    today: date,
) -> date:
    """
    With PREFER_DATES_FROM=future, 'domingo' on Sunday jumps +7 days.
    For fixture asks, same-weekday means today.
    """
    key = _fold(matched).replace(" ", "").replace("-feira", "").replace("-", "")
    # normalize terça → terca already via fold
    wd = _WEEKDAY_INDEX.get(key)
    if wd is None:
        # try prefix keys
        for name, idx in _WEEKDAY_INDEX.items():
            if key.startswith(name.replace("-feira", "")):
                wd = idx
                break
    if wd is not None and today.weekday() == wd:
        return today
    return resolved


def _dateparser_resolve(
    message: str,
    *,
    now: datetime | None = None,
) -> CalendarDateHint | None:
    from dateparser.search import search_dates

    base = _now_br(now)
    today = base.date()
    # RELATIVE_BASE must be naive for dateparser
    relative_base = base.replace(tzinfo=None)
    settings: dict[str, Any] = {
        "PREFER_DATES_FROM": "future",
        "TIMEZONE": _TZ_NAME,
        "RETURN_AS_TIMEZONE_AWARE": True,
        "RELATIVE_BASE": relative_base,
        "DATE_ORDER": "DMY",
    }

    hits = search_dates(message or "", languages=["pt"], settings=settings)
    if not hits:
        return None

    # Prefer the last temporal token in the message (e.g. "… joga domingo")
    chosen: tuple[str, datetime] | None = None
    for matched, dt in hits:
        if not _TEMPORAL_TOKEN.search(_fold(matched)):
            continue
        chosen = (matched, dt)
    if chosen is None:
        return None

    matched, dt = chosen
    if dt.tzinfo is not None:
        local_d = dt.astimezone(_BR_TZ).date()
    else:
        local_d = dt.date()
    local_d = _snap_weekday_to_today(matched, local_d, today)
    label = _label_for(matched, (local_d - today).days)
    return _to_hint(
        local_d,
        today=today,
        label=label,
        source="dateparser",
        matched_text=matched,
    )


def resolve_fixture_date(
    message: str,
    *,
    now: datetime | None = None,
) -> CalendarDateHint | None:
    """
    Resolve a calendar day from a PT-BR sports ask.

    Flag off → legacy regex.
    Flag on  → dateparser; on failure → legacy (fail-open).
    """
    if not dateparser_enabled():
        return legacy_resolve_fixture_date(message, now=now)

    try:
        hint = _dateparser_resolve(message, now=now)
        if hint is not None:
            return hint
    except Exception as exc:  # noqa: BLE001 — fail-open
        logger.warning(
            "[AUDIT] calendar_time dateparser failed → legacy: %s",
            exc,
        )

    return legacy_resolve_fixture_date(message, now=now)


def has_resolvable_calendar_date(
    message: str,
    *,
    now: datetime | None = None,
) -> bool:
    """True when resolve_fixture_date finds a day (respects flag / fail-open)."""
    return resolve_fixture_date(message, now=now) is not None
