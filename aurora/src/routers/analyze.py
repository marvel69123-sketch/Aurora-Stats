import asyncio
import logging
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
# Phase 5A — logic lives in EntityResolver; keep names as compat wrappers.
# ---------------------------------------------------------------------------

from src.core.entity_resolver import (
    fold as _er_fold,
    compact as _er_compact,
    search_variants as _er_search_variants,
    name_match as _er_name_match,
    team_score as _er_team_score,
    pick_best_team as _er_pick_best_team,
    get_resolver as _er_get_resolver,
)


def _fold(text: str) -> str:
    """Compat → entity_resolver.fold."""
    return _er_fold(text)


def _compact(text: str) -> str:
    """Compat → entity_resolver.compact."""
    return _er_compact(text)


def _search_variants(name: str) -> list[str]:
    """Compat → entity_resolver.search_variants."""
    return _er_search_variants(name)


def _name_match(api_name: str, query: str) -> bool:
    """Compat → entity_resolver.name_match."""
    return _er_name_match(api_name, query)


def _team_score(api_team: dict, query: str) -> float:
    """Compat → entity_resolver.team_score."""
    return _er_team_score(api_team, query)


def _pick_best_team(teams: list[dict], query: str) -> dict | None:
    """Compat → entity_resolver.pick_best_team."""
    return _er_pick_best_team(teams, query)


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
    """Compat → EntityResolver.resolve_team_async (returns id + canonical)."""
    result = await _er_get_resolver().resolve_team_async(
        name, teams_search=_safe_teams_search,
    )
    return result.team_id, result.canonical


async def _try_bind_fixture_by_id(
    fixture_id: int,
    home: str,
    away: str,
) -> dict | None:
    """
    P3-A.6 (A+C): bind a known fixture id and skip team-name re-resolve.

    Returns the API fixture row on success, or None to fall back to name lookup.
    Does not invent fixtures. Does not touch engines / DRS / NMB / Gateway.
    """
    try:
        data = await api_football_get("/fixtures", {"id": int(fixture_id)})
    except HTTPException as exc:
        logger.warning(
            "fixture_id_bind fetch failed id=%s status=%s detail=%s",
            fixture_id,
            getattr(exc, "status_code", "?"),
            getattr(exc, "detail", exc),
        )
        return None
    except Exception as exc:
        logger.warning("fixture_id_bind fetch error id=%s err=%s", fixture_id, exc)
        return None

    rows = data.get("response") or []
    if not rows:
        logger.info("fixture_id_bind empty response id=%s — fall back to name resolve", fixture_id)
        return None

    chosen = rows[0]
    got_id = ((chosen.get("fixture") or {}).get("id"))
    if got_id is not None and int(got_id) != int(fixture_id):
        logger.warning(
            "fixture_id_bind id mismatch requested=%s got=%s — fall back",
            fixture_id,
            got_id,
        )
        return None

    api_h = str(((chosen.get("teams") or {}).get("home") or {}).get("name") or "")
    api_a = str(((chosen.get("teams") or {}).get("away") or {}).get("name") or "")
    names_ok = True
    if (home or "").strip() and (away or "").strip():
        names_ok = (
            (_name_match(api_h, home) and _name_match(api_a, away))
            or (_name_match(api_h, away) and _name_match(api_a, home))
        )
    if not names_ok:
        # ID is authoritative when caller passed it; warn but still bind.
        logger.warning(
            "fixture_id_bind name soft-mismatch id=%s api=%r vs %r query=%r vs %r "
            "— trusting fixture_id",
            fixture_id,
            api_h,
            api_a,
            home,
            away,
        )

    logger.info(
        "fixture_id_bind ok id=%s home=%r away=%r skipped_name_reresolve=1",
        fixture_id,
        api_h,
        api_a,
    )
    return chosen


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


def _extract_xg(stat_list: list):
    """P2b Wave 2 — accept common provider xG type aliases (no invention)."""
    aliases = (
        "expected_goals",
        "Expected Goals",
        "expectedGoals",
        "xG",
        "XG",
        "xg",
    )
    for name in aliases:
        val = _extract_stat(stat_list, name)
        if val is not None:
            return val
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
        "xg": _extract_xg(stat_list),
        "yellow_cards": yellow,
        "red_cards": red,
    }


def _build_events(raw_events: list) -> list:
    # Keep analyze payload shape; Wave 2 normalizes again inside NMB.
    out = []
    for e in raw_events:
        out.append(
            {
                "id": e.get("id"),
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
        )
    return out


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
    fixture_id: int | None = Query(
        None,
        description=(
            "P3-A.6: when known (e.g. discovery fixture_id_hint), bind this "
            "fixture id and skip team-name re-resolve."
        ),
    ),
    force_refresh: bool = Query(
        False,
        description=(
            "Emergency Cost Protection: premium path — allow provider refresh. "
            "Simple analyses prefer cache/stale and skip duplicate network calls."
        ),
    ),
    user_id: str | None = Query(
        None,
        description="Optional user/session key for daily consultation budget.",
    ),
):
    """
    Locate a fixture by team names and return a single structured JSON object
    containing fixture details, live statistics, match events, lineups, and
    league standings — ready for AI analysis.

    Discovery order:
    0. Optional fixture_id bind (P3-A.6) — skips name re-resolve when present
    1. Live matches (if the game is currently in play)
    2. Recent / upcoming fixtures resolved via team search

    When soft=True (Inference Layer V2), resolution failures continue with a
    synthetic partial payload + _inference metadata instead of aborting.
    """
    from src.core.inference_context import InferenceContext, build_partial_analyze_data
    from src.ops import cost_protection as _ecpm

    # Internal callers (copilot_engine, etc.) invoke this as a plain coroutine.
    # FastAPI Query()/Param defaults must not leak as runtime values — otherwise
    # bool(user_id) is truthy and begin_request(...).strip() raises AttributeError.
    if not isinstance(prefer_live, bool):
        prefer_live = False
    if not isinstance(soft, bool):
        soft = False
    if fixture_id is not None and not isinstance(fixture_id, int):
        fixture_id = None
    if not isinstance(force_refresh, bool):
        force_refresh = False
    if user_id is not None and not isinstance(user_id, str):
        user_id = None

    # Protect only when already in ECPM scope (copilot) or explicit user/premium.
    # Cert scripts call this without scope → unrestricted.
    _ecpm_tokens = None
    if not _ecpm.is_request_active() and _ecpm.is_enabled() and (
        bool(force_refresh) or bool(user_id)
    ):
        _ecpm_tokens = _ecpm.begin_request(
            user_id or "anonymous",
            force_refresh=bool(force_refresh),
        )
    elif _ecpm.is_request_active() and force_refresh:
        _ecpm.set_force_refresh(True)
    try:
        return await _analyze_fixture_inner(
            home=home,
            away=away,
            prefer_live=prefer_live,
            soft=soft,
            fixture_id=fixture_id,
            force_refresh=bool(force_refresh) or _ecpm.is_force_refresh(),
        )
    finally:
        if _ecpm_tokens is not None:
            _ecpm.end_request(_ecpm_tokens)


async def _analyze_fixture_inner(
    *,
    home: str,
    away: str,
    prefer_live: bool,
    soft: bool,
    fixture_id: int | None,
    force_refresh: bool,
):
    from src.core.inference_context import InferenceContext, build_partial_analyze_data
    from src.ops import cost_protection as _ecpm

    ictx = InferenceContext(soft_mode=soft)

    cache_key = _ecpm.analyze_cache_key(home, away, fixture_id)
    cached_payload = _ecpm.get_cached_analyze(cache_key)
    if cached_payload is not None and not force_refresh:
        budget = _ecpm.consume_query(from_analyze_cache=True)
        if not budget.allowed:
            # Still return cache when budget exhausted — zero provider cost
            out = dict(cached_payload)
            out["_cost_protection"] = {
                "served_from": "analyze_cache",
                "daily_budget_remaining": 0,
                "reason": "daily_budget_exhausted_cache_only",
            }
            return out
        out = dict(cached_payload)
        out["_cost_protection"] = {
            "served_from": "analyze_cache",
            "daily_budget_remaining": budget.remaining,
            "force_refresh": False,
            **_ecpm.metrics().get("current", {}),
        }
        return out

    budget = _ecpm.check_budget()
    if _ecpm.is_request_active() and _ecpm.is_enabled() and not budget.allowed:
        if soft:
            _partial = build_partial_analyze_data(
                home,
                away,
                reason="daily_budget_exhausted — emergency cost protection",
                ctx=ictx,
            )
            _partial["_cost_protection"] = {
                "blocked": True,
                "reason": "daily_budget_exhausted",
                "daily_budget_remaining": 0,
            }
            return _partial
        raise HTTPException(status_code=429, detail="daily_budget_exhausted")

    _ecpm.consume_query(force_refresh=force_refresh)

    # ── Step 1: resolve the fixture ─────────────────────────────────────────
    try:
        fixture = None
        if fixture_id is not None:
            try:
                fid = int(fixture_id)
            except (TypeError, ValueError):
                fid = 0
            if fid > 0:
                fixture = await _try_bind_fixture_by_id(fid, home, away)
                if fixture is not None and _ecpm.is_request_active():
                    _ecpm.record_provider_call()
        if fixture is None:
            fixture = await _find_fixture(home, away, prefer_live=prefer_live)
            if _ecpm.is_request_active():
                _ecpm.record_provider_call(n=3)
    except HTTPException as exc:
        if soft and exc.status_code == 404:
            logger.warning(
                "analyze soft: fixture resolve failed — continuing with partial data "
                "home=%r away=%r detail=%s",
                home, away, exc.detail,
            )
            _partial_payload = build_partial_analyze_data(
                home, away, reason=str(exc.detail), ctx=ictx,
            )
            try:
                from src.ops.live_density import record_analyze_sample as _ops_record

                _ops_record(
                    _partial_payload,
                    home=str(home or ""),
                    away=str(away or ""),
                    league_hint=None,
                )
            except Exception:
                pass
            return _partial_payload
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

    # ── Step 2: fan out via P2b gateway+cache (soft never aborts) ───────────
    from src.data.ingest import (
        fetch_calendar_by_date,
        fetch_events,
        fetch_injuries,
        fetch_lineups,
        fetch_odds,
        fetch_statistics,
        fetch_standings,
        fetch_status,
    )

    _signal_provenance: dict = {}
    _any_rate_limited = False

    async def _safe_ingest(coro, signal: str) -> dict:
        nonlocal _any_rate_limited
        try:
            outcome = await coro
        except Exception as exc:
            logger.warning("analyze soft-fetch failed signal=%s: %s", signal, exc)
            if soft:
                detail = str(exc)
                ictx.register_failure("api_fetch", detail, signal=signal)
                try:
                    from src.core.partial_analysis import is_rate_limit_error

                    if is_rate_limit_error(detail):
                        ictx.register_failure(
                            "rate_limit",
                            detail,
                            signal="api_rate_limit",
                        )
                        ictx.notes.append(
                            "Rate limit API — mantendo análise preliminar"
                        )
                        _any_rate_limited = True
                except Exception:
                    pass
                _signal_provenance[signal] = {
                    "source": "error",
                    "quality": "missing",
                }
                return {"response": []}
            raise

        if outcome.rate_limited or outcome.circuit_open or not outcome.ok:
            detail = outcome.error or outcome.source
            ictx.register_failure("api_fetch", str(detail), signal=signal)
            if outcome.rate_limited:
                _any_rate_limited = True
                try:
                    ictx.register_failure(
                        "rate_limit",
                        str(detail),
                        signal="api_rate_limit",
                    )
                    ictx.notes.append(
                        "Rate limit API — mantendo análise preliminar"
                    )
                except Exception:
                    pass
        _signal_provenance[signal] = {
            "source": outcome.source,
            "quality": outcome.quality,
        }
        if not soft and not outcome.ok and outcome.source == "error":
            raise HTTPException(
                status_code=502,
                detail=f"API fetch failed for {signal}: {outcome.error}",
            )
        return outcome.data if isinstance(outcome.data, dict) else {"response": []}

    stats_data, events_data, lineups_data, standings_data, status_data = (
        await asyncio.gather(
            _safe_ingest(
                fetch_statistics(fixture_id, status_short=status_short),
                "statistics",
            ),
            _safe_ingest(
                fetch_events(fixture_id, status_short=status_short),
                "events",
            ),
            _safe_ingest(
                fetch_lineups(fixture_id, status_short=status_short),
                "lineups",
            ),
            _safe_ingest(
                fetch_standings(league_id, season, status_short=status_short),
                "standings",
            ),
            _safe_ingest(fetch_status(fixture_id), "status"),
        )
    )

    # P2b Wave 3 — odds / injuries / calendar (soft; empty on miss; never invent)
    _kickoff_date = None
    try:
        _raw_date = str(fixture.get("fixture", {}).get("date") or "")
        _kickoff_date = _raw_date.split("T", 1)[0] if _raw_date else None
    except Exception:
        _kickoff_date = None

    async def _empty_cal() -> dict:
        return {"response": []}

    odds_data, injuries_data, calendar_data = await asyncio.gather(
        _safe_ingest(fetch_odds(fixture_id, status_short=status_short), "odds"),
        _safe_ingest(
            fetch_injuries(fixture_id, status_short=status_short), "injuries"
        ),
        _safe_ingest(
            fetch_calendar_by_date(_kickoff_date, status_short=status_short),
            "calendar",
        )
        if _kickoff_date
        else _empty_cal(),
    )

    # Prefer fresh status block when gateway returned a fixture row
    try:
        _st_resp = status_data.get("response") or []
        if isinstance(_st_resp, list) and _st_resp:
            _st_fx = (_st_resp[0] or {}).get("fixture") or {}
            _st_status = _st_fx.get("status")
            if isinstance(_st_status, dict) and _st_status.get("short"):
                fixture["fixture"]["status"] = _st_status
                status_short = str(_st_status.get("short", "")).upper()
                status_minute = _st_status.get("elapsed")
    except Exception:
        pass

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

    # Wave 3 — attach odds / injuries / calendar (normalize; never invent)
    try:
        from src.data.odds import normalize_odds_payload

        _odds_norm = normalize_odds_payload(odds_data)
        if _odds_norm:
            payload["odds"] = _odds_norm
        else:
            payload["_odds_raw"] = odds_data
    except Exception:
        payload["_odds_raw"] = (
            odds_data if isinstance(odds_data, dict) else {"response": []}
        )

    try:
        payload["_injuries_raw"] = (
            injuries_data if isinstance(injuries_data, dict) else {"response": []}
        )
        if (payload["_injuries_raw"].get("response") or []):
            payload["injuries"] = payload["_injuries_raw"]
    except Exception:
        pass

    try:
        _cal_resp = (
            calendar_data.get("response")
            if isinstance(calendar_data, dict)
            else []
        ) or []
        if isinstance(_cal_resp, list) and _cal_resp:
            nearby = []
            for row in _cal_resp[:40]:
                if not isinstance(row, dict):
                    continue
                lg = (row.get("league") or {}).get("id")
                if lg is not None and int(lg) != int(league_id):
                    continue
                nearby.append(row)
            payload["calendar"] = nearby[:12]
    except Exception:
        pass

    if soft:
        # Seed inference notes from secondary fetch failures already recorded
        payload["_inference"] = ictx.to_dict()

    # P2b Wave 1/2/3 — NMB + DRS (ops/presentation; never invents signals)
    payload["_signal_provenance"] = _signal_provenance
    try:
        from src.data.degradation import apply_degradation_plan
        from src.data.drs import compute_drs
        from src.data.nmb import build_nmb_from_analyze_payload

        _user_wants_live = bool(prefer_live) or status_short in LIVE_STATUSES
        nmb = build_nmb_from_analyze_payload(
            payload,
            binding_quality="FULL",
            rate_limited=_any_rate_limited,
            user_wants_live=_user_wants_live,
        )
        drs = compute_drs(nmb)
        deg = apply_degradation_plan(
            drs,
            rate_limited=_any_rate_limited,
            user_wants_live=_user_wants_live,
        )
        payload["_nmb"] = nmb.to_dict()
        payload["_drs"] = drs
        payload["_degradation"] = deg
        payload["_data_plane"] = {
            "wave": "p2b_wave3",
            "wave1": "p2b_wave1",
            "wave2": "p2b_wave2",
            "completion_rate": nmb.completion_rate(),
            "wave2_completion_rate": nmb.wave2_completion_rate(),
            "wave3_completion_rate": nmb.wave3_completion_rate(),
            "xg_coverage": nmb.xg_coverage(),
            "event_coverage": nmb.event_coverage(),
            "odds_coverage": nmb.odds_coverage(),
            "calendar_coverage": nmb.calendar_coverage(),
            "lineup_coverage": nmb.lineup_coverage(),
            "injury_coverage": nmb.injury_coverage(),
            "premium_analysis": bool(drs.get("premium_analysis")),
            "data_freshness_score": (nmb.meta.get("freshness") or {}).get(
                "freshness_score"
            ),
            "tier": drs.get("tier"),
            "drs": drs.get("drs"),
            "rate_limited": _any_rate_limited,
            "provenance": _signal_provenance,
        }
    except Exception as _dp_exc:
        logger.warning("analyze: data plane attach skipped (%s)", _dp_exc)

    # P3-A — operational intelligence (observability only; never mutates data plane)
    try:
        from src.ops.live_density import record_analyze_sample as _ops_record

        _ops_record(
            payload,
            home=str(home or ""),
            away=str(away or ""),
            league_hint=str((payload.get("league") or {}).get("name") or "") or None,
        )
    except Exception as _ops_exc:
        logger.warning("analyze: ops density record skipped (%s)", _ops_exc)

    try:
        from src.ops import cost_protection as _ecpm_end

        if _ecpm_end.is_request_active():
            _ecpm_end.set_cached_analyze(cache_key, payload)
            cur = (_ecpm_end.metrics().get("current") or {})
            payload["_cost_protection"] = {
                "served_from": "network_or_signal_cache",
                "force_refresh": bool(force_refresh),
                "daily_budget_remaining": _ecpm_end.check_budget().remaining,
                "cache_hit_rate": _ecpm_end.metrics().get("cache_hit_rate"),
                "provider_calls": cur.get("provider_calls"),
            }
    except Exception:
        pass

    return payload


@router.get("/cost-protection/metrics")
async def cost_protection_metrics(user_id: str | None = Query(None)):
    """Emergency Cost Protection metrics (quota preservation)."""
    from src.ops.cost_protection import metrics

    return metrics(user_id)
