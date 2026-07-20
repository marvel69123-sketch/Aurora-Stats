"""Emergency Cost Protection Mode — unit tests (no API / engines)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from src.ops import cost_protection as ecpm
from src.data.ingest import fetch_signal


def setup_function():
    ecpm.reset_cost_protection_for_tests()
    ecpm.configure(enabled=True, daily_limit_per_user=12, prefer_cache=True, allow_stale=True)


def test_daily_budget_limit():
    tokens = ecpm.begin_request("user-a", force_refresh=False)
    try:
        for _ in range(12):
            d = ecpm.consume_query()
            assert d.allowed
        d = ecpm.consume_query()
        assert not d.allowed
        assert d.reason == "daily_budget_exhausted"
        assert d.remaining == 0
        m = ecpm.metrics("user-a")
        assert m["daily_budget_remaining"]["user-a"] == 0
        assert m["users"]["user-a"]["queries"] == 12
    finally:
        ecpm.end_request(tokens)


def test_network_unrestricted_outside_request_scope():
    assert ecpm.network_allowed() is True
    assert ecpm.prefer_stale_cache() is False


def test_prefer_stale_for_simple_not_premium():
    tokens = ecpm.begin_request("u1", force_refresh=False)
    try:
        assert ecpm.prefer_stale_cache() is True
        assert ecpm.is_force_refresh() is False
    finally:
        ecpm.end_request(tokens)

    tokens = ecpm.begin_request("u1", force_refresh=True)
    try:
        assert ecpm.prefer_stale_cache() is False
        assert ecpm.is_force_refresh() is True
    finally:
        ecpm.end_request(tokens)


def test_analyze_cache_dedup():
    key = ecpm.analyze_cache_key("A", "B", 1)
    ecpm.set_cached_analyze(key, {"fixture": {"id": 1}, "ok": True})
    got = ecpm.get_cached_analyze(key)
    assert got is not None
    assert got["ok"] is True


def test_fetch_signal_prefers_stale_under_ecpm():
    async def _run():
        tokens = ecpm.begin_request("u2", force_refresh=False)
        try:
            class _Ent:
                quality = "confirmed"
                payload = {"response": [{"id": 1}]}

            with patch("src.data.ingest.get_cache") as gc, patch(
                "src.data.ingest.get_gateway"
            ) as gg:
                cache = gc.return_value
                cache.get.side_effect = [None, _Ent()]  # fresh miss, then stale hit
                gateway = gg.return_value
                gateway.get = AsyncMock(
                    side_effect=AssertionError("network must not be called")
                )
                out = await fetch_signal("statistics", "/fixtures/statistics", {"fixture": 1})
                assert out.source == "stale"
                assert out.ok is True
        finally:
            ecpm.end_request(tokens)

    asyncio.run(_run())


def test_metrics_keys():
    tokens = ecpm.begin_request("u3", force_refresh=True)
    try:
        ecpm.consume_query(force_refresh=True)
        ecpm.record_cache_hit()
        ecpm.record_cache_miss()
        ecpm.record_provider_call(n=2)
        m = ecpm.metrics("u3")
        assert "cache_hit_rate" in m
        assert "provider_calls_per_user" in m
        assert "daily_budget_remaining" in m
        assert m["provider_calls_per_user"]["u3"] == 2
        assert m["daily_budget_remaining"]["u3"] == 11
    finally:
        ecpm.end_request(tokens)
