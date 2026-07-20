"""
P2b Wave 1 — API Ingestion Gateway.

Token bucket + circuit breaker + singleflight around provider GETs.
Never invents payloads.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

Fetcher = Callable[[str, dict[str, Any] | None], Awaitable[dict[str, Any]]]


@dataclass
class GatewayStats:
    requests: int = 0
    cache_bypass_fetches: int = 0
    rate_limited: int = 0
    failures: int = 0
    circuit_open_rejects: int = 0
    singleflight_joins: int = 0
    successes: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "requests": self.requests,
            "cache_bypass_fetches": self.cache_bypass_fetches,
            "rate_limited": self.rate_limited,
            "failures": self.failures,
            "circuit_open_rejects": self.circuit_open_rejects,
            "singleflight_joins": self.singleflight_joins,
            "successes": self.successes,
        }


@dataclass
class TokenBucket:
    rate_per_sec: float = 8.0
    capacity: float = 16.0
    tokens: float = 16.0
    updated_at: float = field(default_factory=time.monotonic)

    def allow(self, cost: float = 1.0) -> bool:
        now = time.monotonic()
        elapsed = now - self.updated_at
        self.updated_at = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate_per_sec)
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    recovery_sec: float = 30.0
    failures: int = 0
    opened_at: float | None = None
    state: str = "closed"  # closed | open | half_open

    def allow_request(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            if self.opened_at is None:
                return False
            if time.monotonic() - self.opened_at >= self.recovery_sec:
                self.state = "half_open"
                return True
            return False
        return True  # half_open probe

    def on_success(self) -> None:
        self.failures = 0
        self.state = "closed"
        self.opened_at = None

    def on_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold or self.state == "half_open":
            self.state = "open"
            self.opened_at = time.monotonic()


@dataclass
class GatewayResult:
    ok: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    rate_limited: bool = False
    circuit_open: bool = False
    from_singleflight: bool = False


class DataGateway:
    """Shared gateway instance for Wave 1 fetches."""

    def __init__(
        self,
        fetcher: Fetcher | None = None,
        *,
        rate_per_sec: float = 8.0,
        capacity: float = 16.0,
    ) -> None:
        self._fetcher = fetcher
        self.bucket = TokenBucket(rate_per_sec=rate_per_sec, capacity=capacity, tokens=capacity)
        self.breaker = CircuitBreaker()
        self.stats = GatewayStats()
        self._inflight: dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()

    def set_fetcher(self, fetcher: Fetcher) -> None:
        self._fetcher = fetcher

    def _flight_key(self, path: str, params: dict[str, Any] | None) -> str:
        items = tuple(sorted((params or {}).items(), key=lambda x: str(x[0])))
        return f"{path}?{items!r}"

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        signal: str = "unknown",
    ) -> GatewayResult:
        self.stats.requests += 1
        if not self.breaker.allow_request():
            self.stats.circuit_open_rejects += 1
            return GatewayResult(
                ok=False,
                error="circuit_open",
                circuit_open=True,
            )
        if not self.bucket.allow(1.0):
            self.stats.rate_limited += 1
            return GatewayResult(
                ok=False,
                error="token_bucket_rate_limited",
                rate_limited=True,
            )

        key = self._flight_key(path, params)
        async with self._lock:
            existing = self._inflight.get(key)
            if existing is not None:
                self.stats.singleflight_joins += 1
                waiter = True
            else:
                loop = asyncio.get_event_loop()
                fut: asyncio.Future = loop.create_future()
                self._inflight[key] = fut
                existing = fut
                waiter = False

        if waiter:
            try:
                data = await existing
                return GatewayResult(ok=True, data=data, from_singleflight=True)
            except Exception as exc:
                return GatewayResult(ok=False, error=str(exc), from_singleflight=True)

        try:
            self.stats.cache_bypass_fetches += 1
            data = await self._do_fetch(path, params)
            self.breaker.on_success()
            self.stats.successes += 1
            if not existing.done():
                existing.set_result(data)
            return GatewayResult(ok=True, data=data)
        except Exception as exc:
            detail = str(exc)
            self.stats.failures += 1
            self.breaker.on_failure()
            rate = "429" in detail or "rate" in detail.lower() or "too many" in detail.lower()
            if rate:
                self.stats.rate_limited += 1
            if not existing.done():
                existing.set_exception(exc)
                # Avoid "Future exception was never retrieved" when no waiters joined
                existing.add_done_callback(lambda f: f.exception())
            return GatewayResult(
                ok=False,
                error=detail,
                rate_limited=rate,
            )
        finally:
            async with self._lock:
                self._inflight.pop(key, None)

    async def _do_fetch(
        self, path: str, params: dict[str, Any] | None
    ) -> dict[str, Any]:
        if self._fetcher is not None:
            return await self._fetcher(path, params)
        from src.client import api_football_get

        return await api_football_get(path, params or {})


_GATEWAY: DataGateway | None = None


def get_gateway() -> DataGateway:
    global _GATEWAY
    if _GATEWAY is None:
        _GATEWAY = DataGateway()
    return _GATEWAY


def reset_gateway_for_tests(gateway: DataGateway | None = None) -> DataGateway:
    global _GATEWAY
    _GATEWAY = gateway if gateway is not None else DataGateway()
    return _GATEWAY
