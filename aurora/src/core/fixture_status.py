"""Canonical fixture live-status helpers — single source of truth."""

from __future__ import annotations

LIVE_STATUSES: frozenset[str] = frozenset(
    {"1H", "2H", "ET", "P", "BT", "HT", "SUSP", "INT", "LIVE"}
)
FINISHED_STATUSES: frozenset[str] = frozenset(
    {"FT", "AET", "PEN", "AWD", "WO"}
)


def fixture_minute(status: dict) -> int:
    """Return match minute from the canonical status block."""
    return int(status.get("minute") or 0)


def fixture_is_live(status: dict) -> bool:
    """True when status.short indicates the match is in play."""
    return status.get("short", "") in LIVE_STATUSES


def fixture_is_finished(status: dict) -> bool:
    """True when status.short indicates the match has ended."""
    return status.get("short", "") in FINISHED_STATUSES


def parse_fixture_status(status: dict) -> tuple[bool, bool, int]:
    """Return (is_live, is_finished, minute) from a canonical status dict."""
    return fixture_is_live(status), fixture_is_finished(status), fixture_minute(status)
