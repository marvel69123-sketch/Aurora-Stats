from typing import Optional
from fastapi import APIRouter, Query
from src.client import api_football_get

router = APIRouter()


@router.get("/")
async def get_players(
    league: Optional[int] = Query(None, description="League ID"),
    season: Optional[int] = Query(None, description="Season year (e.g. 2024)"),
    team: Optional[int] = Query(None, description="Team ID"),
    search: Optional[str] = Query(None, description="Search by player name (min 3 chars)"),
    page: int = Query(1, description="Page number for pagination"),
):
    """Get player statistics. Requires league+season or team+season."""
    params = {"page": page}
    if league:
        params["league"] = league
    if season:
        params["season"] = season
    if team:
        params["team"] = team
    if search:
        params["search"] = search
    data = await api_football_get("/players", params)
    return {
        "total": data.get("results", 0),
        "paging": data.get("paging", {}),
        "players": data.get("response", []),
    }


@router.get("/top-scorers")
async def get_top_scorers(
    league: int = Query(..., description="League ID"),
    season: int = Query(..., description="Season year"),
):
    """Get top scorers for a league and season."""
    data = await api_football_get("/players/topscorers", {"league": league, "season": season})
    return {
        "total": data.get("results", 0),
        "players": data.get("response", []),
    }


@router.get("/top-assists")
async def get_top_assists(
    league: int = Query(..., description="League ID"),
    season: int = Query(..., description="Season year"),
):
    """Get top assist providers for a league and season."""
    data = await api_football_get("/players/topassists", {"league": league, "season": season})
    return {
        "total": data.get("results", 0),
        "players": data.get("response", []),
    }


@router.get("/{player_id}")
async def get_player(
    player_id: int,
    season: int = Query(..., description="Season year"),
):
    """Get statistics for a specific player in a season."""
    data = await api_football_get("/players", {"id": player_id, "season": season})
    results = data.get("response", [])
    return results[0] if results else {}
