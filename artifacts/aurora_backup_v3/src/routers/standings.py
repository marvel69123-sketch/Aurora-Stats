from fastapi import APIRouter, Query
from src.client import api_football_get

router = APIRouter()


@router.get("/")
async def get_standings(
    league: int = Query(..., description="League ID"),
    season: int = Query(..., description="Season year (e.g. 2024)"),
):
    """Get league standings/table for a specific season."""
    data = await api_football_get("/standings", {"league": league, "season": season})
    response = data.get("response", [])
    if not response:
        return {"league": None, "standings": []}
    league_data = response[0].get("league", {})
    return {
        "league": {
            "id": league_data.get("id"),
            "name": league_data.get("name"),
            "country": league_data.get("country"),
            "logo": league_data.get("logo"),
            "season": league_data.get("season"),
        },
        "standings": league_data.get("standings", []),
    }
