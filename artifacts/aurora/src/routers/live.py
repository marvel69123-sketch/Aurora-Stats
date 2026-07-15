import asyncio
import time
from fastapi import APIRouter
from src.client import api_football_get

router = APIRouter()

_CACHE_TTL = 30
_cache: dict = {"data": None, "expires_at": 0.0}

_EMPTY_STATS = {
    "possession": None,
    "shots_on_target": None,
    "shots_total": None,
    "corners": None,
    "fouls": None,
    "offsides": None,
    "saves": None,
    "xg": None,
}


def _extract_stat(team_stats: list, stat_name: str):
    for s in team_stats:
        if s.get("type") == stat_name:
            val = s.get("value")
            if val is None or val == "":
                return None
            return val
    return None


def _as_int_or_none(val) -> int | None:
    """Coerce API numeric/string stats to int; never invent 0 for missing."""
    if val is None or val == "":
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)
    try:
        return int(float(str(val).strip().replace("%", "")))
    except (TypeError, ValueError):
        return None


def _team_stat_list(raw_stats: list, team_id: int) -> list | None:
    """
    Resolve statistics block by team.id only.
    Never fall back to array index — index order is not guaranteed home/away.
    Returns None when the team block is absent (caller must treat as unavailable).
    """
    if not raw_stats or team_id is None:
        return None
    for block in raw_stats:
        if block.get("team", {}).get("id") == team_id:
            return block.get("statistics") or []
    return None


def _build_team_stats_for_id(raw_stats: list, team_id: int) -> dict:
    team_stat_list = _team_stat_list(raw_stats, team_id)
    if team_stat_list is None:
        return dict(_EMPTY_STATS)
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


def _count_cards(events: list, team_id: int, card_details: tuple[str, ...]) -> int:
    return sum(
        1
        for e in events
        if e.get("type") == "Card"
        and e.get("detail") in card_details
        and e.get("team", {}).get("id") == team_id
    )


def _resolve_cards(
    team_stat_list: list | None,
    events: list,
    team_id: int,
    *,
    stats_type: str,
    event_details: tuple[str, ...],
) -> int | None:
    """
    Cards only from confirmed sources:
    1) /fixtures/statistics type (Yellow Cards / Red Cards)
    2) non-empty events list (count matching Card events)
    Otherwise None — never invent 0 from an empty events payload.
    """
    if team_stat_list is not None:
        from_stats = _as_int_or_none(_extract_stat(team_stat_list, stats_type))
        if from_stats is not None:
            return from_stats
    if events:
        return _count_cards(events, team_id, event_details)
    return None


async def _fetch_stats(fixture_id: int) -> tuple[int, list]:
    try:
        result = await api_football_get("/fixtures/statistics", {"fixture": fixture_id})
        return fixture_id, result.get("response", [])
    except Exception:
        return fixture_id, []


async def _build_live_response() -> dict:
    live_data = await api_football_get("/fixtures", {"live": "all"})
    fixtures = live_data.get("response", [])

    if not fixtures:
        return {"total": 0, "cached": False, "matches": []}

    fixture_ids = [f["fixture"]["id"] for f in fixtures]
    stats_results = await asyncio.gather(*[_fetch_stats(fid) for fid in fixture_ids])
    stats_map: dict[int, list] = {fid: raw for fid, raw in stats_results}

    matches = []
    for fixture in fixtures:
        fid = fixture["fixture"]["id"]
        raw_stats = stats_map.get(fid, [])
        events: list = fixture.get("events") or []
        home_id = fixture["teams"]["home"]["id"]
        away_id = fixture["teams"]["away"]["id"]

        home_stat_list = _team_stat_list(raw_stats, home_id)
        away_stat_list = _team_stat_list(raw_stats, away_id)

        matches.append({
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
                "yellow_cards": _resolve_cards(
                    home_stat_list,
                    events,
                    home_id,
                    stats_type="Yellow Cards",
                    event_details=("Yellow Card",),
                ),
                "red_cards": _resolve_cards(
                    home_stat_list,
                    events,
                    home_id,
                    stats_type="Red Cards",
                    event_details=("Red Card", "Yellow Red Card"),
                ),
                "statistics": _build_team_stats_for_id(raw_stats, home_id),
            },
            "away": {
                "id": away_id,
                "name": fixture["teams"]["away"]["name"],
                "logo": fixture["teams"]["away"]["logo"],
                "score": fixture["goals"]["away"],
                "halftime_score": fixture["score"]["halftime"]["away"],
                "yellow_cards": _resolve_cards(
                    away_stat_list,
                    events,
                    away_id,
                    stats_type="Yellow Cards",
                    event_details=("Yellow Card",),
                ),
                "red_cards": _resolve_cards(
                    away_stat_list,
                    events,
                    away_id,
                    stats_type="Red Cards",
                    event_details=("Red Card", "Yellow Red Card"),
                ),
                "statistics": _build_team_stats_for_id(raw_stats, away_id),
            },
        })

    return {"total": len(matches), "cached": False, "matches": matches}


@router.get("/live")
async def get_live_matches():
    """
    Return all currently live fixtures enriched with score, minute, statistics
    (possession, shots on target, corners, fouls, offsides, saves, xG), and
    card counts per team. Results are cached for 30 seconds to protect API quota.

    Credibility: missing stats/cards are null — never invented zeros or index-swapped sides.
    """
    now = time.monotonic()
    if _cache["data"] is not None and now < _cache["expires_at"]:
        payload = dict(_cache["data"])
        payload["cached"] = True
        return payload

    result = await _build_live_response()
    _cache["data"] = result
    _cache["expires_at"] = now + _CACHE_TTL
    return result
