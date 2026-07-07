from typing import Optional
from fastapi import APIRouter, Query
from src.client import api_football_get

router = APIRouter()


@router.get("/")
async def get_teams(
    league: Optional[int] = Query(None, description="League ID"),
    season: Optional[int] = Query(None, description="Season year (e.g. 2024)"),
    country: Optional[str] = Query(None, description="Country name"),
    search: Optional[str] = Query(None, description="Search by team name (min 3 chars)"),
):
    """Get teams by league, season, country, or search."""
    params = {}
    if league:
        params["league"] = league
    if season:
        params["season"] = season
    if country:
        params["country"] = country
    if search:
        params["search"] = search
    data = await api_football_get("/teams", params)
    return {
        "total": data.get("results", 0),
        "teams": data.get("response", []),
    }


@router.get("/{team_id}")
async def get_team(team_id: int):
    """Get a specific team by ID."""
    data = await api_football_get("/teams", {"id": team_id})
    results = data.get("response", [])
    return results[0] if results else {}


@router.get("/{team_id}/statistics")
async def get_team_statistics(
    team_id: int,
    league: int = Query(..., description="League ID (required)"),
    season: int = Query(..., description="Season year (required)"),
):
    """Get statistics for a team in a specific league and season."""
    data = await api_football_get(
        "/teams/statistics",
        {"team": team_id, "league": league, "season": season},
    )
    return data.get("response", {})
