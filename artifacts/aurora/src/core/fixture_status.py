"""Canonical fixture live-status helpers — single source of truth."""

from __future__ import annotations

LIVE_STATUSES: frozenset[str] = frozenset(
    {"1H", "2H", "ET", "P", "BT", "HT", "SUSP", "INT", "LIVE"}
)
FINISHED_STATUSES: frozenset[str] = frozenset(
    {"FT", "AET", "PEN", "AWD", "WO"}
)


def fixture_minute(status: dict) -> int | None:
    """Return match minute from the canonical status block.

    Returns None only when the minute key is absent/unparseable.
    Zero is a valid minute (kickoff) and must not be collapsed to None.
    """
    raw = status.get("minute")
    if raw is None and "elapsed" in status:
        raw = status.get("elapsed")
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def fixture_is_live(status: dict) -> bool:
    """True when status.short indicates the match is in play.

    Canonical live shorts: 1H, 2H, HT, ET, BT, P, SUSP, INT, LIVE.
    Never treat First Half / 1H as pre-match.
    """
    short = str(status.get("short") or "").strip().upper()
    return short in LIVE_STATUSES


def fixture_is_finished(status: dict) -> bool:
    """True when status.short indicates the match has ended."""
    short = str(status.get("short") or "").strip().upper()
    return short in FINISHED_STATUSES


def parse_fixture_status(status: dict) -> tuple[bool, bool, int]:
    """Return (is_live, is_finished, minute) from a canonical status dict.

    Minute defaults to 0 when unknown so downstream math stays numeric,
    but callers that display minute should prefer fixture_minute() which
    preserves None vs 0.
    """
    minute = fixture_minute(status)
    return fixture_is_live(status), fixture_is_finished(status), int(minute or 0)
