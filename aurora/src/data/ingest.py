"""
P2b Wave 1 — Cached gateway fetches for fixtures / status / statistics / standings.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.data.cache import TTL_SEC, cache_key, get_cache
from src.data.gateway import GatewayResult, get_gateway

logger = logging.getLogger(__name__)

LIVE_SHORT = frozenset(
    {"1H", "2H", "HT", "ET", "BT", "P", "LIVE", "INT", "SUSP"}
)


@dataclass
class FetchOutcome:
    ok: bool
    data: dict[str, Any]
    signal: str
    source: str  # network | hot | warm | stale | empty | error
    rate_limited: bool = False
    circuit_open: bool = False
    error: str | None = None
    quality: str = "missing"

    def response_list(self) -> list:
        if isinstance(self.data, dict):
            resp = self.data.get("response")
            if isinstance(resp, list):
                return resp
        return []


def _signal_ttl(signal: str, *, status_short: str | None = None) -> float:
    short = str(status_short or "").upper()
    live = short in LIVE_SHORT
    if signal == "statistics":
        return TTL_SEC["statistics" if live else "statistics_pre"]
    if signal == "events":
        return TTL_SEC["events" if live else "events_pre"]
    if signal == "fixture" and live:
        return TTL_SEC["fixture_live"]
    if signal == "status" and live:
        return TTL_SEC["status"]
    return float(TTL_SEC.get(signal, 300.0))


def _classify_payload(data: dict[str, Any] | None) -> str:
    if not isinstance(data, dict):
        return "error"
    resp = data.get("response")
    if isinstance(resp, list) and len(resp) == 0:
        return "empty"
    if resp is None and not data:
        return "empty"
    return "confirmed"


async def fetch_signal(
    signal: str,
    path: str,
    params: dict[str, Any],
    *,
    status_short: str | None = None,
    allow_stale_on_fail: bool = True,
) -> FetchOutcome:
    """
    Hot → warm → gateway. On API failure, optionally serve stale cache.
    Never invents a payload.

    Emergency Cost Protection: prefer cache/stale; skip network unless
    force_refresh (premium) or ECPM request scope is inactive.
    """
    from src.ops import cost_protection as _ecpm

    cache = get_cache()
    gateway = get_gateway()
    key = cache_key(signal, path, *sorted((params or {}).items(), key=lambda x: str(x[0])))
    ttl = _signal_ttl(signal, status_short=status_short)

    cached = cache.get(key)
    if (
        cached is not None
        and cached.quality in {"confirmed", "empty"}
        and not _ecpm.is_force_refresh()
    ):
        _ecpm.record_cache_hit()
        return FetchOutcome(
            ok=True,
            data=cached.payload if isinstance(cached.payload, dict) else {"response": []},
            signal=signal,
            source="hot",
            quality=cached.quality,
        )

    # ECPM simple: stale before network; block network if not allowed
    if _ecpm.prefer_stale_cache() or not _ecpm.network_allowed():
        stale_first = cache.get(key, allow_stale=True)
        if stale_first is not None and stale_first.quality in {"confirmed", "empty"}:
            _ecpm.record_cache_hit()
            return FetchOutcome(
                ok=True,
                data=(
                    stale_first.payload
                    if isinstance(stale_first.payload, dict)
                    else {"response": []}
                ),
                signal=signal,
                source="stale",
                quality="stale" if stale_first.quality == "confirmed" else stale_first.quality,
            )
        if not _ecpm.network_allowed():
            _ecpm.record_cache_miss()
            return FetchOutcome(
                ok=False,
                data={"response": []},
                signal=signal,
                source="cost_protection_blocked",
                error="emergency_cost_protection_prefer_cache",
                quality="missing",
            )

    _ecpm.record_cache_miss()
    result: GatewayResult = await gateway.get(path, params, signal=signal)
    if result.ok and isinstance(result.data, dict):
        _ecpm.record_provider_call()
        quality = _classify_payload(result.data)
        cache.set(key, signal, result.data, quality=quality, ttl_sec=ttl)  # type: ignore[arg-type]
        return FetchOutcome(
            ok=True,
            data=result.data,
            signal=signal,
            source="network",
            quality=quality,
            rate_limited=bool(result.rate_limited),
        )

    # Recovery: stale cache
    if allow_stale_on_fail:
        stale = cache.get(key, allow_stale=True)
        if stale is not None and stale.quality in {"confirmed", "empty"}:
            logger.warning(
                "ingest: serving stale cache signal=%s err=%s",
                signal,
                result.error,
            )
            _ecpm.record_cache_hit()
            return FetchOutcome(
                ok=True,
                data=stale.payload if isinstance(stale.payload, dict) else {"response": []},
                signal=signal,
                source="stale",
                quality="stale" if stale.quality == "confirmed" else stale.quality,
                rate_limited=bool(result.rate_limited),
                circuit_open=bool(result.circuit_open),
                error=result.error,
            )

    empty = {"response": []}
    if result.rate_limited or result.circuit_open:
        try:
            cache.set(key, signal, empty, quality="error", ttl_sec=min(60.0, ttl))
        except Exception:
            pass
    return FetchOutcome(
        ok=False,
        data=empty,
        signal=signal,
        source="error",
        quality="rate_limited" if result.rate_limited else "missing",
        rate_limited=bool(result.rate_limited),
        circuit_open=bool(result.circuit_open),
        error=result.error,
    )


async def fetch_fixtures(
    params: dict[str, Any],
    *,
    status_short: str | None = None,
) -> FetchOutcome:
    return await fetch_signal("fixture", "/fixtures", params, status_short=status_short)


async def fetch_status(fixture_id: int) -> FetchOutcome:
    return await fetch_signal(
        "status",
        "/fixtures",
        {"id": fixture_id},
        status_short=None,
    )


async def fetch_statistics(
    fixture_id: int, *, status_short: str | None = None
) -> FetchOutcome:
    return await fetch_signal(
        "statistics",
        "/fixtures/statistics",
        {"fixture": fixture_id},
        status_short=status_short,
    )


async def fetch_standings(
    league_id: int, season: int, *, status_short: str | None = None
) -> FetchOutcome:
    return await fetch_signal(
        "standings",
        "/standings",
        {"league": league_id, "season": season},
        status_short=status_short,
    )


async def fetch_events(
    fixture_id: int, *, status_short: str | None = None
) -> FetchOutcome:
    return await fetch_signal(
        "events",
        "/fixtures/events",
        {"fixture": fixture_id},
        status_short=status_short,
    )


async def fetch_lineups(
    fixture_id: int, *, status_short: str | None = None
) -> FetchOutcome:
    return await fetch_signal(
        "lineups",
        "/fixtures/lineups",
        {"fixture": fixture_id},
        status_short=status_short,
    )


async def fetch_odds(
    fixture_id: int, *, status_short: str | None = None
) -> FetchOutcome:
    return await fetch_signal(
        "odds",
        "/odds",
        {"fixture": fixture_id},
        status_short=status_short,
    )


async def fetch_injuries(
    fixture_id: int, *, status_short: str | None = None
) -> FetchOutcome:
    return await fetch_signal(
        "injuries",
        "/injuries",
        {"fixture": fixture_id},
        status_short=status_short,
    )


async def fetch_calendar_by_date(
    date_yyyy_mm_dd: str, *, status_short: str | None = None
) -> FetchOutcome:
    return await fetch_signal(
        "calendar",
        "/fixtures",
        {"date": date_yyyy_mm_dd},
        status_short=status_short,
    )
