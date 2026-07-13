import asyncio
import logging
import re
import unicodedata
from fastapi import APIRouter, Query, HTTPException
from src.client import api_football_get
from src.core.fixture_status import LIVE_STATUSES, fixture_is_live

logger = logging.getLogger(__name__)
router = APIRouter()


def _map_api_status(api_status: dict) -> dict:
    """Map API-Football status → Aurora canonical schema (minute, not elapsed)."""
    return {
        "long":       api_status.get("long"),
        "short":      api_status.get("short"),
        "minute":     int(api_status.get("elapsed") or 0),
        "extra_time": api_status.get("extra"),
    }


# ---------------------------------------------------------------------------
# Team / fixture discovery
# ---------------------------------------------------------------------------

def _fold(text: str) -> str:
    """Lowercase, strip accents/apostrophes/hyphens/punctuation → spaced tokens."""
    t = (text or "").lower().strip()
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    t = re.sub(r"[''`´’]", "", t)          # O'Higgins → Ohiggins → ohiggins
    t = re.sub(r"[^\w\s]", " ", t)         # leftover punct → space
    t = re.sub(r"[-_]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _compact(text: str) -> str:
    """Fully compacted key: 'O'Higgins' → 'ohiggins', 'Ñublense' → 'nublense'."""
    return re.sub(r"\s+", "", _fold(text))


def _search_variants(name: str) -> list[str]:
    """Generate API /teams?search= variants for international / smaller clubs."""
    folded = _fold(name)
    compact = _compact(name)
    # Prefer apostrophe-free / compact first — API-Football often 400s on O'Higgins
    variants: list[str] = []
    for v in (
        compact,                       # ohiggins, nublense
        folded,                        # o higgins → ohiggins after fold
        name.replace("'", "").replace("'", "").strip(),
        name.strip(),
        folded.replace(" ", "-"),
        folded.split()[0] if folded.split() else folded,
    ):
        if v and v not in variants and len(v) >= 3:
            variants.append(v)
    return variants


def _name_match(api_name: str, query: str) -> bool:
    """
    Fuzzy / contains match against API-Football team names.

    Uses folded + compacted forms so:
      O'Higgins ↔ ohiggins ↔ O Higgins
      Ñublense  ↔ nublense
    """
    api_f = _fold(api_name)
    q_f = _fold(query)
    api_c = _compact(api_name)
    q_c = _compact(query)
    if not q_f or not api_f:
        return False
    if q_f == api_f or q_c == api_c:
        return True
    if q_f in api_f or api_f in q_f or q_c in api_c or api_c in q_c:
        return True
    q_words = [w for w in q_f.split() if len(w) > 1]
    if q_words and all(w in api_f or w in api_c for w in q_words):
        return True
    hits = sum(1 for w in q_words if w in api_f or w in api_c)
    return bool(q_words) and hits >= max(1, (len(q_words) + 1) // 2)


def _team_score(api_team: dict, query: str) -> float:
    """Rank API /teams results — prefer exact/folded/compact match."""
    name = (api_team.get("team") or {}).get("name") or ""
    country = ((api_team.get("team") or {}).get("country") or "").lower()
    q_f, n_f = _fold(query), _fold(name)
    q_c, n_c = _compact(query), _compact(name)
    score = 0.0
    if n_c == q_c or n_f == q_f:
        score += 100
    elif q_c in n_c or n_c in q_c or q_f in n_f or n_f in q_f:
        score += 60
    q_words = [w for w in q_f.split() if len(w) > 1]
    if q_words and all(w in n_f or w in n_c for w in q_words):
        score += 40
    else:
        score += 10 * sum(1 for w in q_words if w in n_f or w in n_c)
    # Soft country boosts (Brazil + Chile common for these clubs)
    if any(c in country for c in ("brazil", "brasil", "chile")):
        score += 15
    if not (api_team.get("team") or {}).get("national"):
        score += 5
    return score


def _pick_best_team(teams: list[dict], query: str) -> dict | None:
    """Score and pick the best /teams search hit for *query*."""
    if not teams:
        return None
    ranked = sorted(teams, key=lambda t: _team_score(t, query), reverse=True)
    best = ranked[0]
    logger.info(
        "fixture_lookup pick_team query=%r selected=%r score=%.1f candidates=%s",
        query,
        (best.get("team") or {}).get("name"),
        _team_score(best, query),
        [(t.get("team") or {}).get("name") for t in ranked[:5]],
    )
    return best


async def _safe_teams_search(query: str) -> list[dict]:
    """Call /teams?search= without aborting the pipeline on API 400 errors."""
    try:
        res = await api_football_get("/teams", {"search": query})
        return res.get("response", []) or []
    except HTTPException as exc:
        logger.warning(
            "fixture_lookup teams_search failed query=%r status=%s detail=%s",
            query, getattr(exc, "status_code", "?"), getattr(exc, "detail", exc),
        )
        return []


async def _resolve_team_id(name: str) -> tuple[int | None, str | None]:
    """Try multiple search variants until a team is found."""
    all_hits: list[dict] = []
    for variant in _search_variants(name):
        hits = await _safe_teams_search(variant)
        logger.info(
            "fixture_lookup teams_search variant=%r hits=%d names=%s",
            variant, len(hits),
            [(h.get("team") or {}).get("name") for h in hits[:5]],
        )
        all_hits.extend(hits)
        pick = _pick_best_team(hits, name)
        if pick and _team_score(pick, name) >= 40:
            return pick["team"]["id"], pick["team"]["name"]
    # Global best across all variants
    pick = _pick_best_team(all_hits, name)
    if pick:
        return pick["team"]["id"], pick["team"]["name"]
    return None, None


async def _find_fixture(home: str, away: str, prefer_live: bool = False) -> dict:
    """
    Return the best matching fixture for the supplied team names.

    Strategy (no immediate 400):
      1. Live sweep with fuzzy name match.
      2. Resolve team IDs via multi-variant /teams search.
      3. last/next fixtures for both teams + head-to-head.
      4. Prefer LIVE status among candidates.
    """
    norm_home, norm_away = _fold(home), _fold(away)
    compact_home, compact_away = _compact(home), _compact(away)
    logger.info(
        "fixture_lookup start home=%r away=%r normalized_home=%r normalized_away=%r "
        "compact_home=%r compact_away=%r prefer_live=%s",
        home, away, norm_home, norm_away, compact_home, compact_away, prefer_live,
    )

    # 1. Live sweep
    try:
        live_data = await api_football_get("/fixtures", {"live": "all"})
        live_fixtures = live_data.get("response", []) or []
    except HTTPException as exc:
        logger.warning("fixture_lookup live_sweep failed: %s", exc.detail)
        live_fixtures = []

    live_candidates = []
    for f in live_fixtures:
        api_h = f["teams"]["home"]["name"]
        api_a = f["teams"]["away"]["name"]
        if (_name_match(api_h, home) and _name_match(api_a, away)) or (
            _name_match(api_h, away) and _name_match(api_a, home)
        ):
            live_candidates.append(f)

    logger.info(
        "fixture_lookup candidate fixtures=%s",
        [
            f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}"
            for f in live_candidates[:10]
        ],
    )
    if live_candidates:
        chosen = live_candidates[0]
        logger.info(
            "fixture_lookup selected fixture=%s vs %s status=%s source=live_sweep "
            "home=%r away=%r normalized_home=%r normalized_away=%r",
            chosen["teams"]["home"]["name"],
            chosen["teams"]["away"]["name"],
            (chosen.get("fixture") or {}).get("status", {}).get("short"),
            home, away, norm_home, norm_away,
        )
        return chosen

    # 2. Resolve team IDs (multi-variant, soft-fail)
    home_id, home_name = await _resolve_team_id(home)
    away_id, away_name = await _resolve_team_id(away)
    logger.info(
        "fixture_lookup resolved home=%r→id=%s name=%r | away=%r→id=%s name=%r",
        home, home_id, home_name, away, away_id, away_name,
    )

    if not home_id:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No team found matching '{home}'. "
                f"Tried variants: {_search_variants(home)}. "
                f"Try the official API name (e.g. 'Botafogo PB')."
            ),
        )
    if not away_id:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No team found matching '{away}'. "
                f"Tried variants: {_search_variants(away)}."
            ),
        )

    # 3. Collect fixtures from both teams + H2H
    async def _team_fixtures(team_id: int) -> list[dict]:
        try:
            last_res, next_res = await asyncio.gather(
                api_football_get("/fixtures", {"team": team_id, "last": 15}),
                api_football_get("/fixtures", {"team": team_id, "next": 10}),
            )
            return (last_res.get("response", []) or []) + (next_res.get("response", []) or [])
        except HTTPException as exc:
            logger.warning("fixture_lookup team_fixtures id=%s failed: %s", team_id, exc.detail)
            return []

    home_fx, away_fx = await asyncio.gather(
        _team_fixtures(home_id),
        _team_fixtures(away_id),
    )

    h2h: list[dict] = []
    try:
        h2h_res = await api_football_get(
            "/fixtures/headtohead",
            {"h2h": f"{home_id}-{away_id}", "last": 10},
        )
        h2h = h2h_res.get("response", []) or []
    except HTTPException as exc:
        logger.warning("fixture_lookup h2h failed: %s", exc.detail)

    pool = home_fx + away_fx + h2h
    # Deduplicate by fixture id
    seen: set[int] = set()
    unique: list[dict] = []
    for f in pool:
        fid = (f.get("fixture") or {}).get("id")
        if fid and fid not in seen:
            seen.add(fid)
            unique.append(f)

    matches: list[dict] = []
    for f in unique:
        fh_id = f["teams"]["home"]["id"]
        fa_id = f["teams"]["away"]["id"]
        if {fh_id, fa_id} == {home_id, away_id}:
            matches.append(f)

    cand_log = [
        f"{f['teams']['home']['name']} vs {f['teams']['away']['name']} "
        f"[{(f.get('fixture') or {}).get('status', {}).get('short')}]"
        for f in matches[:15]
    ]
    logger.info(
        "fixture_lookup candidate fixtures=%d list=%s",
        len(matches), cand_log,
    )

    if not matches:
        # Last resort: fuzzy name match inside the combined pool
        fuzzy = []
        for f in unique:
            api_h = f["teams"]["home"]["name"]
            api_a = f["teams"]["away"]["name"]
            if (_name_match(api_h, home) and _name_match(api_a, away)) or (
                _name_match(api_h, away) and _name_match(api_a, home)
            ):
                fuzzy.append(f)
        logger.info(
            "fixture_lookup fuzzy_fallback hits=%d list=%s",
            len(fuzzy),
            [
                f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}"
                for f in fuzzy[:10]
            ],
        )
        matches = fuzzy

    if not matches:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No fixture found between '{home_name}' and '{away_name}' "
                f"(ids {home_id}/{away_id}) in recent/upcoming/H2H results."
            ),
        )

    live_matches = [
        f for f in matches
        if str((f.get("fixture") or {}).get("status", {}).get("short", "")).upper()
        in LIVE_STATUSES
    ]
    # Prefer live; else most recent by timestamp
    if live_matches:
        chosen = live_matches[0]
    else:
        chosen = sorted(
            matches,
            key=lambda f: (f.get("fixture") or {}).get("timestamp") or 0,
            reverse=True,
        )[0]

    short = (chosen.get("fixture") or {}).get("status", {}).get("short", "")
    logger.info(
        "fixture_lookup selected fixture=%s vs %s status=%s is_live=%s "
        "home=%r away=%r normalized_home=%r normalized_away=%r",
        chosen["teams"]["home"]["name"],
        chosen["teams"]["away"]["name"],
        short,
        fixture_is_live({"short": short}),
        home, away, norm_home, norm_away,
    )
    return chosen

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
            "minute": e.get("time", {}).get("elapsed"),  # API event time — ingestion only
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
    prefer_live: bool = Query(False, description="Prefer in-play fixtures when resolving"),
    soft: bool = Query(
        False,
        description=(
            "Inference Layer V2: on missing fixture/teams, return a partial "
            "payload instead of HTTP 404 (used by /aurora/copilot)."
        ),
    ),
):
    """
    Locate a fixture by team names and return a single structured JSON object
    containing fixture details, live statistics, match events, lineups, and
    league standings — ready for AI analysis.

    Discovery order:
    1. Live matches (if the game is currently in play)
    2. Recent / upcoming fixtures resolved via team search

    When soft=True (Inference Layer V2), resolution failures continue with a
    synthetic partial payload + _inference metadata instead of aborting.
    """
    from src.core.inference_context import InferenceContext, build_partial_analyze_data

    ictx = InferenceContext(soft_mode=soft)

    # ── Step 1: resolve the fixture ─────────────────────────────────────────
    try:
        fixture = await _find_fixture(home, away, prefer_live=prefer_live)
    except HTTPException as exc:
        if soft and exc.status_code == 404:
            logger.warning(
                "analyze soft: fixture resolve failed — continuing with partial data "
                "home=%r away=%r detail=%s",
                home, away, exc.detail,
            )
            return build_partial_analyze_data(
                home, away, reason=str(exc.detail), ctx=ictx,
            )
        raise

    fixture_id: int = fixture["fixture"]["id"]
    league_id: int = fixture["league"]["id"]
    season: int = fixture["league"]["season"]
    home_id: int = fixture["teams"]["home"]["id"]
    away_id: int = fixture["teams"]["away"]["id"]

    status_short = str(fixture["fixture"]["status"].get("short", "")).upper()
    status_minute = fixture["fixture"]["status"].get("elapsed")
    logger.info(
        "pipeline=analyze fixture=%s vs %s status=%s minute=%s is_live=%s fixture_id=%s soft=%s",
        fixture["teams"]["home"]["name"],
        fixture["teams"]["away"]["name"],
        status_short,
        status_minute,
        status_short in LIVE_STATUSES,
        fixture_id,
        soft,
    )

    # ── Step 2: fan out – soft mode never aborts on secondary fetch failure ──
    async def _safe_get(path: str, params: dict, signal: str) -> dict:
        try:
            return await api_football_get(path, params)
        except Exception as exc:
            logger.warning("analyze soft-fetch failed signal=%s: %s", signal, exc)
            if soft:
                ictx.register_failure("api_fetch", str(exc), signal=signal)
                return {"response": []}
            raise

    stats_data, events_data, lineups_data, standings_data = await asyncio.gather(
        _safe_get("/fixtures/statistics", {"fixture": fixture_id}, "statistics"),
        _safe_get("/fixtures/events", {"fixture": fixture_id}, "events"),
        _safe_get("/fixtures/lineups", {"fixture": fixture_id}, "lineups"),
        _safe_get("/standings", {"league": league_id, "season": season}, "standings"),
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
    payload = {
        "fixture": {
            "id": fixture_id,
            "date": fixture["fixture"]["date"],
            "timestamp": fixture["fixture"]["timestamp"],
            "referee": fixture["fixture"].get("referee"),
            "venue": {
                "name": fixture["fixture"].get("venue", {}).get("name"),
                "city": fixture["fixture"].get("venue", {}).get("city"),
            },
            "status": _map_api_status(fixture["fixture"]["status"]),
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

    if soft:
        # Seed inference notes from secondary fetch failures already recorded
        payload["_inference"] = ictx.to_dict()

    return payload
