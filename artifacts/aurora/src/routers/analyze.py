import asyncio
from fastapi import APIRouter, Query, HTTPException
from src.client import api_football_get

router = APIRouter()


# ---------------------------------------------------------------------------
# Team / fixture discovery
# ---------------------------------------------------------------------------

def _name_match(api_name: str, query: str) -> bool:
    """
    Return True when *query* (a resolved team name) matches *api_name*.

    Strategy:
      1. Fast substring check — "england" in "England" → True.
      2. Word-level fallback — every significant word of query (>2 chars)
         appears somewhere in api_name.  Handles "Borussia Dortmund" ↔
         "Dortmund" and multi-word national team variants.
    """
    api_lower = api_name.strip().lower()
    q_lower   = query.strip().lower()
    if q_lower in api_lower:
        return True
    # Word-level fallback (ignore tiny words like "fc", "de")
    words = [w for w in q_lower.split() if len(w) > 2]
    return bool(words) and all(w in api_lower for w in words)


async def _find_fixture(home: str, away: str) -> dict:
    """
    Return the best matching fixture for the supplied team names.
    Strategy:
      1. Check live fixtures first (zero extra API calls if match is in play).
      2. Search both teams by name to resolve their IDs.
      3. Pull last 5 + next 5 fixtures for the home team and find the one
         that also involves the away team.
    """
    # 1. Live sweep
    live_data = await api_football_get("/fixtures", {"live": "all"})
    for f in live_data.get("response", []):
        if (
            _name_match(f["teams"]["home"]["name"], home)
            and _name_match(f["teams"]["away"]["name"], away)
        ):
            return f

    # 2. Resolve team IDs in parallel
    home_res, away_res = await asyncio.gather(
        api_football_get("/teams", {"search": home}),
        api_football_get("/teams", {"search": away}),
    )
    home_teams = home_res.get("response", [])
    away_teams = away_res.get("response", [])

    if not home_teams:
        raise HTTPException(status_code=404, detail=f"No team found matching '{home}'")
    if not away_teams:
        raise HTTPException(status_code=404, detail=f"No team found matching '{away}'")

    home_id = home_teams[0]["team"]["id"]
    away_id = away_teams[0]["team"]["id"]
    home_name = home_teams[0]["team"]["name"]
    away_name = away_teams[0]["team"]["name"]

    # 3. Fetch recent + upcoming fixtures for the home team in parallel
    last_res, next_res = await asyncio.gather(
        api_football_get("/fixtures", {"team": home_id, "last": 10}),
        api_football_get("/fixtures", {"team": home_id, "next": 5}),
    )
    candidates = last_res.get("response", []) + next_res.get("response", [])

    for f in candidates:
        fh_id = f["teams"]["home"]["id"]
        fa_id = f["teams"]["away"]["id"]
        if fh_id == home_id and fa_id == away_id:
            return f

    raise HTTPException(
        status_code=404,
        detail=f"No fixture found between '{home_name}' and '{away_name}'"
        " in the last 10 or next 5 matches.",
    )


# ---------------------------------------------------------------------------
# Data transformers
# ---------------------------------------------------------------------------

def _extract_stat(stat_list: list, stat_name: str):
    for s in stat_list:
        if s.get("type") == stat_name:
            val = s.get("value")
            return None if (val is None or val == "") else val
    return None


def _build_team_stats(raw_stats: list, team_index: int, events: list, team_id: int) -> dict:
    stat_list: list = []
    if raw_stats and team_index < len(raw_stats):
        stat_list = raw_stats[team_index].get("statistics", [])

    yellow = sum(
        1 for e in events
        if e.get("type") == "Card"
        and e.get("detail") == "Yellow Card"
        and e.get("team", {}).get("id") == team_id
    )
    red = sum(
        1 for e in events
        if e.get("type") == "Card"
        and e.get("detail") in ("Red Card", "Yellow Red Card")
        and e.get("team", {}).get("id") == team_id
    )

    return {
        "possession": _extract_stat(stat_list, "Ball Possession"),
        "shots_total": _extract_stat(stat_list, "Total Shots"),
        "shots_on_target": _extract_stat(stat_list, "Shots on Goal"),
        "shots_off_target": _extract_stat(stat_list, "Shots off Goal"),
        "blocked_shots": _extract_stat(stat_list, "Blocked Shots"),
        "corners": _extract_stat(stat_list, "Corner Kicks"),
        "fouls": _extract_stat(stat_list, "Fouls"),
        "offsides": _extract_stat(stat_list, "Offsides"),
        "saves": _extract_stat(stat_list, "Goalkeeper Saves"),
        "passes_total": _extract_stat(stat_list, "Total passes"),
        "passes_accurate": _extract_stat(stat_list, "Passes accurate"),
        "pass_accuracy": _extract_stat(stat_list, "Passes %"),
        "xg": _extract_stat(stat_list, "expected_goals"),
        "yellow_cards": yellow,
        "red_cards": red,
    }


def _build_events(raw_events: list) -> list:
    return [
        {
            "minute": e.get("time", {}).get("elapsed"),
            "extra_minute": e.get("time", {}).get("extra"),
            "team": e.get("team", {}).get("name"),
            "team_id": e.get("team", {}).get("id"),
            "type": e.get("type"),
            "detail": e.get("detail"),
            "player": e.get("player", {}).get("name"),
            "player_id": e.get("player", {}).get("id"),
            "assist": e.get("assist", {}).get("name"),
            "assist_id": e.get("assist", {}).get("id"),
            "comments": e.get("comments"),
        }
        for e in raw_events
    ]


def _build_lineup(raw: dict) -> dict | None:
    if not raw:
        return None
    return {
        "formation": raw.get("formation"),
        "coach": {
            "id": raw.get("coach", {}).get("id"),
            "name": raw.get("coach", {}).get("name"),
            "photo": raw.get("coach", {}).get("photo"),
        },
        "starting_xi": [
            {
                "id": p["player"]["id"],
                "name": p["player"]["name"],
                "number": p["player"]["number"],
                "position": p["player"]["pos"],
                "grid": p["player"].get("grid"),
            }
            for p in raw.get("startXI", [])
        ],
        "substitutes": [
            {
                "id": p["player"]["id"],
                "name": p["player"]["name"],
                "number": p["player"]["number"],
                "position": p["player"]["pos"],
            }
            for p in raw.get("substitutes", [])
        ],
    }


def _find_standing(standings_table: list, team_id: int) -> dict | None:
    for group in standings_table:
        for entry in group:
            if entry.get("team", {}).get("id") == team_id:
                all_r = entry.get("all", {})
                home_r = entry.get("home", {})
                away_r = entry.get("away", {})
                return {
                    "rank": entry.get("rank"),
                    "points": entry.get("points"),
                    "played": all_r.get("played"),
                    "won": all_r.get("win"),
                    "drawn": all_r.get("draw"),
                    "lost": all_r.get("lose"),
                    "goals_for": all_r.get("goals", {}).get("for"),
                    "goals_against": all_r.get("goals", {}).get("against"),
                    "goal_difference": entry.get("goalsDiff"),
                    "form": entry.get("form"),
                    "home_record": {
                        "played": home_r.get("played"),
                        "won": home_r.get("win"),
                        "drawn": home_r.get("draw"),
                        "lost": home_r.get("lose"),
                        "goals_for": home_r.get("goals", {}).get("for"),
                        "goals_against": home_r.get("goals", {}).get("against"),
                    },
                    "away_record": {
                        "played": away_r.get("played"),
                        "won": away_r.get("win"),
                        "drawn": away_r.get("draw"),
                        "lost": away_r.get("lose"),
                        "goals_for": away_r.get("goals", {}).get("for"),
                        "goals_against": away_r.get("goals", {}).get("against"),
                    },
                    "description": entry.get("description"),
                }
    return None


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/analyze")
async def analyze_fixture(
    home: str = Query(..., description="Home team name (full or partial match)"),
    away: str = Query(..., description="Away team name (full or partial match)"),
):
    """
    Locate a fixture by team names and return a single structured JSON object
    containing fixture details, live statistics, match events, lineups, and
    league standings — ready for AI analysis.

    Discovery order:
    1. Live matches (if the game is currently in play)
    2. Recent / upcoming fixtures resolved via team search
    """
    # ── Step 1: resolve the fixture ─────────────────────────────────────────
    fixture = await _find_fixture(home, away)

    fixture_id: int = fixture["fixture"]["id"]
    league_id: int = fixture["league"]["id"]
    season: int = fixture["league"]["season"]
    home_id: int = fixture["teams"]["home"]["id"]
    away_id: int = fixture["teams"]["away"]["id"]

    # ── Step 2: fan out – all four calls happen simultaneously ───────────────
    stats_data, events_data, lineups_data, standings_data = await asyncio.gather(
        api_football_get("/fixtures/statistics", {"fixture": fixture_id}),
        api_football_get("/fixtures/events", {"fixture": fixture_id}),
        api_football_get("/fixtures/lineups", {"fixture": fixture_id}),
        api_football_get("/standings", {"league": league_id, "season": season}),
    )

    raw_stats: list = stats_data.get("response", [])
    raw_events: list = events_data.get("response", [])
    raw_lineups: list = lineups_data.get("response", [])

    standings_resp = standings_data.get("response", [])
    standings_table: list = (
        standings_resp[0].get("league", {}).get("standings", [])
        if standings_resp else []
    )

    # ── Step 3: match lineups to teams ──────────────────────────────────────
    home_lineup_raw = next(
        (l for l in raw_lineups if l.get("team", {}).get("id") == home_id), {}
    )
    away_lineup_raw = next(
        (l for l in raw_lineups if l.get("team", {}).get("id") == away_id), {}
    )

    # ── Step 4: assemble response ────────────────────────────────────────────
    return {
        "fixture": {
            "id": fixture_id,
            "date": fixture["fixture"]["date"],
            "timestamp": fixture["fixture"]["timestamp"],
            "referee": fixture["fixture"].get("referee"),
            "venue": {
                "name": fixture["fixture"].get("venue", {}).get("name"),
                "city": fixture["fixture"].get("venue", {}).get("city"),
            },
            "status": {
                "long": fixture["fixture"]["status"]["long"],
                "short": fixture["fixture"]["status"]["short"],
                "minute": fixture["fixture"]["status"].get("elapsed"),
                "extra_time": fixture["fixture"]["status"].get("extra"),
            },
        },
        "league": {
            "id": league_id,
            "name": fixture["league"]["name"],
            "country": fixture["league"]["country"],
            "logo": fixture["league"]["logo"],
            "flag": fixture["league"].get("flag"),
            "season": season,
            "round": fixture["league"]["round"],
        },
        "teams": {
            "home": {
                "id": home_id,
                "name": fixture["teams"]["home"]["name"],
                "logo": fixture["teams"]["home"]["logo"],
                "winner": fixture["teams"]["home"].get("winner"),
            },
            "away": {
                "id": away_id,
                "name": fixture["teams"]["away"]["name"],
                "logo": fixture["teams"]["away"]["logo"],
                "winner": fixture["teams"]["away"].get("winner"),
            },
        },
        "score": {
            "current": {
                "home": fixture["goals"]["home"],
                "away": fixture["goals"]["away"],
            },
            "halftime": {
                "home": fixture["score"]["halftime"]["home"],
                "away": fixture["score"]["halftime"]["away"],
            },
            "fulltime": {
                "home": fixture["score"]["fulltime"]["home"],
                "away": fixture["score"]["fulltime"]["away"],
            },
            "extratime": {
                "home": fixture["score"].get("extratime", {}).get("home"),
                "away": fixture["score"].get("extratime", {}).get("away"),
            },
            "penalty": {
                "home": fixture["score"].get("penalty", {}).get("home"),
                "away": fixture["score"].get("penalty", {}).get("away"),
            },
        },
        "statistics": {
            "home": _build_team_stats(raw_stats, 0, raw_events, home_id),
            "away": _build_team_stats(raw_stats, 1, raw_events, away_id),
        },
        "events": _build_events(raw_events),
        "lineups": {
            "home": _build_lineup(home_lineup_raw),
            "away": _build_lineup(away_lineup_raw),
        },
        "standings": {
            "home": _find_standing(standings_table, home_id),
            "away": _find_standing(standings_table, away_id),
        },
    }
