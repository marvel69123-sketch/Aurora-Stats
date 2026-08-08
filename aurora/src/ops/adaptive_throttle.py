"""
P3-A.2 — Adaptive throttling, backoff, and request budget.

Ops-only. Does not modify engines, Gateway internals, NMB, or DRS.
Wraps an async fetcher used by certification / analyze gateway.set_fetcher.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

Fetcher = Callable[[str, dict[str, Any] | None], Awaitable[dict[str, Any]]]


@dataclass
class RequestBudget:
    """Hard cap on outbound provider calls for a certification run."""

    max_requests: int = 400
    used: int = 0
    rejected: int = 0

    @property
    def remaining(self) -> int:
        return max(0, self.max_requests - self.used)

    def allow(self) -> bool:
        return self.used < self.max_requests

    def consume(self, n: int = 1) -> bool:
        if self.used + n > self.max_requests:
            self.rejected += 1
            return False
        self.used += n
        return True

    def as_dict(self) -> dict[str, int]:
        return {
            "max_requests": self.max_requests,
            "used": self.used,
            "remaining": self.remaining,
            "rejected": self.rejected,
        }


@dataclass
class AdaptiveThrottle:
    """
    Adaptive inter-request delay + exponential backoff on 429/5xx.

    - Speeds up slightly after consecutive successes (floor = min_delay_sec)
    - Slows on high latency or failures
    - Hard backoff on rate-limit signals
    """

    min_delay_sec: float = 0.15
    max_delay_sec: float = 8.0
    current_delay_sec: float = 0.35
    backoff_factor: float = 2.0
    success_shrink: float = 0.92
    latency_slow_ms: float = 2500.0
    budget: RequestBudget = field(default_factory=RequestBudget)
    consecutive_successes: int = 0
    consecutive_failures: int = 0
    rate_limit_hits: int = 0
    waits: int = 0
    total_wait_sec: float = 0.0
    _last_at: float = field(default_factory=time.monotonic)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def acquire(self) -> None:
        """Block until budget allows and spacing delay elapsed."""
        async with self._lock:
            if not self.budget.allow():
                self.budget.rejected += 1
                raise RuntimeError(
                    f"request_budget_exhausted used={self.budget.used}/{self.budget.max_requests}"
                )
            now = time.monotonic()
            wait = self.current_delay_sec - (now - self._last_at)
            if wait > 0:
                self.waits += 1
                self.total_wait_sec += wait
                await asyncio.sleep(wait)
            if not self.budget.consume(1):
                raise RuntimeError(
                    f"request_budget_exhausted used={self.budget.used}/{self.budget.max_requests}"
                )
            self._last_at = time.monotonic()

    def on_success(self, latency_ms: float = 0.0) -> None:
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        # High latency → gentle slowdown; else shrink toward min
        if latency_ms >= self.latency_slow_ms:
            self.current_delay_sec = min(
                self.max_delay_sec, self.current_delay_sec * 1.15
            )
        elif self.consecutive_successes >= 3:
            self.current_delay_sec = max(
                self.min_delay_sec, self.current_delay_sec * self.success_shrink
            )

    def on_failure(self, *, rate_limited: bool = False) -> None:
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        factor = self.backoff_factor * (1.25 if rate_limited else 1.0)
        if rate_limited:
            self.rate_limit_hits += 1
        self.current_delay_sec = min(
            self.max_delay_sec, max(self.min_delay_sec, self.current_delay_sec * factor)
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "current_delay_sec": round(self.current_delay_sec, 4),
            "min_delay_sec": self.min_delay_sec,
            "max_delay_sec": self.max_delay_sec,
            "consecutive_successes": self.consecutive_successes,
            "consecutive_failures": self.consecutive_failures,
            "rate_limit_hits": self.rate_limit_hits,
            "waits": self.waits,
            "total_wait_sec": round(self.total_wait_sec, 3),
            "budget": self.budget.as_dict(),
        }


def is_rate_limit_error(detail: str) -> bool:
    d = (detail or "").lower()
    return (
        "429" in d
        or "rate limit" in d
        or "too many" in d
        or "quota" in d
    )


def wrap_fetcher(
    inner: Fetcher,
    throttle: AdaptiveThrottle,
    *,
    on_call: Callable[[str, bool, float, str | None], None] | None = None,
) -> Fetcher:
    """Return a fetcher that applies budget + adaptive delay + backoff."""

    async def throttled(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        await throttle.acquire()
        t0 = time.perf_counter()
        try:
            data = await inner(path, params)
            ms = (time.perf_counter() - t0) * 1000.0
            throttle.on_success(ms)
            if on_call:
                on_call(path, True, ms, None)
            return data
        except Exception as exc:
            ms = (time.perf_counter() - t0) * 1000.0
            detail = str(exc)
            rl = is_rate_limit_error(detail)
            throttle.on_failure(rate_limited=rl)
            if on_call:
                on_call(path, False, ms, detail[:200])
            # Optional short hard sleep on 429 beyond adaptive delay
            if rl:
                await asyncio.sleep(min(throttle.max_delay_sec, throttle.current_delay_sec))
            raise

    return throttled


def lite_throttle_defaults() -> AdaptiveThrottle:
    """Smaller budget / slightly safer spacing for lite certification."""
    return AdaptiveThrottle(
        min_delay_sec=0.25,
        max_delay_sec=10.0,
        current_delay_sec=0.5,
        budget=RequestBudget(max_requests=180),
    )


def full_throttle_defaults() -> AdaptiveThrottle:
    return AdaptiveThrottle(
        min_delay_sec=0.12,
        max_delay_sec=8.0,
        current_delay_sec=0.3,
        budget=RequestBudget(max_requests=900),
    )
