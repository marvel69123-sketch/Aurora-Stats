"""P3-A.6 — fixture_id bind skips name re-resolve (unit tests, mocked API)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from src.routers.analyze import _try_bind_fixture_by_id


def _fixture_row(fid: int = 42, home: str = "Alpha", away: str = "Beta") -> dict:
    return {
        "fixture": {
            "id": fid,
            "date": "2026-07-20T15:00:00+00:00",
            "timestamp": 1753023600,
            "referee": None,
            "venue": {"name": "Test Arena", "city": "Test City"},
            "status": {"short": "NS", "elapsed": None, "long": "Not Started"},
        },
        "league": {
            "id": 1,
            "name": "Test",
            "country": "World",
            "logo": "",
            "flag": None,
            "season": 2026,
            "round": "Regular Season - 1",
        },
        "teams": {
            "home": {"id": 1, "name": home, "logo": "", "winner": None},
            "away": {"id": 2, "name": away, "logo": "", "winner": None},
        },
        "goals": {"home": None, "away": None},
        "score": {
            "halftime": {"home": None, "away": None},
            "fulltime": {"home": None, "away": None},
        },
    }


def test_bind_by_id_success():
    async def _run():
        row = _fixture_row()
        with patch(
            "src.routers.analyze.api_football_get",
            new_callable=AsyncMock,
            return_value={"response": [row]},
        ) as mocked:
            got = await _try_bind_fixture_by_id(42, "Alpha", "Beta")
            assert got is not None
            assert got["fixture"]["id"] == 42
            mocked.assert_awaited_once_with("/fixtures", {"id": 42})

    asyncio.run(_run())


def test_bind_by_id_empty_falls_back():
    async def _run():
        with patch(
            "src.routers.analyze.api_football_get",
            new_callable=AsyncMock,
            return_value={"response": []},
        ):
            assert await _try_bind_fixture_by_id(99, "Alpha", "Beta") is None

    asyncio.run(_run())


def test_bind_by_id_http_error_falls_back():
    async def _run():
        with patch(
            "src.routers.analyze.api_football_get",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=404, detail="missing"),
        ):
            assert await _try_bind_fixture_by_id(99, "Alpha", "Beta") is None

    asyncio.run(_run())


def test_bind_trusts_id_on_name_soft_mismatch():
    async def _run():
        row = _fixture_row(home="Official Home", away="Official Away")
        with patch(
            "src.routers.analyze.api_football_get",
            new_callable=AsyncMock,
            return_value={"response": [row]},
        ):
            got = await _try_bind_fixture_by_id(42, "Totally Different", "Also Different")
            assert got is not None
            assert got["fixture"]["id"] == 42

    asyncio.run(_run())


def test_analyze_skips_name_resolve_when_fixture_id_binds():
    async def _run():
        row = _fixture_row(fid=777, home="Home FC", away="Away FC")

        async def fake_get(path, params=None):
            if path == "/fixtures" and (params or {}).get("id") == 777:
                return {"response": [row]}
            raise AssertionError(f"unexpected api call {path} {params}")

        from src.routers import analyze as analyze_mod

        class _Out:
            def __init__(self, data):
                self.ok = True
                self.data = data
                self.source = "cache"
                self.rate_limited = False
                self.circuit_open = False
                self.error = None
                self.quality = "ok"
                self.signal = "mock"

        with patch("src.routers.analyze.api_football_get", side_effect=fake_get), patch.object(
            analyze_mod,
            "_find_fixture",
            new_callable=AsyncMock,
            side_effect=AssertionError("name re-resolve must be skipped"),
        ), patch(
            "src.data.ingest.fetch_statistics",
            new_callable=AsyncMock,
            return_value=_Out({}),
        ), patch(
            "src.data.ingest.fetch_events",
            new_callable=AsyncMock,
            return_value=_Out([]),
        ), patch(
            "src.data.ingest.fetch_lineups",
            new_callable=AsyncMock,
            return_value=_Out({}),
        ), patch(
            "src.data.ingest.fetch_standings",
            new_callable=AsyncMock,
            return_value=_Out({}),
        ), patch(
            "src.data.ingest.fetch_status",
            new_callable=AsyncMock,
            return_value=_Out({}),
        ), patch(
            "src.data.ingest.fetch_odds",
            new_callable=AsyncMock,
            return_value=_Out({}),
        ), patch(
            "src.data.ingest.fetch_injuries",
            new_callable=AsyncMock,
            return_value=_Out({}),
        ), patch(
            "src.data.ingest.fetch_calendar_by_date",
            new_callable=AsyncMock,
            return_value=_Out({}),
        ):
            payload = await analyze_mod.analyze_fixture(
                home="Home FC",
                away="Away FC",
                soft=True,
                fixture_id=777,
            )
            assert int(payload["fixture"]["id"]) == 777

    asyncio.run(_run())
