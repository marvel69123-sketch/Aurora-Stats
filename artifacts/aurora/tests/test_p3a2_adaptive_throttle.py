"""P3-A.2 — adaptive throttle / backoff / request budget unit tests (no API)."""

from __future__ import annotations

import asyncio

import pytest

from src.ops.adaptive_throttle import (
    AdaptiveThrottle,
    RequestBudget,
    full_throttle_defaults,
    is_rate_limit_error,
    lite_throttle_defaults,
    wrap_fetcher,
)


def test_request_budget_consume_and_reject():
    b = RequestBudget(max_requests=3)
    assert b.consume() is True
    assert b.consume() is True
    assert b.consume() is True
    assert b.allow() is False
    assert b.consume() is False
    assert b.rejected == 1
    assert b.used == 3
    assert b.remaining == 0


def test_backoff_increases_on_failure_and_429():
    t = AdaptiveThrottle(min_delay_sec=0.1, max_delay_sec=8.0, current_delay_sec=0.5)
    base = t.current_delay_sec
    t.on_failure(rate_limited=False)
    assert t.current_delay_sec > base
    after_fail = t.current_delay_sec
    t.on_failure(rate_limited=True)
    assert t.current_delay_sec > after_fail
    assert t.rate_limit_hits == 1


def test_success_shrinks_delay_after_streak():
    t = AdaptiveThrottle(
        min_delay_sec=0.1,
        max_delay_sec=8.0,
        current_delay_sec=1.0,
        success_shrink=0.9,
    )
    t.on_success(100.0)
    t.on_success(100.0)
    before = t.current_delay_sec
    t.on_success(100.0)  # 3rd consecutive → shrink
    assert t.current_delay_sec < before
    assert t.current_delay_sec >= t.min_delay_sec


def test_high_latency_slows_down():
    t = AdaptiveThrottle(min_delay_sec=0.1, max_delay_sec=8.0, current_delay_sec=0.5)
    before = t.current_delay_sec
    t.on_success(4000.0)
    assert t.current_delay_sec > before


def test_is_rate_limit_error():
    assert is_rate_limit_error("HTTP 429 Too Many Requests")
    assert is_rate_limit_error("rate limit exceeded")
    assert not is_rate_limit_error("timeout connecting")


def test_acquire_respects_budget():
    async def _run():
        t = AdaptiveThrottle(
            min_delay_sec=0.0,
            max_delay_sec=1.0,
            current_delay_sec=0.0,
            budget=RequestBudget(max_requests=2),
        )
        await t.acquire()
        await t.acquire()
        with pytest.raises(RuntimeError, match="request_budget_exhausted"):
            await t.acquire()

    asyncio.run(_run())


def test_wrap_fetcher_success_and_failure():
    async def _run():
        throttle = AdaptiveThrottle(
            min_delay_sec=0.0,
            max_delay_sec=1.0,
            current_delay_sec=0.0,
            budget=RequestBudget(max_requests=10),
        )
        calls: list[str] = []

        async def inner(path: str, params=None):
            calls.append(path)
            if path == "/fail":
                raise RuntimeError("429 rate limit")
            return {"ok": True, "path": path}

        fetcher = wrap_fetcher(inner, throttle)
        data = await fetcher("/ok", None)
        assert data["ok"] is True
        assert throttle.consecutive_successes >= 1
        with pytest.raises(RuntimeError):
            await fetcher("/fail", None)
        assert throttle.rate_limit_hits >= 1
        assert throttle.budget.used == 2

    asyncio.run(_run())


def test_lite_vs_full_defaults():
    lite = lite_throttle_defaults()
    full = full_throttle_defaults()
    assert lite.budget.max_requests < full.budget.max_requests
    assert lite.current_delay_sec >= full.current_delay_sec
