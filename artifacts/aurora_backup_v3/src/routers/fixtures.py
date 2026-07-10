from typing import Optional
from fastapi import APIRouter, Query
from src.client import api_football_get

router = APIRouter()


@router.get("/live")
async def get_live_fixtures(
    league: Optional[int] = Query(None, description="Filter by league ID"),
):
    """Get all currently live fixtures, optionally filtered by league."""
    params = {"live": "all"}
    if league:
        params["league"] = league
    data = await api_football_get("/fixtures", params)
    return {
        "total": data.get("results", 0),
        "fixtures": data.get("response", []),
    }


@router.get("/{fixture_id}/statistics")
async def get_fixture_statistics(fixture_id: int):
    """Get detailed statistics for a specific fixture."""
    data = await api_football_get("/fixtures/statistics", {"fixture": fixture_id})
    return {
        "fixture_id": fixture_id,
        "statistics": data.get("response", []),
    }


@router.get("/{fixture_id}/events")
async def get_fixture_events(fixture_id: int):
    """Get all events (goals, cards, substitutions) for a fixture."""
    data = await api_football_get("/fixtures/events", {"fixture": fixture_id})
    return {
        "fixture_id": fixture_id,
        "events": data.get("response", []),
    }


@router.get("/{fixture_id}/lineups")
async def get_fixture_lineups(fixture_id: int):
    """Get team lineups for a fixture."""
    data = await api_football_get("/fixtures/lineups", {"fixture": fixture_id})
    return {
        "fixture_id": fixture_id,
        "lineups": data.get("response", []),
    }


@router.get("/{fixture_id}/players")
async def get_fixture_players(fixture_id: int):
    """Get player statistics for a fixture."""
    data = await api_football_get("/fixtures/players", {"fixture": fixture_id})
    return {
        "fixture_id": fixture_id,
        "players": data.get("response", []),
    }


@router.get("/")
async def get_fixtures(
    league: Optional[int] = Query(None, description="League ID"),
    season: Optional[int] = Query(None, description="Season year (e.g. 2024)"),
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    team: Optional[int] = Query(None, description="Team ID"),
    status: Optional[str] = Query(None, description="Fixture status (e.g. NS, FT, 1H)"),
    last: Optional[int] = Query(None, description="Get last N fixtures"),
    next: Optional[int] = Query(None, description="Get next N fixtures"),
):
    """Query fixtures by various filters."""
    params = {}
    if league:
        params["league"] = league
    if season:
        params["season"] = season
    if date:
        params["date"] = date
    if team:
        params["team"] = team
    if status:
        params["status"] = status
    if last:
        params["last"] = last
    if next:
        params["next"] = next
    data = await api_football_get("/fixtures", params)
    return {
        "total": data.get("results", 0),
        "fixtures": data.get("response", []),
    }
