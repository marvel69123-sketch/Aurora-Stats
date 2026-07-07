from typing import Optional
from fastapi import APIRouter, Query
from src.client import api_football_get

router = APIRouter()


@router.get("/")
async def get_leagues(
    country: Optional[str] = Query(None, description="Country name"),
    season: Optional[int] = Query(None, description="Season year (e.g. 2024)"),
    current: Optional[bool] = Query(None, description="Filter to currently active leagues"),
    search: Optional[str] = Query(None, description="Search by league name (min 3 chars)"),
):
    """Get leagues, optionally filtered by country, season, or name."""
    params = {}
    if country:
        params["country"] = country
    if season:
        params["season"] = season
    if current is not None:
        params["current"] = str(current).lower()
    if search:
        params["search"] = search
    data = await api_football_get("/leagues", params)
    return {
        "total": data.get("results", 0),
        "leagues": data.get("response", []),
    }


@router.get("/{league_id}")
async def get_league(league_id: int, season: Optional[int] = Query(None)):
    """Get a specific league by ID."""
    params = {"id": league_id}
    if season:
        params["season"] = season
    data = await api_football_get("/leagues", params)
    results = data.get("response", [])
    return results[0] if results else {}
