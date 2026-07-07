import asyncio
from fastapi import APIRouter
from src.client import api_football_get

router = APIRouter()


def _extract_stat(team_stats: list, stat_name: str):
    """Pull a single stat value out of a team's statistics list."""
    for s in team_stats:
        if s.get("type") == stat_name:
            val = s.get("value")
            if val is None or val == "":
                return None
            return val
    return None


def _build_team_stats(raw_stats: list, team_index: int) -> dict:
    """Build the stats dict for one team from the /fixtures/statistics response."""
    if not raw_stats or team_index >= len(raw_stats):
        return {
            "possession": None,
            "shots_on_target": None,
            "shots_total": None,
            "corners": None,
            "fouls": None,
            "offsides": None,
            "saves": None,
            "xg": None,
        }
    team_stat_list = raw_stats[team_index].get("statistics", [])
    return {
        "possession": _extract_stat(team_stat_list, "Ball Possession"),
        "shots_on_target": _extract_stat(team_stat_list, "Shots on Goal"),
        "shots_total": _extract_stat(team_stat_list, "Total Shots"),
        "corners": _extract_stat(team_stat_list, "Corner Kicks"),
        "fouls": _extract_stat(team_stat_list, "Fouls"),
        "offsides": _extract_stat(team_stat_list, "Offsides"),
        "saves": _extract_stat(team_stat_list, "Goalkeeper Saves"),
        "xg": _extract_stat(team_stat_list, "expected_goals"),
    }


def _count_cards(events: list, team_id: int, card_type: str) -> int:
    """Count yellow or red cards from embedded fixture events for a given team."""
    return sum(
        1
        for e in events
        if e.get("type") == "Card"
        and e.get("detail") == card_type
        and e.get("team", {}).get("id") == team_id
    )


async def _fetch_stats(fixture_id: int) -> tuple[int, list]:
    """Fetch statistics for one fixture; returns (id, raw_stats) even on error."""
    try:
        result = await api_football_get("/fixtures/statistics", {"fixture": fixture_id})
        return fixture_id, result.get("response", [])
    except Exception:
        return fixture_id, []


@router.get("/live")
async def get_live_matches():
    """
    Return all currently live fixtures enriched with:
    - fixture id, score, minute
    - statistics: possession, shots on target, shots total, corners, fouls,
      offsides, goalkeeper saves
    - xG (expected goals) when available
    - cards (yellow / red) per team derived from inline events
    """
    live_data = await api_football_get("/fixtures", {"live": "all"})
    fixtures = live_data.get("response", [])

    if not fixtures:
        return {"total": 0, "matches": []}

    # Fetch statistics for every live fixture in parallel
    fixture_ids = [f["fixture"]["id"] for f in fixtures]
    stats_results = await asyncio.gather(*[_fetch_stats(fid) for fid in fixture_ids])
    stats_map: dict[int, list] = {fid: raw for fid, raw in stats_results}

    matches = []
    for fixture in fixtures:
        fid = fixture["fixture"]["id"]
        raw_stats = stats_map.get(fid, [])
        events: list = fixture.get("events", [])

        home_id = fixture["teams"]["home"]["id"]
        away_id = fixture["teams"]["away"]["id"]

        match = {
            "fixture_id": fid,
            "date": fixture["fixture"]["date"],
            "status": {
                "long": fixture["fixture"]["status"]["long"],
                "short": fixture["fixture"]["status"]["short"],
                "minute": fixture["fixture"]["status"].get("elapsed"),
                "extra_time": fixture["fixture"]["status"].get("extra"),
            },
            "league": {
                "id": fixture["league"]["id"],
                "name": fixture["league"]["name"],
                "country": fixture["league"]["country"],
                "logo": fixture["league"]["logo"],
                "flag": fixture["league"].get("flag"),
                "round": fixture["league"]["round"],
            },
            "home": {
                "id": home_id,
                "name": fixture["teams"]["home"]["name"],
                "logo": fixture["teams"]["home"]["logo"],
                "score": fixture["goals"]["home"],
                "halftime_score": fixture["score"]["halftime"]["home"],
                "yellow_cards": _count_cards(events, home_id, "Yellow Card"),
                "red_cards": _count_cards(events, home_id, "Red Card"),
                "statistics": _build_team_stats(raw_stats, 0),
            },
            "away": {
                "id": away_id,
                "name": fixture["teams"]["away"]["name"],
                "logo": fixture["teams"]["away"]["logo"],
                "score": fixture["goals"]["away"],
                "halftime_score": fixture["score"]["halftime"]["away"],
                "yellow_cards": _count_cards(events, away_id, "Yellow Card"),
                "red_cards": _count_cards(events, away_id, "Red Card"),
                "statistics": _build_team_stats(raw_stats, 1),
            },
        }
        matches.append(match)

    return {"total": len(matches), "matches": matches}
