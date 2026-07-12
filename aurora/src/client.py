import os
import httpx
from fastapi import HTTPException

API_FOOTBALL_BASE = "https://v3.football.api-sports.io"


def get_headers() -> dict:
    key = os.environ.get("API_FOOTBALL_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="API_FOOTBALL_KEY not configured")
    return {
        "x-apisports-key": key,
    }


async def api_football_get(path: str, params: dict = None) -> dict:
    headers = get_headers()
    url = f"{API_FOOTBALL_BASE}{path}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url, headers=headers, params=params or {})
    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"API-Football error: {response.text}",
        )
    data = response.json()
    errors = data.get("errors", {})
    if errors:
        raise HTTPException(status_code=400, detail=errors)
    return data
